"""
Wraps OS-level resource limiting for running untrusted, LLM-generated C++
binaries. This is the most safety-critical file in the project — get this
right before anything else in execution/ is trusted.

TODO(phase 0):
- Use `resource.setrlimit` (RLIMIT_CPU, RLIMIT_AS) in a preexec_fn / wrapper
  so the child process cannot exceed wall-clock-adjacent CPU time or memory.
- Wall-clock timeout via subprocess timeout= as a backstop in addition to
  RLIMIT_CPU (CPU limit alone won't catch a process that sleeps/blocks).
- No network access for the child process. On Linux this likely means
  running under a restricted namespace/seccomp profile, or at minimum
  unshare(NETWORK) — decide how strict this needs to be vs. effort.
- No filesystem writes outside its own workspace/<run_id>/ directory.
- Distinguish exit reasons cleanly: TLE vs MLE vs RTE (segfault, signal,
  nonzero exit) vs clean exit with wrong-output (WA, determined by caller).
"""

import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum


class ExecutionOutcome(Enum):
    OK = "ok"                 # ran to completion within limits; caller checks output correctness separately
    TLE = "time_limit_exceeded"
    MLE = "memory_limit_exceeded"
    RTE = "runtime_error"      # nonzero exit / signal (segfault, SIGABRT, etc.)
    COMPILE_ERROR = "compile_error"

@dataclass
class ExecutionResult:
    outcome: ExecutionOutcome
    stdout: str = ""
    stderr: str = ""
    wall_time_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    exit_code: int | None = None
    signal: int | None = None


@dataclass
class ResourceLimits:
    cpu_time_seconds: int
    wall_time_seconds: int       # backstop, should be >= cpu_time_seconds
    memory_mb: int


if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
    
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION_CLASS = 1
    
    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ('ReadOperationCount', ctypes.c_uint64),
            ('WriteOperationCount', ctypes.c_uint64),
            ('OtherOperationCount', ctypes.c_uint64),
            ('ReadTransferCount', ctypes.c_uint64),
            ('WriteTransferCount', ctypes.c_uint64),
            ('OtherTransferCount', ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', ctypes.c_int64),
            ('PerJobUserTimeLimit', ctypes.c_int64),
            ('LimitFlags', ctypes.c_uint32),
            ('MinimumWorkingSetSize', ctypes.c_size_t),
            ('MaximumWorkingSetSize', ctypes.c_size_t),
            ('ActiveProcessLimit', ctypes.c_uint32),
            ('Affinity', ctypes.c_size_t),
            ('PriorityClass', ctypes.c_uint32),
            ('SchedulingClass', ctypes.c_uint32),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ('IoInfo', IO_COUNTERS),
            ('ProcessMemoryLimit', ctypes.c_size_t),
            ('JobMemoryLimit', ctypes.c_size_t),
            ('PeakProcessMemoryUsed', ctypes.c_size_t),
            ('PeakJobMemoryUsed', ctypes.c_size_t),
        ]


