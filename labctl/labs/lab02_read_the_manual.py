"""Lab 02: options and arguments, learned from a program's --help and its man page."""

import hashlib

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "02-read-the-manual"
TITLE = "蛛絲電話"
FLAG = "is1ab{always_read_the_manual}"

README = """\
# 02 蛛絲電話

朋友透過蛛絲電話 `phone` 傳來一則訊息。可是線路很多條，你不知道該接哪一條，也不知道電話怎麼用，小壹說：先看說明書。

## 你要做的事

弄懂 `phone` 怎麼用，接上朋友的線路，聽清楚訊息。訊息裡有 flag。

## 提示

- 很多程式都有 `--help`，會告訴你怎麼用。
- `man` 可以打開說明書，在 man 裡按 `/` 搜尋、按 `q` 離開。
- 選項有短的（`-l`）也有長的（`--line`），意思一樣。
- 有些選項後面要接一個值，例如 `-l 線路號碼`。
- 線路表上的每一條都可以接接看。
"""

PHONE = r'''#!/usr/bin/env python3
"""蛛絲電話。"""
import getopt
import hashlib
import sys

SALT = "@SALT@"
ANSWER_SHA256 = "@ANSWER@"
SEALED_FLAG = "@SEALED@"
PICTURE = @PICTURE@
OTHER_LINES = @OTHERS@

HELP = """用法：./phone [選項]

蛛絲電話。

選項：
  -l, --line 線路      接上指定的線路（數字）
  -d, --decode         把收到的訊息解碼
  -h, --help           顯示這份說明

線路表不在這裡，請看說明書：man ./phone.1
"""


def main(args):
    if not args:
        print("電話還沒接線。不知道怎麼用？試試 ./phone --help")
        return 1
    # 和 GNU 的指令一樣：-dl 88、-l88、--line=88 都可以
    try:
        options, rest = getopt.gnu_getopt(args, "l:dh", ["line=", "decode", "help"])
    except getopt.GetoptError as exc:
        if exc.opt in ("l", "line"):
            print("-l／--line 後面要接線路號碼")
        else:
            print("看不懂的選項：" + ("-" if len(exc.opt) == 1 else "--") + exc.opt
                  + "（用 ./phone --help 看有哪些選項）")
        return 2
    if rest:
        print("多出來的參數：" + " ".join(rest) + "（線路要寫在 -l 後面，例如 -l 88）")
        return 2
    line, decode = None, False
    for option, value in options:
        if option in ("-h", "--help"):
            print(HELP, end="")
            return 0
        if option in ("-d", "--decode"):
            decode = True
        else:
            line = value
    if line is None:
        print("還沒選線路：用 -l 或 --line 指定")
        return 1
    line = line.strip()
    known = line in OTHER_LINES
    if not known and hashlib.sha256((SALT + line).encode("utf-8")).hexdigest() != ANSWER_SHA256:
        print("第 " + line + " 號線沒有人接。線路表在 man ./phone.1")
        return 1
    if not decode:
        print("接通了，但訊息聽不清楚……加上 -d（--decode）把它解碼")
        return 1
    if known:
        print(OTHER_LINES[line])
        return 0
    key = hashlib.sha256((SALT + ":key:" + line).encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    print(PICTURE, end="")
    print("聽清楚朋友的訊息了！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"))
    return 0


raise SystemExit(main(sys.argv[1:]))
'''

MANUAL = r""".TH PHONE 1 "2026" "is1ab" "蛛絲電話使用手冊"
.ad l
.SH 名稱
phone \- 蛛絲電話
.SH 用法
.B ./phone
.RB [ \-l
.IR 線路 ]
.RB [ \-d ]
.SH 說明
朋友的訊息會從固定的線路傳來。
先用
.B \-l
接上正確的線路，再加上
.B \-d
把訊息解碼。
.SH 線路表
@TABLE@
.SH 範例
.B ./phone \-\-line 88 \-\-decode
.SH 另見
.BR man (1)
"""

# 線路表上的其他線路：接上才知道是什麼
OTHER_LINES = {
    "樹梢的線路": "呼——呼——只有風聲。樹梢上什麼都沒有，但風景不錯。",
    "屋簷的線路": "滴答、滴答。外面下雨了，記得收衣服。",
    "蟋蟀家的線路": "唧唧唧！蟋蟀正在練歌，牠說下個月開演唱會，叫你記得來。",
    "螞蟻隊的線路": "「一二、一二！」螞蟻隊正在搬餅乾，現在沒空講電話。",
}


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    numbers = [str(number) for number in rng.sample(range(100, 1000), len(OTHER_LINES) + 1)]
    line, others = numbers[0], dict(zip(numbers[1:], OTHER_LINES.values(), strict=True))
    table = [(name, number) for name, number in zip(OTHER_LINES, numbers[1:], strict=True)] + [("朋友的線路", line)]
    rng.shuffle(table)
    salt = format(rng.getrandbits(64), "016x")
    phone = (
        PHONE.replace("@SALT@", salt)
        .replace("@ANSWER@", hashlib.sha256((salt + line).encode("utf-8")).hexdigest())
        .replace("@SEALED@", seal(flag, line, salt))
        .replace("@PICTURE@", repr(art.render(LAB_ID)))
        .replace("@OTHERS@", repr(others))
    )
    ws.write("phone", phone, mode=0o755)
    ws.write("phone.1", MANUAL.replace("@TABLE@", "\n.br\n".join(f"{name}：第 {number} 號" for name, number in table)))
