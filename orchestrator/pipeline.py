"""
The main loop: Mathematician -> Architect -> Adversary -> (retry/escalate/
done), wired together. This is the file Phase 4 is "done" when this
function runs end-to-end against a real problem.

Deliberately thin: this module should mostly call out to agents/ and
execution/ and use orchestrator/policies.py for all retry/escalate/give-up
decisions, rather than embedding that logic inline here.
"""


import uuid
import logging
from config.settings import settings
from agents.mathematician import Mathematician
from agents.architect import Architect, CodeVersion
from agents.adversary import Adversary, FailureType, AdversaryReport
from orchestrator.state import RunState, IterationRecord
from problems.schema import Problem, Approach
import orchestrator.policies as policies

logger = logging.getLogger("orchestrator.pipeline")


from typing import Callable

def solve(
    problem: Problem,
    run_id: str | None = None,
    callback: Callable[[str, dict], None] | None = None
) -> RunState:
    """
    Main loop: Mathematician -> Architect -> Adversary.
    Supports retries, approach escalations, and logs a markdown transcript.
    """
    if not run_id:
        run_id = uuid.uuid4().hex[:8]
    state = RunState(run_id=run_id, problem=problem)
    
    def emit(event: str, data: dict):
        if callback:
            try:
                callback(event, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                
    mathematician = Mathematician(settings.models.mathematician_model, settings.paths.prompts_dir)
    architect = Architect(settings.models.architect_model, settings.paths.prompts_dir)
    adversary = Adversary(settings.models.adversary_model, settings.paths.prompts_dir)
    
    logger.info(f"Starting solver run {run_id} for problem: {problem.title}")
    emit("run_start", {"run_id": run_id, "problem_title": problem.title})
    
    # 1. Mathematician extracts initial approach
    emit("mathematician_start", {})
    state.current_approach = mathematician.extract_approach(problem, run_id=run_id)
    state.approach_history.append(state.current_approach)
    emit("mathematician_end", {
        "pattern": state.current_approach.pattern,
        "complexity_bound": state.current_approach.complexity_bound,
        "justification": state.current_approach.justification,
        "pseudocode": state.current_approach.pseudocode,
        "edge_cases": state.current_approach.flagged_edge_cases
    })
    
    while True:
        # 2. Architect implements or fixes
        attempt = len(state.iterations) + 1
        emit("architect_start", {"attempt": attempt})
        try:
            if not state.iterations:
                code = architect.implement(problem, state.current_approach, run_id=run_id)
            else:
                last_iteration = state.iterations[-1]
                code = architect.fix(
                    problem,
                    state.current_approach,
                    last_iteration.code_version,
                    last_iteration.adversary_report,
                    run_id=run_id
                )
        except Exception as e:
            logger.error(f"Architect implementation crashed: {e}")
            code = CodeVersion(source_code="", implementation_notes=f"Crash: {str(e)}")
            
        emit("architect_end", {
            "source_code": code.source_code,
            "notes": code.implementation_notes,
            "disputes": code.disputes_approach,
            "dispute_reason": code.dispute_reason
        })
            
        # 3. Check for Architect's dispute on approach
        if code.disputes_approach:
            logger.warning(f"Architect disputed approach: {code.dispute_reason}")
            report = AdversaryReport(
                failure_type=FailureType.WA,
                likely_wrong_approach=True,
                notes=f"Architect dispute: {code.dispute_reason}"
            )
            state.iterations.append(IterationRecord(code_version=code, adversary_report=report))
            emit("adversary_end", {
                "failure_type": report.failure_type.value,
                "notes": report.notes,
                "likely_wrong_approach": report.likely_wrong_approach
            })
        else:
            # 4. Adversary generates tests and runs evaluations
            emit("adversary_start", {})
            try:
                tests = adversary.generate_tests(problem, code, run_id=run_id)
                report = adversary.run_and_evaluate(code, tests, run_id=run_id)
            except Exception as e:
                logger.error(f"Adversary evaluation crashed: {e}")
                report = AdversaryReport(
                    failure_type=FailureType.COMPILE_ERROR,
                    notes=f"Adversary crash: {str(e)}"
                )
                
            state.iterations.append(IterationRecord(code_version=code, adversary_report=report))
            
            emit("adversary_end", {
                "failure_type": report.failure_type.value,
                "notes": report.notes,
                "likely_wrong_approach": report.likely_wrong_approach,
                "failing_test": {
                    "input": report.failing_test.input_data,
                    "hypothesis": report.failing_test.hypothesis,
                    "expected": report.failing_test.expected_output
                } if report.failing_test else None,
                "actual_output": report.actual_output
            })
            
        # 5. Check loop conditions
        if policies.is_solved(report):
            state.final_status = "solved"
            logger.info("Problem solved successfully!")
            emit("solved", {"solution": code.source_code})
            break
            
        if policies.should_escalate_to_mathematician(report, state):
            logger.info("Escalating to Mathematician for new approach...")
            state.mathematician_escalations_used += 1
            state.architect_retries_used = 0
            
            emit("mathematician_start", {"escalation": state.mathematician_escalations_used})
            state.current_approach = mathematician.revise_approach(
                problem,
                state.current_approach,
                report,
                run_id=run_id
            )
            state.approach_history.append(state.current_approach)
            emit("mathematician_end", {
                "pattern": state.current_approach.pattern,
                "complexity_bound": state.current_approach.complexity_bound,
                "justification": state.current_approach.justification,
                "pseudocode": state.current_approach.pseudocode,
                "edge_cases": state.current_approach.flagged_edge_cases
            })
            continue
            
        elif policies.should_retry_architect(report, state):
            logger.info("Retrying Architect implementation fix...")
            state.architect_retries_used += 1
            continue
            
        else:
            state.final_status = policies.give_up_reason(state)
            logger.info(f"Swarm giving up. Reason: {state.final_status}")
            emit("failed", {"status": state.final_status})
            break
            
    # 6. Write final markdown transcript and solution.cpp
    try:
        transcript_dir = settings.paths.logs_dir / run_id
        transcript_dir.mkdir(parents=True, exist_ok=True)
        
        # Save transcript
        transcript_file = transcript_dir / "transcript.md"
        transcript_file.write_text(state.to_transcript(), encoding="utf-8")
        logger.info(f"Transcript written to {transcript_file}")
        
        # Save solution.cpp if solved
        if state.final_status == "solved" and state.latest_code():
            solution_file = transcript_dir / "solution.cpp"
            solution_file.write_text(state.latest_code().source_code, encoding="utf-8")
            logger.info(f"Final C++ solution written to standalone file: {solution_file}")
            
    except Exception as e:
        logger.error(f"Failed to write logs/transcripts: {e}")
        
    return state
