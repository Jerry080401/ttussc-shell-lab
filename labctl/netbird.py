"""NetBird management API: the class status table and the default policy lookup.

The token is NETBIRD_PAT in `.env`. It is sent only to the configured server.
"""

import json
import unicodedata
import urllib.error
import urllib.request

from labctl.plan import groups

DEFAULT_POLICY = "Default"  # NetBird 安裝時自帶的 All → All 政策


class Client:
    def __init__(self, url, token):
        if not token:
            raise ValueError("NETBIRD_PAT is empty, create a token in the NetBird dashboard and put it in .env")
        self.url = url.rstrip("/")
        self.token = token

    def get(self, path):
        request = urllib.request.Request(
            f"{self.url}/api{path}",
            headers={"Authorization": f"Token {self.token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise ValueError(f"NetBird API {path} returned HTTP {exc.code}, check NETBIRD_PAT") from None
        except urllib.error.URLError as exc:
            raise ValueError(
                f"cannot reach {self.url} ({exc.reason}), is NetBird running? (make class-start)"
            ) from None


def default_policy_id(client):
    """ID of the default All policy, or "" when it no longer exists. API errors raise.

    An empty answer makes Terraform drop the policy it took over, so only a successful lookup may return "".
    """
    policies = client.get("/policies")
    if not isinstance(policies, list):
        raise ValueError("unexpected answer from the NetBird API /policies")
    return next((p["id"] for p in policies if p.get("name") == DEFAULT_POLICY), "")


def _members(peers):
    by_group = {}
    for peer in peers:
        for group in peer.get("groups") or []:
            by_group.setdefault(group["name"], []).append(peer)
    return by_group


def _show(peer, name=True):
    mark = "●" if peer.get("connected") else "○"
    return f"{mark} {peer.get('hostname')} {peer.get('ip')}" if name else f"{mark} {peer.get('ip')}"


def _pad(text, width):
    # 中文字在終端機佔兩格，照顯示寬度補空白，欄位才對得齊。
    shown = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(width - shown, 1)


def status_table(cohort, students, peers):
    """One line per student: is the VM online, which computers joined with the student's key."""
    members = _members(peers)
    lines = [_pad("學生", 11) + _pad("VM", 19) + "學生的電腦"]
    vm_up = joined = client_up = 0
    for sid in students:
        names = groups(cohort, sid)
        vms, clients = members.get(names["vm"], []), members.get(names["client"], [])
        vm_up += any(p.get("connected") for p in vms)
        joined += bool(clients)
        client_up += any(p.get("connected") for p in clients)
        vm_text = "、".join(_show(p, name=False) for p in vms) or "（沒有 VM）"
        client_text = "、".join(_show(p) for p in clients) or "（還沒加入）"
        lines.append(_pad(sid, 11) + _pad(vm_text, 19) + client_text)
    total = len(students)
    teachers = "、".join(_show(p) for p in members.get(f"{cohort}-teachers", [])) or "（沒有）"
    lines += [
        "",
        f"VM 在線 {vm_up}/{total}　已加入電腦 {joined}/{total}　電腦在線 {client_up}/{total}",
        f"老師：{teachers}",
        "● 在線　○ 離線",
    ]
    return "\n".join(lines) + "\n"
