"""Lab 08: combine two greps with a pipe to find one log line."""

from datetime import datetime, timedelta, timezone

LAB_ID = "08-grep-log"
TITLE = "企鵝只登入成功一次"
FLAG = "TTUSSC{grep_finds_the_needle}"

README = """\
# 08 企鵝只登入成功一次

冰屋的登入服務把每一次登入都記在 `service.log`。企鵝（`user=penguin`）試了很多次都失敗，
**只成功過一次**，成功那一行最後面寫著 flag。

## 你要做的事

找出 `user=penguin` 而且 `result=success` 的那一行。

## 提示

- `less service.log` 可以一頁一頁看（按 `q` 離開），但檔案有二十萬行，用看的看不完。
- `grep 文字 檔案` 只留下含有那段文字的行。
- `|`（pipe）把前一個指令的輸出交給下一個指令，例如 `指令一 | grep 另一段文字`。
- 小心：檔案裡有很多長得像 flag 的假資料。
"""

USERS = ("seal", "walrus", "orca", "puffin", "albatross", "krill")
START = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone(timedelta(hours=8)))


LINES = 200_000  # 用 less 或捲動翻不完（約 25 MB），只能用 grep 找


def _fake_flag(rng):
    return "TTUSSC{" + format(rng.getrandbits(64), "016x") + "}"


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    success_at = rng.randint(LINES // 5, LINES * 4 // 5)  # 不在開頭或結尾附近
    lines = []
    for index in range(LINES + 1):
        if index == success_at:
            user, result, note = "penguin", "success", f" note={flag}"
        else:
            user = "penguin" if rng.random() < 0.08 else rng.choice(USERS)
            result = "failure" if user == "penguin" else rng.choice(("success", "success", "failure"))
            note = f" note={_fake_flag(rng)}" if rng.random() < 0.1 else ""
        stamp = (START + timedelta(seconds=index * 7 + rng.randint(0, 6))).isoformat()
        level = "INFO" if result == "success" else "WARN"
        host = rng.getrandbits(24)
        ip = f"10.{host >> 16}.{(host >> 8) & 255}.{(host & 255) % 254 + 1}"
        lines.append(f"{stamp} service=iceauth level={level} user={user} action=login result={result} ip={ip}{note}\n")
    ws.write("service.log", "".join(lines))
