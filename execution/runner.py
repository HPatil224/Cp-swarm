"""
Runs a compiled binary against a single test input, under resource limits,
and classifies the outcome.

This is the function both Phase 2 (Architect's sample-I/O check) and Phase 3
(Adversary's stress tests) call — keep the interface stable since both
agents depend on it.

TODO(phase 0):
- Call execution.resource_limits.run_with_limits()
- Track peak memory (e.g. via psutil on the child pid, sampled, OR via
  RLIMIT_AS hard failure — decide which gives better MLE detection fidelity;
  a hard rlimit will SIGKILL/SIGSEGV at the limit rather than reporting peak
  usage, which is fine for "did it exceed" but won't tell you HOW much over)
- Return a TestRunResult that downstream code (Adversary's WA check) can
  compare actual_output against expected_output for correctness, separate
  from the TLE/MLE/RTE classification this module owns.
"""

from dataclasses import dataclass
from pathlib import Path

from execution.resource_limits import ExecutionResult, ResourceLimits, ExecutionOutcome, run_with_limits


@dataclass
class TestRunResult:
    execution: ExecutionResult
    actual_output: str = ""
    # Correctness (WA) is NOT determined here — caller compares
    # actual_output to whatever reference/expected output it has, since this
    # module shouldn't need to know about problem-specific expected values.


def run_test_case(binary_path: Path, stdin_data: str, limits: ResourceLimits) -> TestRunResult:
    """
    Runs a compiled binary against a single test input, under resource limits.
    """
    exec_result = run_with_limits(str(binary_path), stdin_data, limits)
    return TestRunResult(
        execution=exec_result,
        actual_output=exec_result.stdout
    )


def run_against_samples(binary_path: Path, samples: list[tuple[str, str]], limits: ResourceLimits) -> list[bool]:
    """
    Convenience used in Phase 2: run the binary against the problem's own
    sample inputs and return pass/fail per sample (exact string match on
    stdout, post-strip). Real Adversary stress tests do their own richer
    comparison in agents/adversary.py — this is just the cheap sample-I/O
    gate the Architect checks before even involving the Adversary.
    """
    results = []
    for sample_in, sample_out in samples:
        res = run_test_case(binary_path, sample_in, limits)
        if res.execution.outcome == ExecutionOutcome.OK:
            passed = res.actual_output.strip() == sample_out.strip()
            results.append(passed)
        else:
            results.append(False)
    return results
