"""Student passwords: generated once, kept in local/passwords.json (mode 600)."""

import re
import secrets
from pathlib import Path

from labctl.private import read_private_json, write_private_json

# 32 個字元，沒有 0 o 1 l，唸給學生聽或抄在紙上都不會搞混。
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
PASSWORD = re.compile(r"[!-~]{8,64}")  # 鍵盤直接打得出來的 ASCII，不含空白


def generate(rng=None):
    """A new password such as `k3vd-9qwn-hx2e`."""
    rng = rng or secrets.SystemRandom()
    return "-".join("".join(rng.choice(ALPHABET) for _ in range(4)) for _ in range(3))


def load(path):
    data = read_private_json(path) if Path(path).exists() else {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object keyed by student id")
    return data


def ensure(path, students, rng=None):
    """Add a password for every student who has none. Return how many were added."""
    data = load(path)
    missing = [sid for sid in students if not data.get(sid)]
    for sid in missing:
        data[sid] = generate(rng)
    if missing:
        write_private_json(path, data)
    return len(missing)


def export_lines(path, students):
    """`sid password` lines, the input of host/set-password.sh all."""
    data = load(path)
    bad = [sid for sid in students if not (isinstance(data.get(sid), str) and PASSWORD.fullmatch(data[sid]))]
    if bad:
        raise ValueError(f"missing or malformed password for: {', '.join(bad)} (run: labctl passwords new)")
    return "".join(f"{sid} {data[sid]}\n" for sid in students)
