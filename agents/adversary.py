import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from agents.architect import CodeVersion
from agents.base_agent import BaseAgent
from execution.resource_limits import ExecutionOutcome
from problems.schema import Problem


class FailureType(Enum):
    TLE = "tle"
    MLE = "mle"
    RTE = "rte"
    WA = "wrong_answer"
    COMPILE_ERROR = "compile_error"
    NONE = "none"  # all tests passed


@dataclass
class GeneratedTest:
    input_data: str
    hypothesis: str                       # what this test is trying to break, and why
    expected_output: str | None = None    # None if only checking for crash/TLE, not WA


@dataclass
class AdversaryReport:
    failure_type: FailureType
    failing_test: GeneratedTest | None = None
    actual_output: str | None = None
    minimal_repro_input: str | None = None  # shrunk version of failing_test.input_data, if shrinking was attempted
    likely_wrong_approach: bool = False
    notes: str = ""

    @property
    def passed(self) -> bool:
        return self.failure_type == FailureType.NONE


def _parse_xml_tag(text: str, tag: str) -> str:
    pattern = f"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_xml_list(text: str, tag: str) -> list[str]:
    pattern = f"<{tag}>(.*?)</{tag}>"
    return [m.strip() for m in re.findall(pattern, text, re.DOTALL)]


class Adversary(BaseAgent):
    agent_name = "adversary"

    def system_prompt_filename(self) -> str:
        return "adversary.md"

    def generate_tests(self, problem: Problem, code: CodeVersion, run_id: str = "default") -> list[GeneratedTest]:
        """
        Format stress testing prompt, call Claude, and parse generated tests + naive C++ reference code.
        """
        user_message = f"""
We are solving the following competitive programming problem:

Title: {problem.title}
Statement:
{problem.statement}

The Architect has produced the following C++ code implementation:
```cpp
{code.source_code}
```

Your goal is to break this implementation by generating stress tests (scale tests, boundary values, integer overflow-triggering tests, and degenerate structural tests).

To do this, please output:
1. An obviously correct, simple (e.g. O(N^2) or brute-force) reference solution in C++ wrapped in <reference_source>...</reference_source>.
2. A list of test cases, each wrapped in a <test_case>...</test_case> tag. Inside each <test_case> tag, include:
   - <input>...</input>: the raw string of the test input.
   - <hypothesis>...</hypothesis>: a brief statement explaining what this test is trying to break in the Architect's implementation and why.
   - <expected_output>...</expected_output>: (Optional) expected correct output.

Make sure you wrap all your responses inside the requested XML tags so they can be parsed programmatically.
"""
        raw_response = self.call(user_message, run_id=run_id)
        
        # Save reference source in adversary instance to compile later in run_and_evaluate
        ref_source = _parse_xml_tag(raw_response, "reference_source")
        if "```cpp" in ref_source:
            ref_source = ref_source.split("```cpp")[1].split("```")[0].strip()
        elif "```" in ref_source:
            ref_source = ref_source.split("```")[1].split("```")[0].strip()
            
        self.reference_source = ref_source
        
        test_case_blocks = _parse_xml_list(raw_response, "test_case")
        
        tests = []
        for block in test_case_blocks:
            inp = _parse_xml_tag(block, "input")
            hyp = _parse_xml_tag(block, "hypothesis")
            exp = _parse_xml_tag(block, "expected_output")
            
            if not inp:
                inp = _parse_xml_tag(block, "input_data")
                
            tests.append(GeneratedTest(
                input_data=inp,
                hypothesis=hyp or "stress test",
                expected_output=exp if exp else None
            ))
            
        return tests

    def run_and_evaluate(self, code: CodeVersion, tests: list[GeneratedTest], run_id: str = "default") -> AdversaryReport:
        """
        Compiles the solution and stress-tests it, dynamically running the reference solution to obtain expected answers.
        """
        from config.settings import settings
        from execution.compiler import compile_cpp
        from execution.runner import run_test_case
        from execution.resource_limits import ResourceLimits, ExecutionOutcome
        
        # Compile Architect's solution
        compile_res = compile_cpp(code.source_code, f"{run_id}_architect", settings.paths.workspace_dir)
        if not compile_res.success or not compile_res.binary_path:
            return AdversaryReport(
                failure_type=FailureType.COMPILE_ERROR,
                notes=f"Architect compilation failed:\n{compile_res.stderr}"
            )
            
        ref_binary_path = None
        ref_source = getattr(self, "reference_source", "")
        if ref_source:
            ref_compile_res = compile_cpp(ref_source, f"{run_id}_reference", settings.paths.workspace_dir)
            if ref_compile_res.success and ref_compile_res.binary_path:
                ref_binary_path = ref_compile_res.binary_path
                
        try:
            limits = ResourceLimits(
                cpu_time_seconds=settings.sandbox.run_timeout_seconds,
                wall_time_seconds=settings.sandbox.run_timeout_seconds + 1,
                memory_mb=settings.sandbox.memory_limit_mb
            )
            
            for test in tests:
                expected = test.expected_output
                # Get expected output dynamically if reference binary exists
                if ref_binary_path:
                    ref_limits = ResourceLimits(
                        cpu_time_seconds=settings.sandbox.run_timeout_seconds * 3,
                        wall_time_seconds=settings.sandbox.run_timeout_seconds * 3 + 1,
                        memory_mb=settings.sandbox.memory_limit_mb * 2
                    )
                    ref_res = run_test_case(ref_binary_path, test.input_data, ref_limits)
                    if ref_res.execution.outcome == ExecutionOutcome.OK:
                        expected = ref_res.actual_output.strip()
                        
                # Run Architect's solution
                run_res = run_test_case(compile_res.binary_path, test.input_data, limits)
                
                # Check for run limits / outcomes
                if run_res.execution.outcome == ExecutionOutcome.TLE:
                    likely_wrong = run_res.execution.wall_time_seconds >= limits.cpu_time_seconds
                    return AdversaryReport(
                        failure_type=FailureType.TLE,
                        failing_test=test,
                        actual_output=run_res.actual_output,
                        likely_wrong_approach=likely_wrong,
                        notes=f"TLE after {run_res.execution.wall_time_seconds:.2f} seconds."
                    )
                elif run_res.execution.outcome == ExecutionOutcome.MLE:
                    return AdversaryReport(
                        failure_type=FailureType.MLE,
                        failing_test=test,
                        actual_output=run_res.actual_output,
                        notes=f"MLE: peak memory used was {run_res.execution.peak_memory_mb:.2f} MB."
                    )
                elif run_res.execution.outcome == ExecutionOutcome.RTE:
                    return AdversaryReport(
                        failure_type=FailureType.RTE,
                        failing_test=test,
                        actual_output=run_res.actual_output,
                        notes=f"RTE: exit code {run_res.execution.exit_code}, stderr: {run_res.execution.stderr}"
                    )
                    
                # Compare output for Wrong Answer
                if expected is not None:
                    actual = run_res.actual_output.strip()
                    if actual != expected:
                        return AdversaryReport(
                            failure_type=FailureType.WA,
                            failing_test=test,
                            actual_output=actual,
                            notes=f"WA: expected '{expected}', got '{actual}'"
                        )
                        
            return AdversaryReport(failure_type=FailureType.NONE)
            
        finally:
            try:
                if compile_res.binary_path and compile_res.binary_path.exists():
                    compile_res.binary_path.unlink()
                if ref_binary_path and ref_binary_path.exists():
                    ref_binary_path.unlink()
            except Exception:
                pass
