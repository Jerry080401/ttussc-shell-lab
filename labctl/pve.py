"""PVE LXC deployment: settings in deploy/pve/shell-lab.env and the per-student container plan.

The settings file is separate from the NetBird `.env`. Every key has a default except the
access mode's required ones; unknown keys are refused so a typo never silently keeps a default.
Pure computation, never touches a host.
"""

import ipaddress
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from labctl.cloudinit import CHINESE_PACKAGES, SWITCH_TO_GNU_COREUTILS, _locale_profile, _sshd_dropin
from labctl.config import (
    _COHORT,
    _FLAG_PREFIX,
    _LOCALE,
    _SECRET,
    _SSH_TARGET,
    _TIMEZONE,
    GUEST_IMAGES,
    MAX_STUDENTS,
    SECRET_BYTES,
    _items,
    _network,
    parse_env,
    select_students,
    student_ids,
)
from labctl.labs.lab05_organize import RM_GUARD
from labctl.plan import guest_hostname
from labctl.private import check_private

# 和 deploy/pve/shell-lab.env.example 的順序相同。
DEFAULTS = {
    "PVE_SSH": "",
    "COHORT": "shell-lab",
    "STUDENT_COUNT": "20",
    "LAB_SECRET": "",
    "FLAG_PREFIX": "flag",
    "GUEST_OS": "ubuntu-24.04",
    "GUEST_TEMPLATE": "ubuntu-24.04-standard_24.04-2_amd64.tar.zst",
    "GUEST_LOCALE": "C.UTF-8",
    "GUEST_TIMEZONE": "UTC",
    "STUDENT_SUDO": "false",
    "PROTECTED_NETWORKS": "",
    "TEMPLATE_STORAGE": "local",
    "STORAGE": "local-lvm",
    "CTID_START": "201",
    "CT_CORES": "1",
    "CT_MEMORY_MB": "1024",
    "CT_SWAP_MB": "512",
    "CT_DISK_GB": "8",
    "CT_NAMESERVER": "",
    "NAT_BRIDGE": "vmbr1",
    "NAT_SUBNET": "10.10.10.0/24",
    "ACCESS_MODE": "portforward",
}

# 每種連線方式自己的設定。只有 ACCESS_MODE 選到的那一組可以出現在設定檔裡。
# 值是 None 的必填，沒有預設值。
ACCESS_SETTINGS = {
    "portforward": {
        "PORTFORWARD_IFACE": "vmbr0",
        "PORTFORWARD_ADDRESS": "",
        "PORTFORWARD_PORT_START": "22001",
        "PORTFORWARD_SOURCES": None,
    },
}

SECRET_KEYS = ("LAB_SECRET",)
MIN_PORT = 1024

_STORAGE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,63}")
_IFACE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,14}")
_HOST = re.compile(r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9-]{1,63}")
_PRIVATE_V4 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


@dataclass(frozen=True)
class PveConfig:
    pve_ssh: str
    cohort: str
    student_count: int
    lab_secret: bytes
    flag_prefix: str
    guest_os: str
    guest_template: str
    guest_locale: str
    guest_timezone: str
    student_sudo: bool
    protected_networks: tuple
    template_storage: str
    storage: str
    ctid_start: int
    ct_cores: int
    ct_memory_mb: int
    ct_swap_mb: int
    ct_disk_gb: int
    ct_nameserver: str
    nat_bridge: str
    nat_subnet: ipaddress.IPv4Network
    access_mode: str
    access: dict

    def students(self):
        return student_ids(self.student_count)


def load_pve_config(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"{path} not found, copy it from deploy/pve/shell-lab.env.example")
    values = parse_env(path.read_text(encoding="utf-8"))
    if any(values.get(k) for k in SECRET_KEYS):
        check_private(path)
    return build_pve_config(values, str(path))


def build_pve_config(values, source="settings"):
    mode = values.get("ACCESS_MODE", DEFAULTS["ACCESS_MODE"])
    if mode not in ACCESS_SETTINGS:
        raise ValueError(f"ACCESS_MODE must be one of: {', '.join(ACCESS_SETTINGS)}")
    known = {**DEFAULTS, **ACCESS_SETTINGS[mode]}
    other = {k for m, keys in ACCESS_SETTINGS.items() if m != mode for k in keys}
    unknown = sorted(set(values) - set(known))
    if unknown:
        wrong_mode = [k for k in unknown if k in other]
        hint = f" ({', '.join(wrong_mode)} belong to another ACCESS_MODE)" if wrong_mode else ""
        raise ValueError(f"{source} has unknown settings: {', '.join(unknown)}{hint}")
    v = {k: values.get(k, default) for k, default in known.items()}
    missing = [k for k, default in known.items() if default is None and not v[k]]
    if missing:
        raise ValueError(f"{source}: these settings must be filled in: {', '.join(missing)}")
    return _build(v, mode)


