"""Command line entry point: python3 -m labctl [--env FILE] <command>."""

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from labctl import cards, keys, netbird, passwords
from labctl.cloudinit import render_user_data
from labctl.config import host_env_text, load_config, select_students
from labctl.firewall import default_gateways, render_gateway_sync, render_ruleset
from labctl.labs import LABS, build_labs
from labctl.plan import build_plan, vm_fields

# 這兩個值印出來就外洩了，config get 不給看。
SECRET_FIELDS = {"netbird_pat", "lab_secret"}
DERIVED_FIELDS = {"management_url", "netbird_version", "image"}


def _config(args):
    return load_config(args.env)


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
    flags = build_labs(args.out, config.lab_secret, config.cohort, args.student, args.round)
    print(f"built {len(flags)} labs for {args.student} in {args.out}")


def cmd_labs_flags(args):
    # flag 是每題固定的一句話，全班相同。
    print(json.dumps({lab.LAB_ID: lab.FLAG for lab in LABS}, ensure_ascii=False, indent=2))


def cmd_passwords_new(args):
    added = passwords.ensure(args.file, _config(args).students())
    print(f"{args.file}: added {added} passwords")


def cmd_passwords_export(args):
    sys.stdout.write(passwords.export_lines(args.file, _config(args).students()))


def cmd_keys_vm(args):
    sys.stdout.write(keys.vm_key_lines(sys.stdin.read(), _config(args).students()))


def cmd_peers_import(args):
    count = keys.import_peers(args.file, sys.stdin.read(), _config(args).students())
    print(f"{args.file}: saved {count} NetBird IPs")


def cmd_cards(args):
    config = _config(args)
    client_keys = keys.parse_setup_keys(sys.stdin.read())["clients"]
    pw = passwords.load(args.passwords)
    built = cards.build_cards(
        config.students(), keys.load_peers(args.peers), pw, client_keys, config.management_url, args.students
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


def build_parser():
    parser = argparse.ArgumentParser(prog="labctl", description="TTUSSC shell lab tooling")
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
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
