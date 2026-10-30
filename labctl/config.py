"""Read and validate `.env`, the single settings file for the whole project.

Every tool reads the same file: labctl directly, Make, Ansible and Terraform
through the environment. The lab host gets a copy without the NetBird token.
"""

import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path

from labctl.private import check_private

REPO = Path(__file__).resolve().parent.parent
VERSIONS_FILE = REPO / "versions.lock.json"

# 和 .env.example 的順序相同。
KEYS = (
    "COHORT",
    "STUDENT_COUNT",
    "TEACHER_DEVICES",
    "REVOKED_STUDENTS",
    "NETBIRD_DOMAIN",
    "NETBIRD_PUBLIC_IP",
    "NETBIRD_SSH",
    "ADMIN_EMAIL",
    "NETBIRD_PAT",
    "SETUP_KEY_DAYS",
    "LAB_SSH",
    "LAB_SECRET",
    "GUEST_OS",
    "GUEST_LOCALE",
    "GUEST_TIMEZONE",
    "STUDENT_SUDO",
    "VM_VCPU",
    "VM_MEMORY_MIB",
    "VM_DISK_GIB",
    "VM_NETWORK_POOL",
    "PROTECTED_NETWORKS",
)
SECRET_KEYS = ("NETBIRD_PAT", "LAB_SECRET")
OPTIONAL_KEYS = ("REVOKED_STUDENTS", "NETBIRD_PAT", "LAB_SECRET", "PROTECTED_NETWORKS")

GUEST_IMAGES = {
    "ubuntu-26.04": "images:ubuntu/26.04/cloud",
    "ubuntu-24.04": "images:ubuntu/24.04/cloud",
}
MAX_STUDENTS = 99
SUBNET_PREFIX = 28  # 每台 VM 一個 /28
SECRET_BYTES = 32

_KEY = re.compile(r"[A-Z][A-Z0-9_]*")
_UNSAFE_VALUE = re.compile(r"[\s'\"#$`\\]")  # Make 和 shell 會改寫這些字元
_COHORT = re.compile(r"[a-z][a-z0-9-]{0,23}")
_DEVICE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?")
_DOMAIN = re.compile(r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
_SSH_TARGET = re.compile(r"[A-Za-z0-9._-]+@[A-Za-z0-9.-]+")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{8,200}")
_SECRET = re.compile(r"[0-9a-f]{64}")
_LOCALE = re.compile(r"C\.UTF-8|[a-z]{2,3}_[A-Z]{2}\.UTF-8")
_TIMEZONE = re.compile(r"UTC|[A-Z][A-Za-z_]+(?:/[A-Z][A-Za-z0-9_+-]*){1,2}")
_PRIVATE_V4 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


@dataclass(frozen=True)
class Config:
    cohort: str
    student_count: int
    teacher_devices: tuple
    revoked_students: tuple
    netbird_domain: str
    netbird_public_ip: str
    netbird_ssh: str
    admin_email: str
    netbird_pat: str
    setup_key_days: int
    lab_ssh: str
    lab_secret: bytes
    guest_os: str
    guest_locale: str
    guest_timezone: str
    student_sudo: bool
    vm_vcpu: int
    vm_memory_mib: int
    vm_disk_gib: int
    vm_network_pool: ipaddress.IPv4Network
    protected_networks: tuple

    @property
    def management_url(self):
        return f"https://{self.netbird_domain}"

    @property
    def image(self):
        return GUEST_IMAGES[self.guest_os]

    @property
    def netbird_version(self):
        return netbird_version()

    def students(self):
        return student_ids(self.student_count)


def student_ids(count):
    return [f"student{n:02d}" for n in range(1, count + 1)]


def select_students(students, selected):
    """`students` in their own order, limited to `selected` (None means everyone)."""
    if selected is None:
        return list(students)
    if len(selected) != len(set(selected)) or not set(selected) <= set(students):
        raise ValueError("student selection contains duplicates or unknown ids")
    return [s for s in students if s in set(selected)]


def netbird_version():
    """NetBird client version, the same release as the pinned server."""
    return json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))["netbird_release"].removeprefix("v")


def parse_env(text):
    values = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not _KEY.fullmatch(key):
            raise ValueError(f"line {number} must look like KEY=VALUE: {raw!r}")
        if key in values:
            raise ValueError(f"{key} is set twice (line {number})")
        if _UNSAFE_VALUE.search(value):
            raise ValueError(f"{key} must not contain spaces, quotes, #, $, ` or \\ (line {number})")
        values[key] = value
    return values


def load_config(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"{path} not found, create it with: make env")
    values = parse_env(path.read_text(encoding="utf-8"))
    unknown = sorted(set(values) - set(KEYS))
    missing = [k for k in KEYS if k not in values]
    if unknown or missing:
        problems = [f"unknown: {', '.join(unknown)}"] if unknown else []
        problems += [f"missing: {', '.join(missing)}"] if missing else []
        raise ValueError(f"{path} does not match .env.example ({'; '.join(problems)})")
    if any(values[k] for k in SECRET_KEYS):
        check_private(path)
    return _build(values)


def host_env_text(path):
    """The settings file for the lab host: the same content without the NetBird token."""
    load_config(path)
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return "".join(("NETBIRD_PAT=" if line.strip().startswith("NETBIRD_PAT=") else line) + "\n" for line in lines)


