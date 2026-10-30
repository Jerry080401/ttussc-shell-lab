"""Host firewall (nftables) that isolates lab VMs from each other, the host and the LAN.

Rules, applied to traffic entering from any lab bridge:
- to the host itself: only DHCP and DNS, everything else dropped.
- forwarded: dropped to private/special ranges, to configured protected networks
  and to the default gateway itself. Everything else must be routed *via* a
  known default gateway (`rt ip nexthop`), so on-link LAN hosts are unreachable
  even when the LAN uses public addresses.
- IPv6 dropped entirely. New inbound connections to VMs dropped.

The gateway set starts empty and is filled by `render_gateway_sync`. While it is
empty or stale (e.g. DHCP moved the host to another network), VMs cannot reach
anything: the design fails closed.
"""

import ipaddress

TABLE = "inet ttussc_lab"

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


def render_ruleset(bridges, protected_networks):
    """Return an nft script that atomically replaces the ttussc_lab table."""
    names = sorted(bridges)
    for name in names:
        if not (name.isascii() and name.isalnum() and 1 <= len(name) <= 15):
            raise ValueError(f"invalid bridge name: {name!r}")
    bridge_elements = "\t\telements = { " + ", ".join(f'"{n}"' for n in names) + " }\n" if names else ""
    return (
        "#!/usr/sbin/nft -f\n"
        "# Managed by labctl. Regenerate instead of editing.\n"
        f"table {TABLE}\n"
        f"delete table {TABLE}\n"
        "\n"
        f"table {TABLE} {{\n"
        "\tset lab_bridges {\n"
        "\t\ttype ifname\n"
        f"{bridge_elements}"
        "\t}\n"
        "\n"
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
        "\t\tiifname @lab_bridges meta nfproto ipv6 drop\n"
        "\t\tiifname @lab_bridges udp dport { 53, 67 } accept\n"
        "\t\tiifname @lab_bridges tcp dport 53 accept\n"
        "\t\tiifname @lab_bridges drop\n"
        "\t}\n"
        "\n"
        "\tchain forward {\n"
        "\t\ttype filter hook forward priority filter - 10; policy accept;\n"
        "\t\tiifname @lab_bridges meta nfproto ipv6 drop\n"
        "\t\toifname @lab_bridges meta nfproto ipv6 drop\n"
        "\t\tiifname @lab_bridges ip daddr @blocked_v4 drop\n"
        "\t\tiifname @lab_bridges ip daddr @uplink_gateways drop\n"
        "\t\tiifname @lab_bridges rt ip nexthop != @uplink_gateways drop\n"
        "\t\toifname @lab_bridges ct state established,related accept\n"
        "\t\toifname @lab_bridges drop\n"
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


def render_gateway_sync(gateways):
    """Return an nft script that atomically replaces the allowed uplink gateways."""
    addresses = [str(ipaddress.IPv4Address(g)) for g in gateways]
    script = f"flush set {TABLE} uplink_gateways\n"
    if addresses:
        script += f"add element {TABLE} uplink_gateways {{ {', '.join(addresses)} }}\n"
    return script
