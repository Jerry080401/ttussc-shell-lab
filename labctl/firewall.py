"""Host firewall (nftables) that isolates lab VMs from each other, the host and the LAN.

Rules, applied to traffic entering from any lab bridge (every interface named tl*):
- to the host itself: only DHCP and DNS, everything else dropped.
- forwarded: dropped to private/special ranges, to configured protected networks
  and to the default gateway itself. Everything else must be routed *via* a
  known default gateway (`rt ip nexthop`), so on-link LAN hosts are unreachable
  even when the LAN uses public addresses.
- IPv6 dropped entirely. New inbound connections to VMs dropped, except, when
  asked for, SSH that the host port-forwards to a guest (PVE deployment).

The lab host matches its tl* bridges; the PVE deployment uses the same rules in
its own table on its NAT bridge.

The gateway set starts empty and is filled by `render_gateway_sync`. While it is
empty or stale (e.g. DHCP moved the host to another network), VMs cannot reach
anything: the design fails closed.
"""

import ipaddress

TABLE = "inet shell_lab"
BRIDGE_PREFIX = "tl"  # 每台 VM 的 bridge 都叫 tl 加 10 位十六進位，見 plan.bridge_name

# 私有、共享、保留與特殊用途位址，VM 一律不能直接連。
BLOCKED_V4 = [
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.0.0.0/24",
    "192.168.0.0/16",
    "198.18.0.0/15",
    "224.0.0.0/4",
    "240.0.0.0/4",
]


def _v4_set(networks):
    collapsed = ipaddress.collapse_addresses(ipaddress.ip_network(n, strict=True) for n in networks)
    return ", ".join(str(n) for n in collapsed)


def render_ruleset(protected_networks, table=TABLE, interfaces=f"{BRIDGE_PREFIX}*", ssh_in=False, dns_servers=()):
    """Return an nft script that atomically replaces `table`.

    On the lab host the rules match every interface named tl*, not the bridges of today's class
    list, so a VM left over after STUDENT_COUNT shrinks is still isolated. The PVE deployment
    passes its own table and NAT bridge, and `ssh_in` to let port-forwarded SSH reach the guests.
    """
    lab = f'"{interfaces}"'
    # 轉發進來的 SSH：去程只放行 22 埠，回程（使用者可能在私有或同一個網段）不受下面的目的地限制。
    replies = f"\t\tiifname {lab} ct status dnat accept\n" if ssh_in else ""
    inbound = f"\t\toifname {lab} ct status dnat tcp dport 22 accept\n" if ssh_in else ""
    # 主機上沒有給客體用的 DNS 時（PVE 版），只放行指定的 DNS 伺服器的 53 埠，其他目的地照樣限制。
    dns = ""
    if dns_servers:
        servers = ", ".join(str(ipaddress.IPv4Address(s)) for s in dns_servers)
        dns = "".join(
            f"\t\tiifname {lab} ip daddr {{ {servers} }} {proto} dport 53 accept\n" for proto in ("udp", "tcp")
        )
    return (
        "#!/usr/sbin/nft -f\n"
        "# Managed by labctl. Regenerate instead of editing.\n"
        f"table {table}\n"
        f"delete table {table}\n"
        "\n"
        f"table {table} {{\n"
        "\tset blocked_v4 {\n"
        "\t\ttype ipv4_addr\n"
        "\t\tflags interval\n"
        f"\t\telements = {{ {_v4_set(BLOCKED_V4 + list(protected_networks))} }}\n"
        "\t}\n"
        "\n"
        "\t# Filled by gateway sync. Empty or stale means VMs are cut off (fail-closed).\n"
        "\tset uplink_gateways {\n"
        "\t\ttype ipv4_addr\n"
        "\t}\n"
        "\n"
        "\tchain input {\n"
        "\t\ttype filter hook input priority filter - 10; policy accept;\n"
        f"\t\tiifname {lab} meta nfproto ipv6 drop\n"
        f"\t\tiifname {lab} udp dport {{ 53, 67 }} accept\n"
        f"\t\tiifname {lab} tcp dport 53 accept\n"
        f"\t\tiifname {lab} drop\n"
        "\t}\n"
        "\n"
        "\tchain forward {\n"
        "\t\ttype filter hook forward priority filter - 10; policy accept;\n"
        f"\t\tiifname {lab} meta nfproto ipv6 drop\n"
        f"\t\toifname {lab} meta nfproto ipv6 drop\n"
        f"{replies}"
        f"{dns}"
        f"\t\tiifname {lab} ip daddr @blocked_v4 drop\n"
        f"\t\tiifname {lab} ip daddr @uplink_gateways drop\n"
        f"\t\tiifname {lab} rt ip nexthop != @uplink_gateways drop\n"
        f"\t\toifname {lab} ct state established,related accept\n"
        f"{inbound}"
        f"\t\toifname {lab} drop\n"
        "\t}\n"
        "}\n"
    )


def default_gateways(routes):
    """Gateways from `ip -j -4 route show default` output, sorted and validated."""
    gateways = set()
    for route in routes:
        if "gateway" in route:
            gateways.add(ipaddress.IPv4Address(route["gateway"]))  # ValueError on garbage
    return [str(g) for g in sorted(gateways)]


def render_gateway_sync(gateways, table=TABLE):
    """Return an nft script that atomically replaces the allowed uplink gateways."""
    addresses = [str(ipaddress.IPv4Address(g)) for g in gateways]
    script = f"flush set {table} uplink_gateways\n"
    if addresses:
        script += f"add element {table} uplink_gateways {{ {', '.join(addresses)} }}\n"
    return script