def _build(v):
    empty = [k for k in KEYS if not v[k] and k not in OPTIONAL_KEYS]
    if empty:
        raise ValueError(f"these settings are empty: {', '.join(empty)}")

    cohort = _match("COHORT", v, _COHORT, "a lowercase label, at most 24 characters")
    count = _integer("STUDENT_COUNT", v, 1, MAX_STUDENTS)
    students = student_ids(count)
    devices = _items(v["TEACHER_DEVICES"])
    if not devices or len(devices) != len(set(devices)) or not all(_DEVICE.fullmatch(d) for d in devices):
        raise ValueError("TEACHER_DEVICES must list unique lowercase device names, separated by commas")
    revoked = _items(v["REVOKED_STUDENTS"])
    if not set(revoked) <= set(students) or len(revoked) != len(set(revoked)):
        raise ValueError(f"REVOKED_STUDENTS must list ids from student01 to {students[-1]}")

    domain = _match("NETBIRD_DOMAIN", v, _DOMAIN, "a lowercase domain name such as netbird.example.com")
    try:
        public_ip = str(ipaddress.IPv4Address(v["NETBIRD_PUBLIC_IP"]))
    except ValueError:
        raise ValueError("NETBIRD_PUBLIC_IP must be an IPv4 address") from None
    netbird_ssh = _match("NETBIRD_SSH", v, _SSH_TARGET, "user@host")
    email = _match("ADMIN_EMAIL", v, _EMAIL, "an email address")
    if v["NETBIRD_PAT"] and not _TOKEN.fullmatch(v["NETBIRD_PAT"]):
        raise ValueError("NETBIRD_PAT does not look like a NetBird personal access token")
    days = _integer("SETUP_KEY_DAYS", v, 1, 30)

    lab_ssh = _match("LAB_SSH", v, _SSH_TARGET, "user@host")
    if v["LAB_SECRET"] and not _SECRET.fullmatch(v["LAB_SECRET"]):
        raise ValueError(f"LAB_SECRET must be {SECRET_BYTES * 2} lowercase hex digits (make env creates one)")
    if v["GUEST_OS"] not in GUEST_IMAGES:
        raise ValueError(f"GUEST_OS must be one of: {', '.join(GUEST_IMAGES)}")
    locale = _match("GUEST_LOCALE", v, _LOCALE, "a UTF-8 locale such as zh_TW.UTF-8")
    timezone = _match("GUEST_TIMEZONE", v, _TIMEZONE, "a time zone such as Asia/Taipei")
    if v["STUDENT_SUDO"] not in ("true", "false"):
        raise ValueError("STUDENT_SUDO must be true or false")

    pool = _network("VM_NETWORK_POOL", v["VM_NETWORK_POOL"])
    if not any(pool.subnet_of(n) for n in _PRIVATE_V4) or pool.prefixlen > SUBNET_PREFIX:
        raise ValueError(f"VM_NETWORK_POOL must be a private IPv4 network of /{SUBNET_PREFIX} or larger")
    if 2 ** (SUBNET_PREFIX - pool.prefixlen) < count:
        raise ValueError(f"VM_NETWORK_POOL is too small for {count} VMs of /{SUBNET_PREFIX} each")
    protected = tuple(_network("PROTECTED_NETWORKS", n) for n in _items(v["PROTECTED_NETWORKS"]))
    for network in protected:
        if pool.overlaps(network):
            raise ValueError(f"PROTECTED_NETWORKS overlaps VM_NETWORK_POOL: {network}")

    return Config(
        cohort=cohort,
        student_count=count,
        teacher_devices=tuple(devices),
        revoked_students=tuple(revoked),
        netbird_domain=domain,
        netbird_public_ip=public_ip,
        netbird_ssh=netbird_ssh,
        admin_email=email,
        netbird_pat=v["NETBIRD_PAT"],
        setup_key_days=days,
        lab_ssh=lab_ssh,
        lab_secret=bytes.fromhex(v["LAB_SECRET"]),
        guest_os=v["GUEST_OS"],
        guest_locale=locale,
        guest_timezone=timezone,
        student_sudo=v["STUDENT_SUDO"] == "true",
        vm_vcpu=_integer("VM_VCPU", v, 1, 8),
        vm_memory_mib=_integer("VM_MEMORY_MIB", v, 1024, 16384),
        vm_disk_gib=_integer("VM_DISK_GIB", v, 8, 256),
        vm_network_pool=pool,
        protected_networks=protected,
    )


def _items(value):
    return [item for item in value.split(",") if item]


def _match(key, v, pattern, expected):
    if not pattern.fullmatch(v[key]):
        raise ValueError(f"{key} must be {expected}, got {v[key]!r}")
    return v[key]


def _integer(key, v, minimum, maximum):
    if not re.fullmatch(r"[0-9]+", v[key]) or not minimum <= int(v[key]) <= maximum:
        raise ValueError(f"{key} must be an integer from {minimum} to {maximum}")
    return int(v[key])


def _network(key, value):
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        raise ValueError(f"{key}: {value!r} is not a network such as 10.231.0.0/16") from None
    if network.version != 4:
        raise ValueError(f"{key} accepts IPv4 only (VMs have no IPv6): {network}")
    return network
