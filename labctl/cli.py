"""Command line entry point: python3 -m labctl [--env FILE] <command>."""

import argparse
import dataclasses
import json
import subprocess
import sys
from pathlib import Path

from labctl import cards, keys, netbird, passwords
from labctl.cloudinit import render_user_data
from labctl.config import host_env_text, load_config, select_students
from labctl.firewall import default_gateways, render_gateway_sync, render_ruleset
from labctl.labs import DEFAULT_FLAG_PREFIX, LABS, build_labs, full_flag
from labctl.plan import build_plan, vm_fields
from labctl.pve import (
    build_pve_plan,
    ct_fields,
    load_pve_config,
    render_access,
    render_guest_setup,
    shell_settings,
)

# 這兩個值印出來就外洩了，config get 不給看。
SECRET_FIELDS = {"netbird_pat", "lab_secret"}
DERIVED_FIELDS = {"management_url", "netbird_version", "image"}


def _config(args):
    return load_config(args.env)


def _active(config):
    """Students who still get setup keys and connection commands (REVOKED_STUDENTS are left out)."""
    return [s for s in config.students() if s not in config.revoked_students]


def _instance(config, sid):
    return build_plan(config, [sid])["instances"][0]


def cmd_config_check(args):
    config = _config(args)
    print(f"{args.env} OK: {config.student_count} students, NetBird at {config.management_url}")


def cmd_config_get(args):
    config = _config(args)
    name = args.name
    if name in SECRET_FIELDS:
        raise ValueError(f"refusing to print {name}, read it from {args.env} yourself")
    if name not in DERIVED_FIELDS | {f.name for f in dataclasses.fields(config)}:
        raise ValueError(f"unknown setting: {name}")
    value = getattr(config, name)
    if isinstance(value, bool):
        value = str(value).lower()
    elif isinstance(value, tuple):
        value = ",".join(map(str, value))
    print(value)


def cmd_config_host_env(args):
    sys.stdout.write(host_env_text(args.env))


def cmd_students(args):
    print("\n".join(_config(args).students()))


def cmd_plan(args):
    print(json.dumps(build_plan(_config(args), args.students), ensure_ascii=False, indent=2))


def cmd_vm(args):
    print(" ".join(vm_fields(_instance(_config(args), args.student), args.fields)))


def cmd_render_cloud_init(args):
    sys.stdout.write(render_user_data(_instance(_config(args), args.student)))


def cmd_render_firewall(args):
    sys.stdout.write(render_ruleset([str(n) for n in _config(args).protected_networks]))


def cmd_render_gateway_sync(args):
    # 讀 `ip -j -4 route show default` 的輸出，只放行目前的預設閘道。沒有預設路由時清空，VM 就連不出去。
    routes = json.loads(sys.stdin.read() or "[]")
    if not isinstance(routes, list):
        raise ValueError("expected the JSON list printed by: ip -j -4 route show default")
    sys.stdout.write(render_gateway_sync(default_gateways(routes)))


def cmd_labs_build(args):
    config = _config(args)
    select_students(config.students(), [args.student])  # 不在名單上的學生直接停止
    if not config.lab_secret:
        raise ValueError("LAB_SECRET is empty, create one with: make env")
    flags = build_labs(args.out, config.lab_secret, config.cohort, args.student, args.round, config.flag_prefix)
    print(f"built {len(flags)} labs for {args.student} in {args.out}")


def cmd_labs_flags(args):
    # flag 是每題固定的一句話，全班相同。
    prefix = _config(args).flag_prefix if args.env.is_file() else DEFAULT_FLAG_PREFIX
    print(json.dumps({lab.LAB_ID: full_flag(lab, prefix) for lab in LABS}, ensure_ascii=False, indent=2))


def cmd_passwords_new(args):
    added = passwords.ensure(args.file, _config(args).students())
    print(f"{args.file}: added {added} passwords")


def cmd_passwords_export(args):
    sys.stdout.write(passwords.export_lines(args.file, _config(args).students()))


def cmd_keys_vm(args):
    sys.stdout.write(keys.vm_key_lines(sys.stdin.read(), _active(_config(args))))


def cmd_peers_import(args):
    count = keys.import_peers(args.file, sys.stdin.read(), _config(args).students())
    print(f"{args.file}: saved {count} NetBird IPs")


def cmd_cards(args):
    config = _config(args)
    client_keys = keys.parse_setup_keys(sys.stdin.read())["clients"]
    pw = passwords.load(args.passwords)
    built = cards.build_cards(
        _active(config), keys.load_peers(args.peers), pw, client_keys, config.management_url, args.students
    )
    cards.write_markdown(args.out, built)
    print(f"wrote {len(built)} students to {args.out}")


def _client(config):
    return netbird.Client(config.management_url, config.netbird_pat)


def cmd_netbird_status(args):
    config = _config(args)
    peers = _client(config).get("/peers")
    sys.stdout.write(netbird.status_table(config.cohort, config.students(), peers))


def cmd_netbird_default_policy(args):
    print(netbird.default_policy_id(_client(_config(args))))


def cmd_netbird_check(args):
    found = netbird.open_policies(_client(_config(args)))
    if found:
        raise ValueError(f"enabled policies use the All group, every student can reach every VM: {', '.join(found)}")
    print("OK: no enabled policy uses the All group")


def cmd_pve_check(args):
    config = load_pve_config(args.env)
    print(f"{args.env} OK: {config.student_count} containers, access mode {config.access_mode}")


def cmd_pve_settings(args):
    sys.stdout.write(shell_settings(load_pve_config(args.env)))


