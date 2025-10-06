"""Repository-scoped locking for concurrent safety."""

import os
import subprocess
import sys
from pathlib import Path
from typing import TextIO


class LockError(Exception):
    """Raised when lock acquisition fails."""


class RepoLock:
    """
    Advisory lock for a git repository.

    Uses fcntl on Unix systems, PID file fallback on Windows.
    """

    def __init__(self, repo_root: Path):
        """
        Initialize repo lock.

        Args:
            repo_root: Repository root path
        """
        self.repo_root = repo_root
        self.lock_path = self._get_lock_path(repo_root)
        self.lock_file: TextIO | None = None
        self.acquired = False

    def _get_lock_path(self, repo_root: Path) -> Path:
        """
        Get the lock file path, handling both regular repos and worktrees.

        Args:
            repo_root: Repository root path

        Returns:
            Path to the lock file

        Raises:
            LockError: If git common directory cannot be found
        """
        try:
            # Use --git-common-dir to get the main .git directory
            # This works correctly in both regular repos and worktrees
            result = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            git_common_dir = Path(result.stdout.strip())

            # Make it absolute if it's relative
            if not git_common_dir.is_absolute():
                git_common_dir = (repo_root / git_common_dir).resolve()

            return git_common_dir / "wt.lock"
        except subprocess.CalledProcessError as e:
            raise LockError(
                f"Cannot determine git directory (are you in a git repository?): {e.stderr.strip()}"
            )
        except FileNotFoundError:
            raise LockError("git command not found")

    def acquire(self, timeout: int = 10) -> None:
        """
        Acquire the lock.

        Args:
            timeout: Timeout in seconds (unused on Unix with fcntl)

        Raises:
            LockError: If lock cannot be acquired
        """
        # Create lock file
        try:
            self.lock_file = open(self.lock_path, "a")
        except (OSError, IOError) as e:
            raise LockError(f"Cannot create lock file at {self.lock_path}: {e}")

        # Try to acquire lock
        if sys.platform == "win32":
            self._acquire_windows()
        else:
            self._acquire_unix()

        self.acquired = True

    def _acquire_unix(self) -> None:
        """Acquire lock using fcntl (Unix)."""
        import fcntl

        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError) as e:
            self.lock_file.close()
            self.lock_file = None
            raise LockError(f"Could not acquire lock (another wt process running?): {e}")

    def _acquire_windows(self) -> None:
        """Acquire lock using PID file (Windows)."""
        import time

        # Simple PID-based locking for Windows
        pid = os.getpid()
        max_attempts = 50  # 5 seconds with 100ms sleep

        for attempt in range(max_attempts):
            try:
                # Try to read existing PID
                if self.lock_path.exists():
                    content = self.lock_path.read_text().strip()
                    if content:
                        existing_pid = int(content)

                        # Check if process still exists
                        if self._process_exists_windows(existing_pid):
                            if attempt == max_attempts - 1:
                                raise LockError(
                                    f"Lock held by PID {existing_pid} (another wt process running?)"
                                )
                            time.sleep(0.1)
                            continue

                # Write our PID
                self.lock_file.write(str(pid))
                self.lock_file.flush()
                return

            except (ValueError, IOError, OSError) as e:
                if attempt == max_attempts - 1:
                    raise LockError(f"Could not acquire lock: {e}")
                time.sleep(0.1)

    def _process_exists_windows(self, pid: int) -> bool:
        """Check if process exists on Windows."""
        import ctypes

        PROCESS_QUERY_INFORMATION = 0x0400
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False

    def release(self) -> None:
        """Release the lock."""
        if not self.acquired or not self.lock_file:
            return

        # Release lock
        if sys.platform != "win32":
            import fcntl

            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            except (IOError, OSError):
                pass

        # Close and clean up
        try:
            self.lock_file.close()
        except (IOError, OSError):
            pass

        # Remove lock file on Windows
        if sys.platform == "win32":
            try:
                self.lock_path.unlink(missing_ok=True)
            except (IOError, OSError):
                pass

        self.lock_file = None
        self.acquired = False

    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False
