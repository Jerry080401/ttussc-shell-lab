"""Lab 01: read the prompt, run whoami/hostname, pass arguments to a program."""

from labctl.labs import art
from labctl.labs.answer_check import render_check
from labctl.plan import guest_hostname

LAB_ID = "01-check-in"
TITLE = "報到"
FLAG = "TTUSSC{whoami_is_a_deep_question}"

README = """\
# 01 報到

歡迎！你已經成功登入自己的 Linux。畫面最左邊的這一串叫「提示字元」：

    student@lab-studentXX:~$

- `student`：你的帳號
- `lab-studentXX`：這台主機的名稱，`XX` 是你的編號
- `~`：你現在所在的位置，`~` 代表你的家目錄
- `$`：表示你是一般使用者，管理員 root 的提示字元結尾是 `#`

看到提示字元，就表示可以輸入指令了。

## 你要做的事

1. 輸入 `whoami`，看看你的帳號叫什麼。
2. 輸入 `hostname`，看看這台主機叫什麼。
3. 把這兩個答案當成「參數」，交給報到程式：

       ~/lab/01-check-in/check 帳號 主機名稱

   答對就會顯示 flag。

## 提示

- 一行指令的第一個字是「指令」，後面用空白隔開的都是「參數」。
- Linux 分大小寫：`whoami` 不能打成 `WhoAmI`。
- 指令或檔名打到一半按 Tab，會自動補完。
"""

NORMALIZE = "    return text.strip().lower()\n"
READ_ANSWER = """\
    if len(sys.argv) != 3:
        print("用法：~/lab/01-check-in/check 帳號 主機名稱（兩個參數，中間用空白隔開）")
        return 2
    answer = sys.argv[1] + " " + sys.argv[2]
"""


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    answer = f"student {guest_hostname(student_id)}"
    salt = format(rng.getrandbits(64), "016x")
    ws.write(
        "check",
        render_check(
            flag,
            answer,
            salt,
            "報到：check 帳號 主機名稱",
            NORMALIZE,
            READ_ANSWER,
            "不對喔，用 whoami 和 hostname 再確認一次。",
            art.render(LAB_ID),
        ),
        mode=0o755,
    )
