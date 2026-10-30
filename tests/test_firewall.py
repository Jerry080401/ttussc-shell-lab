import unittest

from labctl.firewall import default_gateways


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
