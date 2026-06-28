"""
Handles g++ invocation and compile-error parsing.

TODO(phase 0):
- Write source to workspace/<run_id>/solution.cpp
- Invoke: g++ -O2 -std=c++17 -Wall -Wextra -o <binary> solution.cpp
  (consider -fsanitize=address,undefined for an optional stricter pass —
  useful for the Adversary's RTE hunting, but adds overhead; maybe a
  separate "sanitized build" used only when chasing a suspected memory bug
  rather than every run.)
- Capture stderr on failure, return structured CompileResult rather than
  raising — the Architect needs the raw compiler error text to fix its code.
- Enforce its own timeout (CPP_COMPILE_TIMEOUT_SECONDS) — pathological
  template code can make g++ itself hang/balloon.
"""


import subprocess
import time
import os
from dataclasses import dataclass
from pathlib import Path
from config.settings import settings


@dataclass
class CompileResult:
    success: bool
    binary_path: Path | None
    stderr: str = ""
    duration_seconds: float = 0.0


def compile_cpp(source_code: str, run_id: str, workspace_dir: Path) -> CompileResult:
    """
    Writes source_code to workspace_dir / run_id / "solution.cpp", and compiles it.
    Uses g++ with flags -O2 -std=c++17 -Wall -Wextra.
    Enforces a compiler timeout and captures stderr on failure.
    """
    run_dir = workspace_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    source_path = run_dir / "solution.cpp"
    source_path.write_text(source_code, encoding="utf-8")
    
    if os.name == "nt":
        binary_path = run_dir / "solution.exe"
    else:
        binary_path = run_dir / "solution"
        
    cmd = [
        "g++",
        "-O2",
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-o",
        str(binary_path),
        str(source_path)
    ]
    
    timeout = settings.sandbox.compile_timeout_seconds
    
    start_time = time.perf_counter()
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(run_dir)
        )
        duration = time.perf_counter() - start_time
        
        if res.returncode == 0:
            return CompileResult(
                success=True,
                binary_path=binary_path,
                stderr=res.stderr,
                duration_seconds=duration
            )
        else:
            return CompileResult(
                success=False,
                binary_path=None,
                stderr=res.stderr,
                duration_seconds=duration
            )
            
    except subprocess.TimeoutExpired as e:
        duration = time.perf_counter() - start_time
        stderr = f"Compilation timed out after {timeout} seconds."
        if e.stderr:
            if isinstance(e.stderr, bytes):
                stderr += "\n" + e.stderr.decode("utf-8", errors="ignore")
            else:
                stderr += "\n" + str(e.stderr)
        return CompileResult(
            success=False,
            binary_path=None,
            stderr=stderr,
            duration_seconds=duration
        )
    except Exception as e:
        duration = time.perf_counter() - start_time
        return CompileResult(
            success=False,
            binary_path=None,
            stderr=f"Compilation failed with unexpected error: {str(e)}",
            duration_seconds=duration
        )