def _match(key, v, pattern, expected):
    if not pattern.fullmatch(v[key]):
        raise ValueError(f"{key} must be {expected}, got {v[key]!r}")
    return v[key]


def _integer(key, v, minimum, maximum):
    if not re.fullmatch(r"[0-9]+", v[key]) or not minimum <= int(v[key]) <= maximum:
        raise ValueError(f"{key} must be an integer from {minimum} to {maximum}")
    return int(v[key])


def _ipv4(key, value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError:
        raise ValueError(f"{key} must be an IPv4 address, got {value!r}") from None


def _build(v, mode):
    if v["PVE_SSH"]:
        _match("PVE_SSH", v, _SSH_TARGET, "user@host")
    cohort = _match("COHORT", v, _COHORT, "a lowercase label, at most 24 characters")
    count = _integer("STUDENT_COUNT", v, 1, MAX_STUDENTS)
    if v["LAB_SECRET"] and not _SECRET.fullmatch(v["LAB_SECRET"]):
        raise ValueError(f"LAB_SECRET must be {SECRET_BYTES * 2} lowercase hex digits")
    flag_prefix = _match("FLAG_PREFIX", v, _FLAG_PREFIX, "letters, digits, _ or -, at most 32 characters")
    if v["GUEST_OS"] not in GUEST_IMAGES:
        raise ValueError(f"GUEST_OS must be one of: {', '.join(GUEST_IMAGES)}")
    template = v["GUEST_TEMPLATE"]
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.tar\.(zst|gz|xz)", template) or not template.startswith(v["GUEST_OS"] + "-"):
        raise ValueError(f"GUEST_TEMPLATE must be a {v['GUEST_OS']} LXC template file name, got {template!r}")
    locale = _match("GUEST_LOCALE", v, _LOCALE, "a UTF-8 locale such as zh_TW.UTF-8")
    timezone = _match("GUEST_TIMEZONE", v, _TIMEZONE, "a time zone such as Asia/Taipei")
    if v["STUDENT_SUDO"] not in ("true", "false"):
        raise ValueError("STUDENT_SUDO must be true or false")

    template_storage = _match("TEMPLATE_STORAGE", v, _STORAGE, "a PVE storage name")
    storage = _match("STORAGE", v, _STORAGE, "a PVE storage name")
    ctid_start = _integer("CTID_START", v, 100, 999_999_999 - count + 1)
    nameserver = _ipv4("CT_NAMESERVER", v["CT_NAMESERVER"]) if v["CT_NAMESERVER"] else ""

    bridge = _match("NAT_BRIDGE", v, _IFACE, "a network interface name")
    subnet = _network("NAT_SUBNET", v["NAT_SUBNET"])
    if not any(subnet.subnet_of(n) for n in _PRIVATE_V4):
        raise ValueError("NAT_SUBNET must be a private IPv4 network")
    # 第一個位址給橋接，容器從第二個開始，最後一個是廣播位址。
    if subnet.num_addresses < count + 3:
        raise ValueError(f"NAT_SUBNET is too small for {count} containers")
    protected = tuple(_network("PROTECTED_NETWORKS", n) for n in _items(v["PROTECTED_NETWORKS"]))
    for network in protected:
        if subnet.overlaps(network):
            raise ValueError(f"PROTECTED_NETWORKS overlaps NAT_SUBNET: {network}")

    return PveConfig(
        pve_ssh=v["PVE_SSH"],
        cohort=cohort,
        student_count=count,
        lab_secret=bytes.fromhex(v["LAB_SECRET"]),
        flag_prefix=flag_prefix,
        guest_os=v["GUEST_OS"],
        guest_template=template,
        guest_locale=locale,
        guest_timezone=timezone,
        student_sudo=v["STUDENT_SUDO"] == "true",
        protected_networks=protected,
        template_storage=template_storage,
        storage=storage,
        ctid_start=ctid_start,
        ct_cores=_integer("CT_CORES", v, 1, 8),
        ct_memory_mb=_integer("CT_MEMORY_MB", v, 256, 16384),
        ct_swap_mb=_integer("CT_SWAP_MB", v, 0, 16384),
        ct_disk_gb=_integer("CT_DISK_GB", v, 2, 256),
        ct_nameserver=nameserver,
        nat_bridge=bridge,
        nat_subnet=subnet,
        access_mode=mode,
        access=_ACCESS_BUILDERS[mode](v, count),
    )


def _portforward(v, count):
    iface = _match("PORTFORWARD_IFACE", v, _IFACE, "a network interface name")
    address = v["PORTFORWARD_ADDRESS"]
    if address and not _HOST.fullmatch(address):
        raise ValueError(f"PORTFORWARD_ADDRESS must be an IPv4 address or host name, got {address!r}")
    port_start = _integer("PORTFORWARD_PORT_START", v, MIN_PORT, 65536 - count)
    sources = [_network("PORTFORWARD_SOURCES", n) for n in _items(v["PORTFORWARD_SOURCES"])]
    if not sources:
        raise ValueError("PORTFORWARD_SOURCES must list at least one network, 0.0.0.0/0 allows every source")
    return {
        "iface": iface,
        "address": address,
        "port_start": port_start,
        "sources": tuple(str(n) for n in ipaddress.collapse_addresses(sources)),
    }


_ACCESS_BUILDERS = {"portforward": _portforward}


def _access_fields(config, slot):
    if config.access_mode == "portforward":
        return {"port": config.access["port_start"] + slot - 1}
    raise AssertionError(config.access_mode)


def build_pve_plan(config, selected=None):
    """Every selected student's container: CTID, host name, address and how it is reached."""
    chosen = set(select_students(config.students(), selected))
    net = config.nat_subnet
    instances = []
    for slot, sid in enumerate(config.students(), 1):
        if sid not in chosen:
            continue
        instances.append(
            {
                "student_id": sid,
                "slot": slot,
                "ctid": config.ctid_start + slot - 1,
                "hostname": guest_hostname(sid),
                "address": str(net.network_address + 1 + slot),
                "prefix": net.prefixlen,
                "gateway": str(net.network_address + 1),
                "access": _access_fields(config, slot),
            }
        )
    return {
        "cohort": config.cohort,
        "access_mode": config.access_mode,
        "students": [i["student_id"] for i in instances],
        "instances": instances,
    }


NAT_TABLE = "ip shell_lab_nat"


def render_network(config):
    """Return an nft script that atomically replaces the NAT table of the container network.

    Containers reach the internet through the host: their source address is rewritten on the way out of
    any interface other than the NAT bridge.
    """
    return (
        "#!/usr/sbin/nft -f\n"
        "# Managed by labctl (labctl pve render-network). Regenerate instead of editing.\n"
        f"table {NAT_TABLE}\n"
        f"delete table {NAT_TABLE}\n"
        "\n"
        f"table {NAT_TABLE} {{\n"
        "\tchain postrouting {\n"
        "\t\ttype nat hook postrouting priority srcnat; policy accept;\n"
        f'\t\tip saddr {config.nat_subnet} oifname != "{config.nat_bridge}" masquerade\n'
        "\t}\n"
        "}\n"
    )


ACCESS_TABLE = "ip shell_lab_access"


def render_access(config):
    """Return an nft script that atomically replaces the access mode's table."""
    if config.access_mode == "portforward":
        return _render_portforward(config)
    raise AssertionError(config.access_mode)


def _render_portforward(config):
    # 一條規則查 map：目的埠 → 容器位址 . 22。人數只影響 map 的內容，不影響規則數量。
    access = config.access
    ports = ", ".join(f"{i['access']['port']} : {i['address']} . 22" for i in build_pve_plan(config)["instances"])
    return (
        "#!/usr/sbin/nft -f\n"
        "# Managed by labctl (labctl pve render-access). Regenerate instead of editing.\n"
        f"table {ACCESS_TABLE}\n"
        f"delete table {ACCESS_TABLE}\n"
        "\n"
        f"table {ACCESS_TABLE} {{\n"
        "\tset sources {\n"
        "\t\ttype ipv4_addr\n"
        "\t\tflags interval\n"
        f"\t\telements = {{ {', '.join(access['sources'])} }}\n"
        "\t}\n"
        "\n"
        "\tmap ssh_ports {\n"
        "\t\ttype inet_service : ipv4_addr . inet_service\n"
        f"\t\telements = {{ {ports} }}\n"
        "\t}\n"
        "\n"
        "\tchain prerouting {\n"
        "\t\ttype nat hook prerouting priority dstnat; policy accept;\n"
        f'\t\tiifname "{access["iface"]}" ip saddr @sources dnat ip to tcp dport map @ssh_ports\n'
        "\t}\n"
        "}\n"
    )


# 題目用到的程式：python3（互動程式和判斷答案）、man 和 less（第 2、8 題）、file（第 7 題）、
# git（第 13 題）、vim 或 nano（第 12 題）。tar、gzip、diff、ps、find 等樣板本來就有。
GUEST_PACKAGES = ["openssh-server", "python3", "man-db", "less", "file", "git", "vim", "nano", "locales", "tzdata"]
_HEREDOC_END = "SHELL_LAB_EOF"


def _write_file(path, content):
    if _HEREDOC_END in content:
        raise ValueError(f"file content for {path} contains {_HEREDOC_END}")
    return [f"cat >{path} <<'{_HEREDOC_END}'", content.rstrip("\n"), _HEREDOC_END, f"chmod 0644 {path}"]


def render_guest_setup(config):
    """Return a bash script that sets up one container the way cloud-init sets up a VM.

    The script carries no secret: passwords are set separately over stdin.
    """
    locale = config.guest_locale
    packages = GUEST_PACKAGES + (CHINESE_PACKAGES if locale.startswith("zh_TW") else [])
    if config.student_sudo:
        packages.append("sudo")
    lines = [
        "#!/bin/bash",
        "# Generated by labctl pve render-guest-setup. Runs as root inside one container.",
        "set -euo pipefail",
        "export DEBIAN_FRONTEND=noninteractive",
        # 樣板可能排除了說明文件，拿掉之後裝的套件才會有 man page。
        "rm -f /etc/dpkg/dpkg.cfg.d/excludes",
        "apt-get update -q",
        f"apt-get install -y -q -o DPkg::Lock::Timeout=300 {' '.join(packages)}",
    ]
    if config.guest_os == "ubuntu-26.04":
        lines.append(shlex.join(SWITCH_TO_GNU_COREUTILS))
    if locale != "C.UTF-8":
        lines += [f"locale-gen {locale}", f"update-locale LANG={locale}"]
    lines += [
        f"ln -sf /usr/share/zoneinfo/{config.guest_timezone} /etc/localtime",
        f"echo {config.guest_timezone} >/etc/timezone",
        *_write_file("/etc/ssh/sshd_config.d/00-shell-lab.conf", _sshd_dropin()),
        *_write_file("/etc/profile.d/shell-lab-locale.sh", _locale_profile(locale)),
        *_write_file("/etc/profile.d/shell-lab-rm.sh", RM_GUARD),
        # 帳號先鎖住，密碼之後經 stdin 設定。
        "id student >/dev/null 2>&1 || useradd -m -s /bin/bash student",
        "usermod -aG sudo student" if config.student_sudo else "gpasswd -d student sudo >/dev/null 2>&1 || true",
        "install -d -m 0700 -o student -g student /home/student/lab",
        "/usr/sbin/sshd -t",
        "systemctl enable ssh >/dev/null 2>&1",
        "systemctl restart ssh",
    ]
    return "\n".join(lines) + "\n"


CT_FIELDS = ("ctid", "hostname", "address", "prefix", "gateway", "port")


def ct_fields(instance, fields):
    """Values of `fields` for one container, for the deploy scripts that read them with `read`."""
    flat = {k: v for k, v in instance.items() if k != "access"} | instance["access"]
    unknown = [f for f in fields if f not in flat or f not in CT_FIELDS]
    if unknown:
        raise ValueError(f"unknown container field: {', '.join(unknown)} (choose from {', '.join(CT_FIELDS)})")
    return [str(flat[f]) for f in fields]


def shell_settings(config):
    """`KEY=value` lines for the deploy scripts. LAB_SECRET is left out: only labctl needs it."""
    values = {
        "PVE_SSH": config.pve_ssh,
        "COHORT": config.cohort,
        "STUDENT_COUNT": config.student_count,
        "GUEST_OS": config.guest_os,
        "GUEST_TEMPLATE": config.guest_template,
        "GUEST_LOCALE": config.guest_locale,
        "GUEST_TIMEZONE": config.guest_timezone,
        "STUDENT_SUDO": str(config.student_sudo).lower(),
        "TEMPLATE_STORAGE": config.template_storage,
        "STORAGE": config.storage,
        "CTID_START": config.ctid_start,
        "CT_CORES": config.ct_cores,
        "CT_MEMORY_MB": config.ct_memory_mb,
        "CT_SWAP_MB": config.ct_swap_mb,
        "CT_DISK_GB": config.ct_disk_gb,
        "CT_NAMESERVER": config.ct_nameserver,
        "NAT_BRIDGE": config.nat_bridge,
        "NAT_SUBNET": config.nat_subnet,
        "NAT_GATEWAY": config.nat_subnet.network_address + 1,
        "ACCESS_MODE": config.access_mode,
    }
    for key, value in config.access.items():
        values[f"{config.access_mode.upper()}_{key.upper()}"] = ",".join(value) if isinstance(value, tuple) else value
    # 值都經過上面的檢查，只有英數字和 ._-/,:@，放進 shell 不需要引號。
    return "".join(f"{key}={value}\n" for key, value in values.items())
