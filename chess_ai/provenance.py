"""Identify executable artifacts and host settings in match reports."""
import hashlib
import platform
import shutil
from pathlib import Path
from collections.abc import Sequence


def engine_metadata(command: Sequence[str]) -> dict[str, object]:
    resolved = shutil.which(command[0]) or command[0]
    path = Path(resolved)
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"command": list(command), "executable_sha256": digest,
            "platform": platform.platform(), "machine": platform.machine(),
            "python": platform.python_version()}
