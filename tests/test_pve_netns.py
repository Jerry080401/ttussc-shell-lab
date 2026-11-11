"""Functional test of the PVE container network: real connections through the generated nftables rules.

Runs tests/pve_netlab.sh inside a brand-new network namespace, the same way as test_firewall_netns.
The bridge-level (L2) rules need a kernel with nftables bridge support; without it the test still runs
everything else and expects what an unfiltered bridge does.
"""

import subprocess
import unittest

from labctl.pve import (
    build_pve_config,
    render_access,
    render_gateway_sync_pve,
    render_isolation,
    render_l2,
    render_nat,
)
from tests.helpers import REPO, scratch_dir
from tests.test_firewall_netns import NETNS, netns_available, nft_env


def config(count):
    return build_pve_config(
        {
            "STUDENT_COUNT": str(count),
            "PORTFORWARD_SOURCES": "192.0.2.10/32",
            "PORTFORWARD_IFACE": "vmbr0",
            "PROTECTED_NETWORKS": "198.51.100.0/24",
        }
    )


def write(text):
    path = scratch_dir() / "rules.nft"
    path.write_text(text, encoding="utf-8")
    return path


def bridge_family_supported():
    rules = write(render_l2(config(2)))
    script = f"ip link add vmbr1 type bridge && nft -f {rules}"
    return subprocess.run([*NETNS, "sh", "-c", script], env=nft_env(), capture_output=True).returncode == 0


@unittest.skipUnless(netns_available(), "needs unshare/nsenter/ip/ping/nft and network namespaces")
class ContainerNetworkInNetnsTest(unittest.TestCase):
    def test_isolation_and_port_forwarding(self):
        two, one = config(2), config(1)
        l2 = bridge_family_supported()
        files = [
            write(render_nat(two) + render_isolation(two, ["10.99.0.53"])),
            write(render_l2(two)) if l2 else "-",
            write(render_access(two)),
            write(render_access(one)),
            write(render_gateway_sync_pve(["192.0.2.254"])),
            write(render_gateway_sync_pve([])),
        ]
        result = subprocess.run(
            [*NETNS, "bash", str(REPO / "tests" / "pve_netlab.sh"), *map(str, files)],
            env=nft_env(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = dict(line.split() for line in result.stdout.splitlines())
        expected = {
            "client_22001": "ct1",
            "client_22002": "ct2",
            "client_22003": "blocked",
            "stranger_22001": "blocked",
            "ct1_internet": "net",
            "ct1_host_ssh": "blocked",
            "ct1_host_webui": "blocked",
            "ct1_host_uplink_webui": "blocked",
            "ct1_lan_host": "blocked",
            "ct1_gateway": "blocked",
            "ct1_private": "blocked",
            "ct1_protected": "blocked",
            "ct1_dns": "dns",
            "ct1_private_port_53": "blocked",
            "ct1_dns_other_port": "blocked",
            "ct1_internet_no_gateway": "blocked",
            "client_22001_no_gateway": "ct1",
            "reload_client_22001": "ct1",
            "reload_ct1_internet": "net",
            "fewer_client_22001": "ct1",
            "fewer_client_22002": "blocked",
            # 只有橋接層規則擋得住：同一座橋接上的容器互連、冒用別的位址。
            "ct1_ct2": "blocked" if l2 else "ct2",
            "ct2_spoofed_source": "blocked" if l2 else "net",
        }
        self.assertEqual(observed, expected)
        if not l2:
            self.skipTest("kernel has no nftables bridge support, the L2 rules were not loaded")


if __name__ == "__main__":
    unittest.main()
