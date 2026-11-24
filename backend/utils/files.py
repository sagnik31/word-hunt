import os
import time
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write text so that a crash or Ctrl+C at any moment leaves either the
    old file or the new one, never half of either."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    for wait in (0.1, 0.5, 2.0, None):
        try:
            tmp.replace(path)
            return
        except PermissionError:  # Windows: another program has the file open
            if wait is None:
                raise
            time.sleep(wait)
