"""Functional test of the PVE access rules: real connections through the generated nftables rules.

Runs tests/pve_netlab.sh inside a brand-new network namespace, the same way as test_firewall_netns.
"""

import subprocess
import unittest

from labctl.pve import build_pve_config, render_access
from tests.helpers import REPO, scratch_dir
from tests.test_firewall_netns import NETNS, netns_available, nft_env


def rules(count):
    config = build_pve_config(
        {"STUDENT_COUNT": str(count), "PORTFORWARD_SOURCES": "192.0.2.10/32", "PORTFORWARD_IFACE": "vmbr0"}
    )
    return render_access(config)


@unittest.skipUnless(netns_available(), "needs unshare/nsenter/ip/ping/nft and network namespaces")
class PortForwardInNetnsTest(unittest.TestCase):
    def write(self, text):
        path = scratch_dir() / "access.nft"
        path.write_text(text, encoding="utf-8")
        return path

    def test_ports_reach_their_own_container_from_allowed_sources_only(self):
        files = [self.write(rules(2)), self.write(rules(1))]
        result = subprocess.run(
            [*NETNS, "bash", str(REPO / "tests" / "pve_netlab.sh"), *map(str, files)],
            env=nft_env(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = dict(line.split() for line in result.stdout.splitlines())
        self.assertEqual(
            observed,
            {
                "client_22001": "ct1",
                "client_22002": "ct2",
                "client_22003": "blocked",
                "stranger_22001": "blocked",
                "reload_client_22001": "ct1",
                "fewer_client_22001": "ct1",
                "fewer_client_22002": "blocked",
            },
        )


if __name__ == "__main__":
    unittest.main()
