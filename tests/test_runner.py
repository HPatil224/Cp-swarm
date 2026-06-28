"""
Phase 0 tests for the resource-limited runner. This is the safety-critical
surface — validate every failure mode (TLE, MLE, RTE, clean OK) against
hand-written C++ before trusting it with LLM-generated code.
"""

import pytest

from execution.compiler import compile_cpp
from execution.resource_limits import ExecutionOutcome, ResourceLimits
from execution.runner import run_test_case

LIMITS = ResourceLimits(cpu_time_seconds=2, wall_time_seconds=3, memory_mb=128)


def _compile(tmp_path, source, run_id):
    result = compile_cpp(source, run_id=run_id, workspace_dir=tmp_path)
    assert result.success, result.stderr
    return result.binary_path


def test_clean_exit_within_limits(tmp_path):
    src = """
#include <iostream>
int main() { int x; std::cin >> x; std::cout << x * 2; return 0; }
"""
    binary = _compile(tmp_path, src, "ok")
    result = run_test_case(binary, stdin_data="21\n", limits=LIMITS)
    assert result.execution.outcome == ExecutionOutcome.OK
    assert result.actual_output.strip() == "42"


def test_infinite_loop_triggers_tle(tmp_path):
    src = """
int main() { while(true) {} return 0; }
"""
    binary = _compile(tmp_path, src, "tle")
    result = run_test_case(binary, stdin_data="", limits=LIMITS)
    assert result.execution.outcome == ExecutionOutcome.TLE


def test_huge_allocation_triggers_mle(tmp_path):
    src = """
#include <vector>
int main() {
    std::vector<long long> v;
    while (true) v.push_back(0); // grows unbounded
    return 0;
}
"""
    binary = _compile(tmp_path, src, "mle")
    result = run_test_case(binary, stdin_data="", limits=LIMITS)
    assert result.execution.outcome == ExecutionOutcome.MLE


def test_segfault_triggers_rte(tmp_path):
    src = """
int main() {
    int* p = nullptr;
    *p = 1; // segfault
    return 0;
}
"""
    binary = _compile(tmp_path, src, "rte")
    result = run_test_case(binary, stdin_data="", limits=LIMITS)
    assert result.execution.outcome == ExecutionOutcome.RTE


# TODO(phase 0): test that the child process genuinely cannot reach the
# network (e.g. attempt a socket connection in the test source and assert
# it fails/is blocked) once resource_limits.py decides its network policy.