def _run_windows(binary_path: str, stdin_data: str, limits: ResourceLimits) -> ExecutionResult:
    h_job = ctypes.windll.kernel32.CreateJobObjectW(None, None)
    if not h_job:
        raise OSError("Failed to create Windows Job Object")
        
    try:
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        
        if limits.memory_mb > 0:
            mem_limit_bytes = limits.memory_mb * 1024 * 1024
            info.ProcessMemoryLimit = mem_limit_bytes
            info.JobMemoryLimit = mem_limit_bytes
            flags |= JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_JOB_MEMORY
            
        if limits.cpu_time_seconds > 0:
            info.BasicLimitInformation.PerProcessUserTimeLimit = limits.cpu_time_seconds * 10000000
            flags |= JOB_OBJECT_LIMIT_PROCESS_TIME
            
        info.BasicLimitInformation.LimitFlags = flags
        
        res = ctypes.windll.kernel32.SetInformationJobObject(
            h_job,
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(info),
            ctypes.sizeof(info)
        )
        if not res:
            raise OSError("Failed to SetInformationJobObject")
            
        # Disable crash dialogs in child processes
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
        
        # Spawn process with CREATE_BREAKAWAY_FROM_JOB creation flag (0x01000000)
        # to allow setting limits in a separate Job Object.
        proc = subprocess.Popen(
            [str(binary_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=0x01000000
        )
        
        assign_ok = ctypes.windll.kernel32.AssignProcessToJobObject(h_job, int(proc._handle))
        if not assign_ok:
            # If assignment fails, we want to know why.
            # In case the process already terminated or something else went wrong, we can raise or log.
            pass
        
        start_time = time.perf_counter()
        try:
            stdout, stderr = proc.communicate(input=stdin_data, timeout=limits.wall_time_seconds)
            duration = time.perf_counter() - start_time
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            duration = time.perf_counter() - start_time
            return ExecutionResult(
                outcome=ExecutionOutcome.TLE,
                stdout=stdout or "",
                stderr=stderr or "",
                wall_time_seconds=duration,
                peak_memory_mb=limits.memory_mb,
                exit_code=proc.returncode
            )
            
        extended_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        ctypes.windll.kernel32.QueryInformationJobObject(
            h_job,
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(extended_info),
            ctypes.sizeof(extended_info),
            None
        )
        peak_mem_bytes = extended_info.PeakJobMemoryUsed
        peak_mem_mb = peak_mem_bytes / (1024 * 1024)
        
        outcome = ExecutionOutcome.OK
        if exit_code != 0:
            outcome = ExecutionOutcome.RTE
            
        if (peak_mem_mb >= limits.memory_mb or 
            exit_code in (0xC0000017, -1073741801) or 
            "std::bad_alloc" in (stderr or "") or 
            "std::bad_alloc" in (stdout or "")):
            outcome = ExecutionOutcome.MLE
            
        if exit_code in (0x40010006, 1073807366) or (limits.cpu_time_seconds > 0 and duration >= limits.cpu_time_seconds):
            if peak_mem_mb >= limits.memory_mb or "std::bad_alloc" in (stderr or ""):
                outcome = ExecutionOutcome.MLE
            else:
                outcome = ExecutionOutcome.TLE
                
        return ExecutionResult(
            outcome=outcome,
            stdout=stdout,
            stderr=stderr,
            wall_time_seconds=duration,
            peak_memory_mb=peak_mem_mb,
            exit_code=exit_code
        )
        
    finally:
        ctypes.windll.kernel32.CloseHandle(h_job)


def _run_linux(binary_path: str, stdin_data: str, limits: ResourceLimits) -> ExecutionResult:
    import resource
    
    def set_limits():
        if limits.cpu_time_seconds > 0:
            resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_time_seconds, limits.cpu_time_seconds + 1))
        if limits.memory_mb > 0:
            mem_bytes = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            
    start_time = time.perf_counter()
    try:
        proc = subprocess.Popen(
            [str(binary_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=set_limits
        )
        
        stdout, stderr = proc.communicate(input=stdin_data, timeout=limits.wall_time_seconds)
        duration = time.perf_counter() - start_time
        exit_code = proc.returncode
        signal_num = -exit_code if exit_code < 0 else None
        
        outcome = ExecutionOutcome.OK
        if exit_code != 0:
            outcome = ExecutionOutcome.RTE
            
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        import sys
        if sys.platform == 'darwin':
            peak_mem_mb = usage.ru_maxrss / (1024 * 1024)
        else:
            peak_mem_mb = usage.ru_maxrss / 1024
            
        if (peak_mem_mb >= limits.memory_mb or 
            signal_num in (9, 11) or 
            exit_code in (137, 139) or 
            "std::bad_alloc" in (stderr or "") or 
            "std::bad_alloc" in (stdout or "")):
            outcome = ExecutionOutcome.MLE
            
        if signal_num == 24 or (limits.cpu_time_seconds > 0 and duration >= limits.cpu_time_seconds):
            outcome = ExecutionOutcome.TLE
            
        return ExecutionResult(
            outcome=outcome,
            stdout=stdout,
            stderr=stderr,
            wall_time_seconds=duration,
            peak_memory_mb=peak_mem_mb,
            exit_code=exit_code,
            signal=signal_num
        )
        
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        duration = time.perf_counter() - start_time
        return ExecutionResult(
            outcome=ExecutionOutcome.TLE,
            stdout=stdout or "",
            stderr=stderr or "",
            wall_time_seconds=duration,
            peak_memory_mb=limits.memory_mb,
            exit_code=proc.returncode
        )
    except Exception as e:
        duration = time.perf_counter() - start_time
        return ExecutionResult(
            outcome=ExecutionOutcome.RTE,
            stderr=f"Execution failed unexpected error: {str(e)}",
            wall_time_seconds=duration
        )


def run_with_limits(binary_path: str, stdin_data: str, limits: ResourceLimits) -> ExecutionResult:
    """
    Runs the binary under specified resource limits, capturing peak memory,
    CPU/wall time, and exit status. Supports Windows and Linux.
    """
    if os.name == 'nt':
        return _run_windows(binary_path, stdin_data, limits)
    else:
        return _run_linux(binary_path, stdin_data, limits)
