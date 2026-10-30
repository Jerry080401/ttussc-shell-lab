"""Files only the teacher may read: permission check and atomic replace."""

import json
import os
import tempfile
from pathlib import Path


def check_private(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError(f"{path} can be read by other users, run: chmod 600 {path}")


def read_private_json(path):
    check_private(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_private(path, text):
    """Replace `path` with `text` in one step, mode 600. A half-written file never takes its place."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")  # mkstemp 建立的檔案是 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def write_private_json(path, data):
    write_private(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
