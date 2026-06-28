"""
Top-level convenience wrapper combining compiler.py + runner.py into the
single call site agents actually use: "given this C++ source and this list
of test inputs, compile once and run all of them."

Keeping this separate from compiler.py/runner.py so each of those stays
narrowly testable (tests/test_compiler.py, tests/test_runner.py), while this
module is what orchestrator/pipeline.py and agents/adversary.py actually
import.
"""

from dataclasses import dataclass
from pathlib import Path

from execution.compiler import CompileResult, compile_cpp
from execution.resource_limits import ResourceLimits
from execution.runner import TestRunResult


@dataclass
class SandboxRunReport:
    compile_result: CompileResult
    test_results: list[TestRunResult]  # empty if compile failed


from execution.runner import run_test_case


def compile_and_run(
    source_code: str,
    run_id: str,
    workspace_dir: Path,
    test_inputs: list[str],
    limits: ResourceLimits,
) -> SandboxRunReport:
    """
    Compiles the C++ source code and runs it against a list of test inputs.
    Cleans up the compiled binary afterwards.
    """
    compile_result = compile_cpp(source_code, run_id, workspace_dir)
    if not compile_result.success or not compile_result.binary_path:
        return SandboxRunReport(
            compile_result=compile_result,
            test_results=[]
        )
        
    test_results = []
    for stdin_data in test_inputs:
        res = run_test_case(compile_result.binary_path, stdin_data, limits)
        test_results.append(res)
        
    # Clean up the compiled binary to avoid cluttering disk space
    try:
        if compile_result.binary_path.exists():
            compile_result.binary_path.unlink()
    except Exception:
        pass
        
    return SandboxRunReport(
        compile_result=compile_result,
        test_results=test_results
    )