def cmd_pve_students(args):
    print("\n".join(load_pve_config(args.env).students()))


def cmd_pve_plan(args):
    print(json.dumps(build_pve_plan(load_pve_config(args.env), args.students), ensure_ascii=False, indent=2))


def cmd_pve_ct(args):
    instance = build_pve_plan(load_pve_config(args.env), [args.student])["instances"][0]
    print(" ".join(ct_fields(instance, args.fields)))


def cmd_pve_render_access(args):
    sys.stdout.write(render_access(load_pve_config(args.env)))


def cmd_pve_render_guest_setup(args):
    sys.stdout.write(render_guest_setup(load_pve_config(args.env)))


def cmd_pve_passwords_new(args):
    added = passwords.ensure(args.file, load_pve_config(args.env).students())
    print(f"{args.file}: added {added} passwords")


def cmd_pve_passwords_export(args):
    sys.stdout.write(passwords.export_lines(args.file, load_pve_config(args.env).students()))


def build_parser():
    parser = argparse.ArgumentParser(prog="labctl", description="Shell lab tooling")
    parser.add_argument("--env", default=".env", type=Path, help="settings file (default: .env)")
    commands = parser.add_subparsers(dest="command", required=True)

    def group(name, help_text):
        return commands.add_parser(name, help=help_text).add_subparsers(dest="what", required=True)

    def command(parent, name, func, help_text):
        sub = parent.add_parser(name, help=help_text)
        sub.set_defaults(func=func)
        return sub

    config = group("config", "check or read .env")
    command(config, "check", cmd_config_check, "validate every setting")
    command(config, "get", cmd_config_get, "print one setting").add_argument("name")
    command(config, "host-env", cmd_config_host_env, "print .env for the lab host (without NETBIRD_PAT)")

    command(commands, "students", cmd_students, "print every student id")
    command(commands, "plan", cmd_plan, "print the VM plan as JSON").add_argument(
        "--students", nargs="+", help="limit to these students"
    )
    vm = command(commands, "vm", cmd_vm, "print fields of one VM, separated by spaces")
    vm.add_argument("student")
    vm.add_argument("fields", nargs="+")

    render = group("render", "print generated files")
    command(render, "cloud-init", cmd_render_cloud_init, "cloud-init user-data for one VM").add_argument("student")
    command(render, "firewall", cmd_render_firewall, "nftables isolation rules for every VM")
    command(render, "gateway-sync", cmd_render_gateway_sync, "nft script for the uplink gateways (stdin: ip -j route)")

    labs = group("labs", "build lab exercises")
    build = command(labs, "build", cmd_labs_build, "create every lab for one student in an empty directory")
    build.add_argument("student")
    build.add_argument("--out", required=True, help="empty or missing directory")
    build.add_argument("--round", type=int, default=1, help="data round, bump it for fresh data")
    command(labs, "flags", cmd_labs_flags, "print each lab's flag (the answers, the same for everyone)")

    pw = group("passwords", "student passwords in local/passwords.json")
    for name, func, help_text in (
        ("new", cmd_passwords_new, "create a password for every student who has none"),
        ("export", cmd_passwords_export, "print `sid password` lines for host/set-password.sh all"),
    ):
        command(pw, name, func, help_text).add_argument("--file", default="local/passwords.json")

    key = group("keys", "setup keys from terraform output -json setup_keys (stdin)")
    command(key, "vm", cmd_keys_vm, "print `sid key` lines for host/enroll-netbird.sh all")

    peers = group("peers", "the VMs' NetBird IPs in local/peers.json")
    command(peers, "import", cmd_peers_import, "save `sid ip` lines from host/enroll-netbird.sh all").add_argument(
        "--file", default="local/peers.json"
    )

    card = command(commands, "cards", cmd_cards, "write every student's commands (stdin: terraform output)")
    card.add_argument("--peers", default="local/peers.json")
    card.add_argument("--passwords", default="local/passwords.json")
    card.add_argument("--students", nargs="+", help="limit to these students")
    card.add_argument("--out", default="local/cards.md", help="Markdown file, mode 600, replaced if it exists")

    nb = group("netbird", "ask the NetBird management API")
    command(nb, "status", cmd_netbird_status, "every student's VM and computers, online or not")
    command(nb, "default-policy", cmd_netbird_default_policy, "print the ID of the default All policy")
    command(nb, "check", cmd_netbird_check, "fail if an enabled policy still uses the All group")

    pve = group("pve", "PVE LXC deployment (--env deploy/pve/shell-lab.env)")
    command(pve, "check", cmd_pve_check, "validate every setting")
    command(pve, "settings", cmd_pve_settings, "print the settings as KEY=value lines, without LAB_SECRET")
    command(pve, "students", cmd_pve_students, "print every student id")
    command(pve, "plan", cmd_pve_plan, "print the container plan as JSON").add_argument(
        "--students", nargs="+", help="limit to these students"
    )
    ct = command(pve, "ct", cmd_pve_ct, "print fields of one container, separated by spaces")
    ct.add_argument("student")
    ct.add_argument("fields", nargs="+")
    command(pve, "render-access", cmd_pve_render_access, "nftables rules of the access mode")
    command(pve, "render-guest-setup", cmd_pve_render_guest_setup, "bash script that sets up one container")
    for name, func, help_text in (
        ("passwords-new", cmd_pve_passwords_new, "create a password for every student who has none"),
        ("passwords-export", cmd_pve_passwords_export, "print `sid password` lines for shell-lab-setup.sh"),
    ):
        command(pve, name, func, help_text).add_argument("--file", default="local/pve-passwords.json")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
