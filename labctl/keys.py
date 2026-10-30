"""Setup keys from `terraform output -json setup_keys`, and the VMs' NetBird IPs in local/peers.json."""

import ipaddress
import json
import re
from pathlib import Path

from labctl.private import write_private_json

SETUP_KEY = re.compile(r"[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}")


def parse_setup_keys(text):
    """{"clients": {...}, "vms": {...}, "teachers": {...}} from the Terraform output."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ("clients", "vms")):
        raise ValueError("expected the JSON printed by: terraform output -json setup_keys")
    return data


def vm_key_lines(text, students):
    """`sid key` lines for every student's VM, the input of host/enroll-netbird.sh all."""
    keys = parse_setup_keys(text)["vms"]
    bad = [sid for sid in students if not (isinstance(keys.get(sid), str) and SETUP_KEY.fullmatch(keys[sid]))]
    if bad:
        raise ValueError(f"no VM setup key for: {', '.join(bad)} (run: make keys)")
    return "".join(f"{sid} {keys[sid]}\n" for sid in students)


def load_peers(path):
    if not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object keyed by student id")
    return data


def import_peers(path, text, students):
    """Merge `sid ip` lines (output of host/enroll-netbird.sh all) into peers.json. Return the count."""
    data = load_peers(path)
    count = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0] not in students:
            raise ValueError(f"expected `studentNN ip`, got {line!r}")
        sid, ip = parts
        try:
            ipaddress.IPv4Address(ip)
        except ValueError:
            raise ValueError(f"{sid}: {ip!r} is not an IPv4 address") from None
        entry = data.get(sid) if isinstance(data.get(sid), dict) else {}
        data[sid] = {**entry, "netbird_ip": ip}
        count += 1
    write_private_json(path, data)
    return count
