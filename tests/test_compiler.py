"""
Phase 0 tests. These should be among the very first things made to pass —
validates compiler.py against known-good and known-bad C++ before any LLM
is wired in.
"""

import pytest

from execution.compiler import compile_cpp


GOOD_SOURCE = """
#include <iostream>
int main() { std::cout << "hello"; return 0; }
"""

BAD_SOURCE = """
#include <iostream>
int main() { std::cout << "missing semicolon" return 0; }
"""


def test_compile_success(tmp_path):
    result = compile_cpp(GOOD_SOURCE, run_id="test1", workspace_dir=tmp_path)
    assert result.success
    assert result.binary_path is not None
    assert result.binary_path.exists()


def test_compile_failure_returns_stderr_not_raises(tmp_path):
    result = compile_cpp(BAD_SOURCE, run_id="test2", workspace_dir=tmp_path)
    assert not result.success
    assert result.stderr  # should contain g++'s actual error text
    assert result.binary_path is None


def test_compile_timeout(tmp_path, monkeypatch):
    import execution.compiler
    from config.settings import Settings, SandboxConfig
    
    mock_settings = Settings(
        sandbox=SandboxConfig(compile_timeout_seconds=0.01)
    )
    monkeypatch.setattr(execution.compiler, "settings", mock_settings)
    
    result = compile_cpp(GOOD_SOURCE, run_id="test_timeout", workspace_dir=tmp_path)
    assert not result.success
    assert "timed out" in result.stderr or "expired" in result.stderr or "Compilation timed out" in result.stderr
    assert result.binary_path is None
