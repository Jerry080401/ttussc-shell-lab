"""Functional firewall test: real packets through the generated nftables rules.

Runs tests/netlab.sh inside a brand-new network namespace (`unshare -n`, or
`unshare -Urn` when not root), so the host's own network is never touched.
Needs: unshare, nsenter, ip, ping, nft. To use an nft binary that is not on
PATH, set LABCTL_TEST_NFT (and LABCTL_TEST_NFT_LIBS for its shared libraries).
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from labctl.firewall import render_gateway_sync, render_ruleset
from labctl.plan import build_plan
from tests.helpers import REPO, example_config

NFT = os.environ.get("LABCTL_TEST_NFT") or shutil.which("nft")
NETNS = ["unshare", "-n"] if os.geteuid() == 0 else ["unshare", "-Urn"]


def netns_available():
    if not (NFT and all(shutil.which(t) for t in ("unshare", "nsenter", "ip", "ping"))):
        return False
    return subprocess.run([*NETNS, "true"], capture_output=True).returncode == 0


def nft_env():
    env = dict(os.environ, NFT=NFT)
    if os.environ.get("LABCTL_TEST_NFT_LIBS"):
        env["LD_LIBRARY_PATH"] = os.environ["LABCTL_TEST_NFT_LIBS"]
    return env


def plan(**env):
    return build_plan(example_config(**env), ["student01", "student02"])


def bridges(p):
    return [i["network"]["bridge"] for i in p["instances"]]


@unittest.skipUnless(netns_available(), "needs unshare/nsenter/ip/ping/nft and network namespaces")
class FirewallInNetnsTest(unittest.TestCase):
    def write(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".nft", delete=False, encoding="utf-8") as handle:
            handle.write(text)
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_kernel_accepts_ruleset_without_instances(self):
        # 還沒有任何 VM 時（例如宿主機剛裝好）規則也要能載入。
        path = self.write(render_ruleset([], []))
        result = subprocess.run([*NETNS, NFT, "-f", path], env=nft_env(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_isolation_behaviour(self):
        normal, protected = plan(), plan(PROTECTED_NETWORKS="203.0.113.0/24")
        br1, br2 = bridges(normal)
        files = [
            self.write(render_ruleset(bridges(normal), normal["protected_networks"])),
            self.write(render_gateway_sync(["198.51.100.1"])),
            self.write(render_gateway_sync(["198.51.100.254"])),
            self.write(render_gateway_sync([])),
            self.write(render_ruleset(bridges(protected), protected["protected_networks"])),
        ]
        env = dict(nft_env(), BR1=br1, BR2=br2)
        result = subprocess.run(
            [*NETNS, "bash", str(REPO / "tests" / "netlab.sh"), *files],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = dict(line.split() for line in result.stdout.splitlines())
        self.assertEqual(
            observed,
            {
                "vm1_internet": "reachable",
                "vm1_lan_host": "blocked",
                "vm1_gateway": "blocked",
                "vm1_vm2": "blocked",
                "vm2_vm1": "blocked",
                "vm1_host_ssh": "blocked",
                "vm1_host_uplink_ssh": "blocked",
                "vm1_other_bridge_ssh": "blocked",
                "vm1_host_dns_tcp": "reachable",
                "vm1_host_dns_udp": "reachable",
                "vm1_host_ipv6": "blocked",
                "lan_to_vm1": "blocked",
                "vm1_internet_stale_gateway": "blocked",
                "vm1_internet_after_sync": "reachable",
                "vm1_internet_no_gateway": "blocked",
                "vm1_protected_network": "blocked",
                "vm1_other_internet": "reachable",
            },
        )


if __name__ == "__main__":
    unittest.main()
