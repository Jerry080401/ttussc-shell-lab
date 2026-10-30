"""Lab 10: background jobs, ps, and sending a specific signal with kill."""

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "10-signals"
TITLE = "叫醒企鵝"
FLAG = "TTUSSC{kill_just_sends_a_signal}"

README = """\
# 10 叫醒企鵝

`sleepy` 是一隻愛睡覺的企鵝。牠醒來的時候會說出 flag，但只有用對方法叫牠才會醒。

## 你要做的事

1. `cd ~/lab/10-signals`，先直接執行 `./sleepy` 看看，再按 Ctrl+C，看牠說什麼。
2. 這次讓牠在**背景**睡：`./sleepy &`。shell 會印出工作編號和行程編號（PID）。
3. 用 `ps` 找到 `sleepy` 的 PID。
4. 用 `kill` 送出 **USR1** 訊號叫醒牠：`kill -USR1 PID`（把 PID 換成你查到的數字）。

## 提示

- 在指令後面加 `&`，程式會在背景執行，你可以繼續打別的指令。
- `ps` 列出目前的行程，`PID` 欄是行程編號，`CMD` 欄是名稱。
- `kill` 其實是「送訊號」：不加選項時送 TERM（請它結束），`-USR1` 則是送 USR1 訊號。Ctrl+C 送的是 INT。
- `jobs` 看背景工作，`fg` 把背景工作叫回前景。
"""

SLEEPY = r'''#!/usr/bin/env python3
"""打瞌睡的企鵝：收到 USR1 訊號才會醒來說出 flag。"""
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
    say(PICTURE + "企鵝醒來了！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"), 0)


def on_int(signum, frame):
    say("Ctrl+C（INT 訊號）把企鵝嚇跑了，沒拿到 flag。試試讓牠在背景睡，再用 kill 送 USR1。", 130)


def on_term(signum, frame):
    say("企鵝被趕走了（TERM 訊號）。要叫醒牠，請送 USR1：kill -USR1 PID", 143)


show_as_sleepy()
signal.signal(signal.SIGUSR1, on_usr1)
signal.signal(signal.SIGINT, on_int)
signal.signal(signal.SIGTERM, on_term)
print("企鵝睡著了……zzz（要用 kill 送 USR1 訊號才叫得醒）", flush=True)
deadline = time.time() + 600
while time.time() < deadline:
    time.sleep(1)
say("企鵝睡飽，自己走了。再執行一次 ./sleepy 重來。", 1)
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
