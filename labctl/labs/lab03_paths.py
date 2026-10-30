"""Lab 03: absolute vs relative paths and the current working directory."""

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "03-paths"
TITLE = "迷宮裡的門"
FLAG = "TTUSSC{absolute_paths_never_get_lost}"

README = """\
# 03 迷宮裡的門

迷宮 `maze/` 的深處有一扇門，位置在：

    ~/lab/03-paths/maze/north/deep/cave/gate

這扇門很挑：**你必須站在 `/tmp` 裡，而且用「絕對路徑」呼叫它**，它才會打開。

## 你要做的事

1. 先走進迷宮看看：`cd ~/lab/03-paths/maze`，用 `ls`、`cd` 一路走到 `cave`，再試試 `./gate`，看它說什麼。
2. 用 `cd /tmp` 移動到 `/tmp`，用 `pwd` 確認自己在哪裡。
3. 用絕對路徑呼叫那扇門。

## 提示

- 絕對路徑從 `/` 開始，不管你現在在哪裡都指向同一個地方。相對路徑從「你現在的位置」開始算。
- `~` 會被 shell 展開成你的家目錄 `/home/student`，所以 `~/lab/...` 也算絕對路徑。
- `cd ..` 回到上一層，`cd -` 回到上一個去過的地方。
"""

GATE = r'''#!/usr/bin/env python3
"""迷宮深處的門：只在 /tmp、用絕對路徑呼叫時才會打開。"""
import hashlib
import os
import sys

SALT = "@SALT@"
SEALED_FLAG = "@SEALED@"
PICTURE = @PICTURE@
TARGET = "/tmp"


def main():
    called = sys.argv[0]
    if not os.path.isabs(called):
        print("你用的是相對路徑（" + called + "）。這扇門只認從 / 開始的絕對路徑。")
        return 1
    here = os.getcwd()
    if os.path.realpath(here) != os.path.realpath(TARGET):
        print("你現在在 " + here + "。門只在你站在 /tmp 的時候才會打開：先 cd /tmp")
        return 1
    key = hashlib.sha256((SALT + ":key:" + TARGET).encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    print(PICTURE, end="")
    print("門打開了！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"))
    return 0


raise SystemExit(main())
'''

ROOMS = ["north/deep/cave", "north/shallow", "south/lake", "south/lake/island", "east/tunnel", "west/cliff"]


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    for room in ROOMS:
        ws.write(
            f"maze/{room}/note.txt",
            rng.choice(["這裡什麼都沒有。\n", "牆上刻著：往深處走。\n", "地上有企鵝的腳印。\n", "好冷。\n"]),
        )
    salt = format(rng.getrandbits(64), "016x")
    gate = (
        GATE.replace("@SALT@", salt)
        .replace("@SEALED@", seal(flag, "/tmp", salt))
        .replace("@PICTURE@", repr(art.render(LAB_ID)))
    )
    ws.write("maze/north/deep/cave/gate", gate, mode=0o755)
