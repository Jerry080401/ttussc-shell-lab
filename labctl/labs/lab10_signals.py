"""Lab 10: background jobs, ps, and sending a specific signal with kill."""

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "10-signals"
TITLE = "叫醒小蜘蛛"
FLAG = "kill_just_sends_a_signal"

README = """\
# 10 叫醒小蜘蛛

守夜的小蜘蛛 `sleepy` 睡過頭了。牠醒來的時候會說出 flag，但要輕輕撥動絲線才叫得醒，太大聲會把牠嚇跑。

## 你要做的事

1. 先直接執行 `./sleepy` 看看，再按 Ctrl+C，看牠說什麼。
2. 這次讓牠在**背景**睡：`./sleepy &`。shell 會印出工作編號和行程編號（PID）。
3. 用 `ps` 找到 `sleepy` 的 PID。
4. 用 `kill` 送出 **USR1** 訊號，就像輕撥絲線：`kill -USR1 PID`（把 PID 換成你查到的數字）。

## 提示

- 在指令後面加 `&`，程式會在背景執行，你可以繼續打別的指令。
- `ps` 列出目前的行程，`PID` 欄是行程編號，`CMD` 欄是名稱。
- `kill` 其實是「送訊號」：不加選項時送 TERM（請它結束），`-USR1` 則是送 USR1 訊號。Ctrl+C 送的是 INT。
- `jobs` 看背景工作，`fg` 把背景工作叫回前景。
- 背景程式的輸出會蓋過提示字元。畫面看起來停住時不是當掉，按一下 Enter 就會回來。
"""

SLEEPY = r'''#!/usr/bin/env python3
"""守夜的小蜘蛛：收到 USR1 訊號才會醒來說出 flag。"""
import ctypes
import hashlib
import signal
import sys
import time

SALT = "@SALT@"
SEALED_FLAG = "@SEALED@"
PICTURE = @PICTURE@


def show_as_sleepy():
    # 讓 ps 顯示 sleepy 而不是 python3（Linux 的 PR_SET_NAME）
    try:
        ctypes.CDLL(None).prctl(15, b"sleepy", 0, 0, 0)
    except (OSError, AttributeError):
        pass


def say(text, code):
    print(text, flush=True)
    sys.exit(code)


def on_usr1(signum, frame):
    key = hashlib.sha256((SALT + ":key:USR1").encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    say(PICTURE + "小蜘蛛揉揉眼睛醒來了！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"), 0)


def on_int(signum, frame):
    say("Ctrl+C（INT 訊號）把小蜘蛛嚇跑了，沒拿到 flag。\n試試讓牠在背景睡，再用 kill 送 USR1。", 130)


def on_term(signum, frame):
    say("小蜘蛛被請走了（TERM 訊號）。要叫醒牠，請送 USR1：kill -USR1 PID", 143)


show_as_sleepy()
signal.signal(signal.SIGUSR1, on_usr1)
signal.signal(signal.SIGINT, on_int)
signal.signal(signal.SIGTERM, on_term)
print("小蜘蛛睡著了……zzz（要用 kill 送 USR1 訊號才叫得醒）", flush=True)
deadline = time.time() + 600
while time.time() < deadline:
    time.sleep(1)
say("小蜘蛛睡飽，自己回家了。再執行一次 ./sleepy 重來。", 1)
'''


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    salt = format(rng.getrandbits(64), "016x")
    sleepy = (
        SLEEPY.replace("@SALT@", salt)
        .replace("@SEALED@", seal(flag, "USR1", salt))
        .replace("@PICTURE@", repr(art.render(LAB_ID)))
    )
    ws.write("sleepy", sleepy, mode=0o755)
