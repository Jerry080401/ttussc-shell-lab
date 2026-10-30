"""Test-only helpers."""

import atexit
import shutil
import tempfile
from pathlib import Path

from labctl.config import load_config

REPO = Path(__file__).resolve().parent.parent
EXAMPLE_ENV = REPO / ".env.example"
SECRET_HEX = "ab" * 32


def scratch_dir():
    """A temporary directory removed when the test run ends (one lab build is about 30 MB)."""
    path = Path(tempfile.mkdtemp(prefix="labctl-test-"))
    atexit.register(shutil.rmtree, path, True)
    return path


def write_env(mode=0o600, **overrides):
    """Write .env.example with `KEY=value` overrides and return the path. Unknown keys are appended."""
    lines = []
    for line in EXAMPLE_ENV.read_text(encoding="utf-8").splitlines():
        key = line.partition("=")[0]
        lines.append(f"{key}={overrides.pop(key)}" if key in overrides else line)
    lines += [f"{key}={value}" for key, value in overrides.items()]
    path = scratch_dir() / ".env"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(mode)
    return path


def example_config(**overrides):
    return load_config(write_env(**overrides))
