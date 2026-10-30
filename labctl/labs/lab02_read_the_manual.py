"""Lab 02: options and arguments, learned from a program's --help and its man page."""

import hashlib

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "02-read-the-manual"
TITLE = "看說明書"
FLAG = "TTUSSC{always_read_the_manual}"

README = """\
# 02 看說明書

這個資料夾裡有一台企鵝電台收音機 `radio`。企鵝電台每天在固定的頻道播放 flag，可是沒人告訴你是哪個頻道，也沒人告訴你收音機怎麼用。

## 你要做的事

1. 先 `cd ~/lab/02-read-the-manual`。
2. 用 `./radio --help` 看它有哪些選項。
3. 說明裡會告訴你去哪裡找頻道表，照著去找。
4. 調到正確的頻道並解碼，就會聽到 flag。

## 提示

- 選項有短的（`-c`）也有長的（`--channel`），意思一樣。
- 有些選項後面要接一個值，例如 `-c 頻道數字`。
- `man` 可以打開說明書，在 man 裡按 `/` 搜尋、按 `q` 離開。
"""

RADIO = r'''#!/usr/bin/env python3
"""企鵝電台收音機。"""
import getopt
import hashlib
import sys

SALT = "@SALT@"
ANSWER_SHA256 = "@ANSWER@"
SEALED_FLAG = "@SEALED@"
PICTURE = @PICTURE@

HELP = """用法：./radio [選項]

企鵝電台收音機。

選項：
  -c, --channel 頻道   調到指定的頻道（數字）
  -d, --decode         把收到的訊號解碼
  -h, --help           顯示這份說明

頻道表不在這裡，請看說明書：man ./radio.1
"""


def main(args):
    if not args:
        print("收音機沒有開。不知道怎麼用？試試 ./radio --help")
        return 1
    # 和 GNU 的指令一樣：-dc 88、-c88、--channel=88 都可以
    try:
        options, rest = getopt.gnu_getopt(args, "c:dh", ["channel=", "decode", "help"])
    except getopt.GetoptError as exc:
        if exc.opt in ("c", "channel"):
            print("-c／--channel 後面要接頻道數字")
        else:
            print("看不懂的選項：" + ("-" if len(exc.opt) == 1 else "--") + exc.opt
                  + "（用 ./radio --help 看有哪些選項）")
        return 2
    if rest:
        print("多出來的參數：" + " ".join(rest) + "（頻道要寫在 -c 後面，例如 -c 88）")
        return 2
    channel, decode = None, False
    for option, value in options:
        if option in ("-h", "--help"):
            print(HELP, end="")
            return 0
        if option in ("-d", "--decode"):
            decode = True
        else:
            channel = value
    if channel is None:
        print("還沒選頻道：用 -c 或 --channel 指定")
        return 1
    channel = channel.strip()
    if hashlib.sha256((SALT + channel).encode("utf-8")).hexdigest() != ANSWER_SHA256:
        print("第 " + channel + " 頻道只有沙沙的雜訊。頻道表在 man ./radio.1")
        return 1
    if not decode:
        print("收到一串加密的訊號……加上 -d（--decode）把它解碼")
        return 1
    key = hashlib.sha256((SALT + ":key:" + channel).encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    print(PICTURE, end="")
    print("收到企鵝電台的廣播！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"))
    return 0


raise SystemExit(main(sys.argv[1:]))
'''

MANUAL = r""".TH RADIO 1 "2026" "TTUSSC" "企鵝電台使用手冊"
.SH 名稱
radio \- 企鵝電台收音機
.SH 用法
.B ./radio
.RB [ \-c
.IR 頻道 ]
.RB [ \-d ]
.SH 說明
企鵝電台每天在固定的頻道播放加密的 flag。
先用
.B \-c
調到正確的頻道，再加上
.B \-d
把訊號解碼。
.SH 頻道表
企鵝電台：第 @PENGUIN@ 頻道
.br
海豹新聞台：第 @SEAL@ 頻道（只有雜訊）
.SH 範例
.B ./radio \-\-channel 88 \-\-decode
.SH 另見
.BR man (1)
"""


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    channel = str(rng.randint(100, 999))
    decoy = str(rng.choice([c for c in range(100, 1000) if str(c) != channel]))
    salt = format(rng.getrandbits(64), "016x")
    radio = (
        RADIO.replace("@SALT@", salt)
        .replace("@ANSWER@", hashlib.sha256((salt + channel).encode("utf-8")).hexdigest())
        .replace("@SEALED@", seal(flag, channel, salt))
        .replace("@PICTURE@", repr(art.render(LAB_ID)))
    )
    ws.write("radio", radio, mode=0o755)
    ws.write("radio.1", MANUAL.replace("@PENGUIN@", channel).replace("@SEAL@", decoy))
