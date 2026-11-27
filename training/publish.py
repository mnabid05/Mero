"""Publish a finished offline training artifact without exposing partial output."""
from contextlib import contextmanager
import fcntl
from pathlib import Path
import tempfile


@contextmanager
def unpublished(destination:Path,manifest:str):
    """The writer owns a private sibling directory until a single rename commits it."""
    parent=destination.parent
    parent.mkdir(parents=True,exist_ok=True)
    # Keep this lock inode stable even after exit; two independent callers
    # cannot race to overwrite each other's finished split or model.
    with (parent/f".{destination.name}.publish.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"another writer is publishing {destination}") from exc
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        with tempfile.TemporaryDirectory(dir=parent,prefix=f".{destination.name}.stage-") as tmp:
            staging=Path(tmp)/"artifact"
            yield staging
            if not (staging/manifest).is_file():
                raise ValueError(f"artifact has no completion manifest: {manifest}")
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(destination)
            staging.rename(destination)
