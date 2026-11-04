"""Lab 12: find differences with diff and fix them in an editor."""

from labctl.labs import art
from labctl.labs.answer_check import render_check

LAB_ID = "12-diff-config"
TITLE = "修好蛛網"
FLAG = "is1ab{spot_the_difference_with_diff}"

README = """\
# 12 修好蛛網

蛛網最近怪怪的，蟲都黏不住。小壹翻了翻蛛網的設定檔 `web.conf`，發現有幾行被改錯了。還好有一份正確的範本 `expected.conf`，小壹請你幫忙修好。

## 你要做的事

1. 找出 `web.conf` 和 `expected.conf` 有哪幾行不一樣。
2. 用文字編輯器把 `web.conf` 改成跟範本一樣。
3. 執行 `./check`，全部改對就會顯示 flag。

## 提示

- `diff 檔案一 檔案二` 比較兩個檔案。輸出裡 `<` 開頭是第一個檔案的內容，`>` 開頭是第二個檔案的內容。
- 文字編輯器可以用 `nano 檔案` 或 `vim 檔案`。
- nano：改完按 `Ctrl+O`、`Enter` 存檔，`Ctrl+X` 離開。
- vim：按 `i` 開始輸入，改完按 `Esc`，再輸入 `:wq` 存檔離開。
"""

SETTINGS = [
    ("name", ["main-web", "apple-web", "lemon-web"]),
    ("remote_line", ["friend-tree"]),  # 第 8 題小壹接上的那條線
    ("lines", ["24", "32", "40"]),
    ("circles", ["12", "15", "9"]),
    ("glue", ["on", "auto"]),
    ("theme", ["red-black", "blue", "green"]),
    ("guard", ["amy", "ben"]),
    ("check_time", ["06:30", "07:00", "05:45"]),
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
        with open("web.conf", encoding="utf-8") as handle:
            answer = handle.read()
    except OSError as exc:
        print(f"讀不到 web.conf：{exc}。先 cd ~/lab/12-diff-config 再執行 ./check")
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
        return "# 蛛網設定\n" + "".join(f"{key} = {settings[key]}\n" for key, _ in SETTINGS)

    expected = render(values)
    ws.write("expected.conf", expected)
    ws.write("web.conf", render(broken))
    salt = format(rng.getrandbits(64), "016x")
    ws.write(
        "check",
        render_check(
            flag,
            normalize(expected),
            salt,
            "檢查 web.conf 是否已改成和 expected.conf 相同：./check",
            NORMALIZE,
            READ_ANSWER,
            "還有地方不一樣，用 diff 再比一次。",
            art.render(LAB_ID),
        ),
        mode=0o755,
    )
