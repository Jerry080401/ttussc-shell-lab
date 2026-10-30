"""Bonus lab 12: find differences with diff and fix them in an editor."""

from labctl.labs import art
from labctl.labs.answer_check import render_check

LAB_ID = "12-diff-config"
TITLE = "加分：設定檔差在哪"
FLAG = "TTUSSC{spot_the_difference_with_diff}"

README = """\
# 12 加分：設定檔差在哪

企鵝基地的設定檔 `penguin.conf` 被改壞了幾行。`expected.conf` 是正確的範本。

## 你要做的事

1. 用 `diff penguin.conf expected.conf` 找出哪幾行不一樣。
2. 用編輯器（`nano penguin.conf` 或 `vim penguin.conf`）把 `penguin.conf` 改成跟範本一樣。
3. 執行 `./check`，全部改對就會顯示 flag。

## 提示

- `diff` 的輸出裡，`<` 開頭是第一個檔案的內容，`>` 開頭是第二個檔案的內容。
- nano：改完按 `Ctrl+O`、`Enter` 存檔，`Ctrl+X` 離開。
- vim：按 `i` 開始輸入，改完按 `Esc`，再輸入 `:wq` 存檔離開。
"""

SETTINGS = [
    ("name", ["tux-base", "ice-station", "snow-camp"]),
    ("port", ["8022", "9022", "7022"]),
    ("fish_per_day", ["12", "15", "9"]),
    ("heater", ["on", "auto"]),
    ("theme", ["ice-blue", "aurora", "midnight"]),
    ("guard", ["seal", "walrus"]),
    ("alarm", ["06:30", "07:00", "05:45"]),
    ("max_guests", ["4", "6", "8"]),
]

NORMALIZE = """\
    lines = [line.rstrip() for line in text.replace("\\r\\n", "\\n").split("\\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\\n".join(lines)
"""
READ_ANSWER = """\
    try:
        with open("penguin.conf", encoding="utf-8") as handle:
            answer = handle.read()
    except OSError as exc:
        print(f"讀不到 penguin.conf：{exc}")
        return 2
"""


def normalize(text):
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    values = {key: rng.choice(choices) for key, choices in SETTINGS}
    broken = dict(values)
    for key in rng.sample([key for key, _ in SETTINGS], 3):
        broken[key] = rng.choice([c for c in dict(SETTINGS)[key] if c != values[key]] + [values[key] + "0"])

    def render(settings):
        return "# 企鵝基地設定\n" + "".join(f"{key} = {settings[key]}\n" for key, _ in SETTINGS)

    expected = render(values)
    ws.write("expected.conf", expected)
    ws.write("penguin.conf", render(broken))
    salt = format(rng.getrandbits(64), "016x")
    ws.write(
        "check",
        render_check(
            flag,
            normalize(expected),
            salt,
            "檢查 penguin.conf 是否已改成和 expected.conf 相同：./check",
            NORMALIZE,
            READ_ANSWER,
            "還有地方不一樣，用 diff 再比一次。",
            art.render(LAB_ID),
        ),
        mode=0o755,
    )
