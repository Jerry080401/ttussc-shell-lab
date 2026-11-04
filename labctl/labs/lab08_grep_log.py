"""Lab 08: combine two greps with a pipe to find one log line."""

from datetime import datetime, timedelta, timezone

from labctl.labs import art
from labctl.labs.answer_check import render_check
from labctl.labs.flags import decoy_flag

LAB_ID = "08-grep-log"
TITLE = "那通接通的電話"
FLAG = "is1ab{grep_finds_the_right_line}"

README = """\
# 08 那通接通的電話

小壹打電話給住在遠方的朋友，打了好多次都沒接通，只有一次接通了。朋友在電話裡說了一句話，就是 flag，可是小壹忘了。

幸好電話服務會把每一通電話都記在 `service.log`：誰打的、有沒有接通，接通時對方說的話也會記下來。小壹的帳號是 `xiaoyi`。

## 你要做的事

找出小壹接通的那一通，把朋友說的話交給小壹確認：

    ./check 朋友說的話

## 提示

- `head 檔案` 看前幾行，先弄清楚每一行長什麼樣子。
- `user=` 是誰打的。`result=success` 是接通了，`result=failure` 是沒接通。
- `less service.log` 可以一頁一頁看（按 `q` 離開），但檔案有二十萬行，用看的看不完。
- `grep 文字 檔案` 只留下含有那段文字的行。
- `|`（pipe）把前一個指令的輸出交給下一個指令，例如 `指令一 | grep 另一段文字`，這樣就能同時篩選兩個條件。
- 小心：別人的通話裡也有很多長得像 flag 的句子。
"""

USERS = ("amy", "ben", "cindy", "david", "emma", "frank")
START = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone(timedelta(hours=8)))


READ_ANSWER = """\
    if len(sys.argv) != 2:
        print("用法：./check 朋友說的話")
        return 2
    answer = sys.argv[1]
"""
LINES = 200_000  # 用 less 或捲動翻不完（約 25 MB），只能用 grep 找


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    success_at = rng.randint(LINES // 5, LINES * 4 // 5)  # 不在開頭或結尾附近
    lines = []
    for index in range(LINES + 1):
        if index == success_at:
            user, result, note = "xiaoyi", "success", f" note={flag}"
        else:
            user = "xiaoyi" if rng.random() < 0.08 else rng.choice(USERS)
            result = "failure" if user == "xiaoyi" else rng.choice(("success", "success", "failure"))
            note = f" note={decoy_flag(rng)}" if rng.random() < 0.1 else ""
        stamp = (START + timedelta(seconds=index * 7 + rng.randint(0, 6))).isoformat()
        level = "INFO" if result == "success" else "WARN"
        host = rng.getrandbits(24)
        ip = f"10.{host >> 16}.{(host >> 8) & 255}.{(host & 255) % 254 + 1}"
        lines.append(
            f"{stamp} service=phone level={level} user={user} action=call target=friend-tree result={result} ip={ip}{note}\n"
        )
    ws.write("service.log", "".join(lines))
    salt = format(rng.getrandbits(64), "016x")
    ws.write(
        "check",
        render_check(
            flag,
            flag,
            salt,
            "確認朋友說的話：./check 朋友說的話",
            "    return text.strip()\n",
            READ_ANSWER,
            "小壹想了想：「朋友說的不是這句。」再查一次，要找小壹自己接通的那一通。",
            art.render(LAB_ID),
        ),
        mode=0o755,
    )
