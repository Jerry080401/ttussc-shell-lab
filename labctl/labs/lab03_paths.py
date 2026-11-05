"""Lab 03: absolute vs relative paths and the current working directory."""

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "03-paths"
TITLE = "送信到樹洞"
FLAG = "absolute_paths_never_get_lost"

README = """\
# 03 送信到樹洞

小壹請你把一封信投進森林裡的樹洞信箱 `mailbox`。小壹只記得信箱在 `forest/` 裡面，確切的位置要你自己去找。

郵差有個規矩：**信要站在郵局 `post-office/` 寄出，而且要寫完整地址（絕對路徑）**，信箱才會收。

## 你要做的事

1. 在森林裡到處走走，找到信箱，記下它的完整位置。
2. 走到郵局，用完整地址呼叫信箱。

## 提示

- 路上遇到的東西都可以用 `cat` 看看。
- 打出程式的路徑就能執行它：`./check` 是相對路徑的寫法，`/usr/bin/ls` 是絕對路徑的寫法。
- `pwd` 會顯示你現在所在的完整路徑。
- 絕對路徑從 `/` 開始，不管你現在在哪裡都指向同一個地方。相對路徑從「你現在的位置」開始算。
- `~` 會被 shell 展開成你的家目錄 `/home/student`，所以 `~/lab/...` 也算絕對路徑。
- `cd ..` 回到上一層，`cd -` 回到上一個去過的地方，`cd ~/lab/03-paths` 回到這題的起點。
- 按 `Tab` 可以自動補完檔名和路徑，長路徑不用整個打。
"""

MAILBOX = r'''#!/usr/bin/env python3
"""森林裡的樹洞信箱：只收從郵局寄出、寫完整地址的信。"""
import hashlib
import os
import sys

SALT = "@SALT@"
SEALED_FLAG = "@SEALED@"
PICTURE = @PICTURE@


def main():
    called = sys.argv[0]
    if not os.path.isabs(called):
        print("你用的是相對路徑（" + called + "）。")
        print("信箱只收從 / 開始的完整地址（絕對路徑）。")
        return 1
    post_office = os.path.join(os.path.dirname(os.path.abspath(called)), "..", "..", "..", "post-office")
    here = os.getcwd()
    if os.path.realpath(here) != os.path.realpath(post_office):
        print("你現在在 " + here + "。")
        print("信要從郵局寄：先走到 post-office。")
        return 1
    key = hashlib.sha256((SALT + ":key:post-office").encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    print(PICTURE, end="")
    print("信投進信箱了！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"))
    return 0


raise SystemExit(main())
'''

# 路徑 → （圖, 說明）。資料夾是地點，檔案是物品。
THINGS = {
    "forest/garden/flower": ("flower", "花開得正好，可是這裡沒有信箱。"),
    "forest/garden/bee": ("bee", "嗡嗡。蜜蜂說牠很忙，沒看到信箱。"),
    "forest/pond/frog": ("frog", "呱！信箱？池塘裡只有我。"),
    "forest/pond/fish": ("fish", "魚吐了一個泡泡，沒有回答你。"),
    "forest/cave/bat": ("bat", "蝙蝠倒掛著睡覺。這裡太暗了，信箱應該不會裝在這裡。"),
    "forest/big-tree/acorn": ("acorn", "樹下有一顆橡實。抬頭一看，樹上好像有個洞。"),
    "post-office/stamp": ("stamp", "一張郵票。信要從這裡寄出去。"),
}


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    for path, (picture, text) in THINGS.items():
        ws.write(path, art.item(picture) + "\n" + text + "\n")
    salt = format(rng.getrandbits(64), "016x")
    mailbox = (
        MAILBOX.replace("@SALT@", salt)
        .replace("@SEALED@", seal(flag, "post-office", salt))
        .replace("@PICTURE@", repr(art.render(LAB_ID)))
    )
    ws.write("forest/big-tree/hole/mailbox", mailbox, mode=0o755)
