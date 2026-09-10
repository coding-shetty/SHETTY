"""One running server per data directory; prevents competing schedulers/recovery."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path


class InstanceLock:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "server.lock"
        self.fd: int | None = None

    def acquire(self) -> None:
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            os.close(fd)
            raise ValueError("SHETTY is already running with this data directory. Stop the other server or login service first.") from exc
        self.fd = fd
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))

    def release(self) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
        # Do not unlink: replacing an in-use lock inode would defeat flock.
