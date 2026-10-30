"""Connection list: every student's commands and password in one Markdown file, only for the teacher."""

import ipaddress
import re

from labctl.config import select_students
from labctl.keys import SETUP_KEY
from labctl.passwords import PASSWORD
from labctl.private import write_private

MANAGEMENT_URL = re.compile(r"https://[A-Za-z0-9.-]+(:[0-9]{1,5})?/?")

# 安裝方式和學生連線說明（docs/STUDENT_GUIDE.md）相同，每個人都一樣。
MARKDOWN = """\
# TTUSSC Linux Lab 連線指令（全班）

## 安裝 NetBird（每個人一樣，課前先裝好）

- Windows（在 Windows PowerShell 執行）
  - `curl.exe -L -o netbird-installer.exe https://pkgs.netbird.io/windows/x64`
  - `.\\netbird-installer.exe`
- macOS（依晶片選一行下載）
  - `curl -L -o netbird.pkg https://pkgs.netbird.io/macos/arm64`（Apple M 系列）
  - `curl -L -o netbird.pkg https://pkgs.netbird.io/macos/amd64`（Intel）
  - `open netbird.pkg`
- Linux
  - `curl -fsSL https://pkgs.netbird.io/install.sh | sh`

## 每個人的指令

{cards}"""

# netbird up 和 ssh 放在同一個程式碼區塊，一行一個指令，整段複製就好。
MARKDOWN_CARD = """\
- {sid}
  ```
  {netbird}
  {ssh}
  ```
  - 密碼 {password}
"""


def _is_ipv4(value):
    if not isinstance(value, str):
        return False
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        return False
    return True


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def build_cards(students, peers, passwords, setup_keys, management_url, selected=None):
    """Return {student_id: commands and password}, stopping if any selected student has missing or malformed data.

    peers: {id: {"netbird_ip", ...}}, passwords: {id: password},
    setup_keys: {id: NetBird client setup key}.
    """
    if not _matches(MANAGEMENT_URL, management_url):
        raise ValueError(f"management URL must look like https://netbird.example.com, got {management_url!r}")
    cards, problems = {}, []
    for sid in select_students(students, selected):
        peer = peers.get(sid)
        peer = peer if isinstance(peer, dict) else {}
        key, password = setup_keys.get(sid), passwords.get(sid)
        ip = peer.get("netbird_ip")
        bad = [
            name
            for name, ok in (
                ("setup key", _matches(SETUP_KEY, key)),
                ("password", _matches(PASSWORD, password)),
                ("NetBird IP", _is_ipv4(ip)),
            )
            if not ok
        ]
        if bad:
            problems.append(f"{sid} ({', '.join(bad)})")
            continue
        # 指令直接填好完整的值，不用 <…> 佔位符號（Windows PowerShell 會把 < 當成保留運算子）。
        cards[sid] = {
            "sid": sid,
            "netbird": f"netbird up --management-url {management_url} --setup-key {key}",
            "ssh": f"ssh student@{ip}",
            "password": password,
        }
    if problems:
        raise ValueError("missing or malformed card data: " + ", ".join(problems))
    return cards


def _md_code(value):
    # 用比內容更長的反引號包起來，密碼裡有 ` 也不會把格式弄壞。
    fence = "`" * (max((len(run) for run in re.findall(r"`+", value)), default=0) + 1)
    pad = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{fence}{pad}{value}{pad}{fence}"


def render_markdown(cards):
    # 指令只由驗證過的網址、註冊碼和 IP 組成，沒有反引號也沒有換行，可以直接放進程式碼區塊。
    return MARKDOWN.format(
        cards="".join(
            MARKDOWN_CARD.format(
                sid=card["sid"], netbird=card["netbird"], ssh=card["ssh"], password=_md_code(card["password"])
            )
            for card in cards
        )
    )


def write_markdown(path, cards):
    """Write the list to `path`, readable only by the teacher (mode 600), replacing it in one step."""
    write_private(path, render_markdown(cards.values()))
