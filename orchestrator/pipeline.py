"""
The main loop: Mathematician -> Architect -> Adversary -> (retry/escalate/
done), wired together. This is the file Phase 4 is "done" when this
function runs end-to-end against a real problem.

Deliberately thin: this module should mostly call out to agents/ and
execution/ and use orchestrator/policies.py for all retry/escalate/give-up
decisions, rather than embedding that logic inline here.
"""

from agents.adversary import Adversary
from agents.architect import Architect
from agents.mathematician import Mathematician
from orchestrator.state import RunState
from problems.schema import Problem


def solve(problem: Problem) -> RunState:
    """
    TODO(phase 4): implement the full loop. Rough shape:

    1. run_id = uuid.uuid4().hex[:8]; state = RunState(run_id, problem)
    2. mathematician = Mathematician(settings.models.mathematician_model, settings.paths.prompts_dir)
       architect = Architect(...)
       adversary = Adversary(...)
    3. state.current_approach = mathematician.extract_approach(problem)
       state.approach_history.append(state.current_approach)
    4. LOOP:
       a. code = architect.implement(problem, state.current_approach)   # or .fix(...) on retries
       b. if code.disputes_approach: treat like an Adversary
          likely_wrong_approach signal -> go to escalation branch directly
       c. tests = adversary.generate_tests(problem, code)
       d. report = adversary.run_and_evaluate(code, tests)
       e. state.iterations.append(IterationRecord(code, report))
       f. if policies.is_solved(report): state.final_status = "solved"; break
       g. if policies.should_escalate_to_mathematician(report, state):
             state.current_approach = mathematician.revise_approach(problem, state.current_approach, report)
             state.approach_history.append(state.current_approach)
             state.mathematician_escalations_used += 1
             state.architect_retries_used = 0
             continue
       h. elif policies.should_retry_architect(report, state):
             state.architect_retries_used += 1
             continue  # next architect.implement/.fix call uses updated state
       i. else: state.final_status = policies.give_up_reason(state); break
    5. write transcript to logs/runs/<run_id>/ (see state.to_transcript TODO)
    6. return state

    Left unimplemented intentionally — this is the integration point that
    should only be wired once every agent and execution/ piece it calls has
    been independently validated (phases 0-3).
    """
    raise NotImplementedError
