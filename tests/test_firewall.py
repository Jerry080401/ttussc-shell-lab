import unittest

from labctl.firewall import default_gateways, render_gateway_sync, render_ruleset

# 實驗主機上 VM 隔離規則的全文。改動共用的規則產生程式時，VM 這邊的規則必須逐字不變。
VM_RULESET = """\
#!/usr/sbin/nft -f
# Managed by labctl. Regenerate instead of editing.
table inet shell_lab
delete table inet shell_lab

table inet shell_lab {
\tset blocked_v4 {
\t\ttype ipv4_addr
\t\tflags interval
\t\telements = { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, \
192.0.0.0/24, 192.168.0.0/16, 198.18.0.0/15, 203.0.113.0/24, 224.0.0.0/3 }
\t}

\t# Filled by gateway sync. Empty or stale means VMs are cut off (fail-closed).
\tset uplink_gateways {
\t\ttype ipv4_addr
\t}

\tchain input {
\t\ttype filter hook input priority filter - 10; policy accept;
\t\tiifname "tl*" meta nfproto ipv6 drop
\t\tiifname "tl*" udp dport { 53, 67 } accept
\t\tiifname "tl*" tcp dport 53 accept
\t\tiifname "tl*" drop
\t}

\tchain forward {
\t\ttype filter hook forward priority filter - 10; policy accept;
\t\tiifname "tl*" meta nfproto ipv6 drop
\t\toifname "tl*" meta nfproto ipv6 drop
\t\tiifname "tl*" ip daddr @blocked_v4 drop
\t\tiifname "tl*" ip daddr @uplink_gateways drop
\t\tiifname "tl*" rt ip nexthop != @uplink_gateways drop
\t\toifname "tl*" ct state established,related accept
\t\toifname "tl*" drop
\t}
}
"""


class VmRulesetTest(unittest.TestCase):
    def test_vm_ruleset_text_is_unchanged(self):
        self.assertEqual(render_ruleset(["203.0.113.0/24"]), VM_RULESET)

    def test_vm_gateway_sync_text_is_unchanged(self):
        self.assertEqual(
            render_gateway_sync(["198.51.100.1", "198.51.100.254"]),
            "flush set inet shell_lab uplink_gateways\n"
            "add element inet shell_lab uplink_gateways { 198.51.100.1, 198.51.100.254 }\n",
        )
        self.assertEqual(render_gateway_sync([]), "flush set inet shell_lab uplink_gateways\n")


class DefaultGatewaysTest(unittest.TestCase):
    """Input is `ip -j -4 route show default` output."""

    def test_single_default_route(self):
        routes = [{"dst": "default", "gateway": "172.27.240.1", "dev": "eth0", "protocol": "kernel", "flags": []}]
        self.assertEqual(default_gateways(routes), ["172.27.240.1"])

    def test_multiple_uplinks_all_count(self):
        routes = [
            {
                "dst": "default",
                "gateway": "192.168.1.1",
                "dev": "wlan0",
                "protocol": "dhcp",
                "prefsrc": "192.168.1.23",
                "metric": 600,
                "flags": [],
            },
            {
                "dst": "default",
                "gateway": "203.0.113.1",
                "dev": "eth1",
                "protocol": "dhcp",
                "prefsrc": "203.0.113.17",
                "metric": 100,
                "flags": [],
            },
        ]
        self.assertEqual(default_gateways(routes), ["192.168.1.1", "203.0.113.1"])

    def test_device_only_default_route_is_ignored(self):
        # 例如 VPN 介面的 "default dev wg0"：沒有閘道可放行。
        routes = [{"dst": "default", "dev": "wg0", "scope": "link", "flags": []}]
        self.assertEqual(default_gateways(routes), [])

    def test_malformed_gateway_rejected(self):
        # 閘道位址會寫進 nft 腳本，格式不對就停止。
        routes = [{"dst": "default", "gateway": "1.2.3.4 } ; flush ruleset", "dev": "eth0", "flags": []}]
        with self.assertRaises(ValueError):
            default_gateways(routes)


if __name__ == "__main__":
    unittest.main()
