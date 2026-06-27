"""Track and clean up spawned CLI subprocesses.

This is a safety net for cases where the server is interrupted (Ctrl+C) and the
FastAPI lifespan cleanup doesn't run to completion. We only track processes we
spawn so we don't accidentally kill unrelated system processes.

On Windows, uses a Win32 Job Object with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``
for kernel-guaranteed process tree termination. Falls back to ``taskkill`` when
the Job Object API is unavailable or a process is already assigned to a job.
"""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import threading

from loguru import logger

_lock = threading.Lock()
_pids: set[int] = set()
_atexit_registered = False


# =============================================================================
# Windows Job Object — kernel-guaranteed process tree termination
# =============================================================================

_WINDOWS_JOB_MANAGER: WindowsJobManager | None = None


class WindowsJobManager:
    """Wrap a Win32 Job Object that terminates all child processes on handle close.

    Uses ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` so the OS guarantees every
    assigned process and its descendants are killed when the job handle is
    closed (e.g. at process exit or explicit ``close()``).

    Falls back to ``taskkill`` for individual processes when the job API
    cannot be used (process already in another job, insufficient permissions).
    """

    def __init__(self) -> None:
        self._job_handle: int | None = None
        self._available: bool = False
        self._init_error: str | None = None
        self._setup()

    def _setup(self) -> None:
        """Create the job object and enable kill-on-close.

        This is intentionally not ``__init__`` so we can swallow ctypes import
        errors gracefully on platforms where ``ctypes.wintypes`` is absent
        (e.g. alternative Python builds with ctypes but no Windows types).
        """
        if os.name != "nt":
            self._init_error = "not Windows"
            return

        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            self._init_error = "ctypes not available"
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # --- Complete Win32 structure definitions for JOBOBJECT_EXTENDED_LIMIT_INFORMATION ---
        # These match the MSDN struct exactly so SetInformationJobObject receives
        # the correct buffer size; all unset fields default to zero.

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("ChildProcessRateControl", wintypes.DWORD),
                ("Flags", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            # ``wintypes`` does not export ``ULONGLONG``; use the equivalent ctypes type.
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("LimitViolationInfo", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ]

        # --- Declare Win32 API functions ---

        CreateJobObjectW = kernel32.CreateJobObjectW
        CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        CreateJobObjectW.restype = wintypes.HANDLE

        CloseHandle = kernel32.CloseHandle
        CloseHandle.argtypes = [wintypes.HANDLE]
        CloseHandle.restype = wintypes.BOOL

        SetInformationJobObject = kernel32.SetInformationJobObject
        SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,  # JOBOBJECTINFOCLASS
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        SetInformationJobObject.restype = wintypes.BOOL

        OpenProcess = kernel32.OpenProcess
        OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        OpenProcess.restype = wintypes.HANDLE

        AssignProcessToJobObject = kernel32.AssignProcessToJobObject
        AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        AssignProcessToJobObject.restype = wintypes.BOOL

        # Store references so they aren't garbage-collected.
        self._CloseHandle = CloseHandle
        self._OpenProcess = OpenProcess
        self._AssignProcessToJobObject = AssignProcessToJobObject

        # --- Create the job object ---

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        JOBOBJECTINFOCLASS_EXTLIMITED = 9  # JobObjectExtendedLimitInformation

        job_handle = CreateJobObjectW(None, None)  # unnamed job object
        if not job_handle:
            self._init_error = (
                f"CreateJobObject failed: last_error={ctypes.get_last_error()}"
            )
            return

        # Build the extended limit info structure with only LimitFlags set.
        # ctypes zero-initializes all other fields, matching the Win32 convention
        # of leaving unused limit fields at 0.
        limit_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limit_info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        result = SetInformationJobObject(
            job_handle,
            JOBOBJECTINFOCLASS_EXTLIMITED,
            ctypes.byref(limit_info),
            ctypes.sizeof(limit_info),
        )
        if not result:
            CloseHandle(job_handle)
            self._init_error = (
                f"SetInformationJobObject failed: last_error={ctypes.get_last_error()}"
            )
            return

        self._job_handle = job_handle
        self._available = True
        self._PROCESS_SET_QUOTA = 0x0100

    def assign(self, pid: int) -> bool:
        """Assign a process to the job object.

        Returns ``True`` on success, ``False`` when the process cannot be
        assigned (caller should fall back to ``taskkill`` / ``os.kill``).
        """
        if not self._available or self._job_handle is None:
            return False
        try:
            handle = self._OpenProcess(self._PROCESS_SET_QUOTA, False, pid)
            if not handle:
                return False
            try:
                return bool(self._AssignProcessToJobObject(self._job_handle, handle))
            finally:
                self._CloseHandle(handle)
        except Exception:
            return False

    def close(self) -> None:
        """Close the job handle, killing all assigned processes.

        Safe to call multiple times. After closing, new processes can no longer
        be assigned to this job.
        """
        if self._job_handle is not None:
            try:
                self._CloseHandle(self._job_handle)
            except Exception:
                pass
            finally:
                self._job_handle = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> str | None:
        return self._init_error


def _get_windows_job_manager() -> WindowsJobManager:
    """Return the module-level Windows Job Object manager (lazy init)."""
    global _WINDOWS_JOB_MANAGER
    if _WINDOWS_JOB_MANAGER is None:
        _WINDOWS_JOB_MANAGER = WindowsJobManager()
        if not _WINDOWS_JOB_MANAGER.available:
            logger.debug(
                "Windows Job Object unavailable ({}); fallback to taskkill",
                _WINDOWS_JOB_MANAGER.init_error or "unknown",
            )
    return _WINDOWS_JOB_MANAGER


def ensure_atexit_registered() -> None:
    global _atexit_registered
    with _lock:
        if _atexit_registered:
            return
        atexit.register(kill_all_best_effort)
        _atexit_registered = True


def register_pid(pid: int) -> None:
    if not pid:
        return
    ensure_atexit_registered()
    if os.name == "nt":
        # Best-effort assign to Job Object so child processes are cleaned up
        # automatically when the handle closes. Failure is non-fatal; taskkill
        # remains as the individual-cleanup fallback.
        job = _get_windows_job_manager()
        if job.available:
            job.assign(pid)
    with _lock:
        _pids.add(int(pid))


def unregister_pid(pid: int) -> None:
    if not pid:
        return
    with _lock:
        _pids.discard(int(pid))


def kill_pid_tree_best_effort(pid: int) -> None:
    """Kill a tracked process and its children where the platform supports it."""
    if not pid:
        return
    if os.name == "nt":
        try:
            # /T kills child processes, /F forces termination.
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception as e:
            logger.debug("process_registry: taskkill failed pid=%s: %s", pid, e)
        return

    # Best-effort fallback for non-Windows.
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception as e:
        logger.debug("process_registry: terminate failed pid=%s: %s", pid, e)


def kill_all_best_effort() -> None:
    """Kill any still-running registered pids (best-effort).

    On Windows, closing the Job Object handle kills all assigned process
    trees automatically via ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``. The
    explicit pid-by-pid fallback handles legacy pids that were registered
    before the Job Object was available or could not be assigned.
    """
    with _lock:
        pids = list(_pids)
        _pids.clear()

    for pid in pids:
        kill_pid_tree_best_effort(pid)
