"""Lab 09: count rows with cut | sort | uniq -c | sort -n and name the winner."""

from datetime import datetime, timedelta

from labctl.labs import art
from labctl.labs.answer_check import render_check

LAB_ID = "09-sort-uniq"
TITLE = "本週最佳織網員"
FLAG = "sort_before_you_uniq"

README = """\
# 09 本週最佳織網員

大家每補好一段網，就會記一筆在 `fixes.csv`：

    時間,織網員,絲線

小壹要頒獎章給本週補得最多的織網員，請你幫忙算一算。

## 你要做的事

算出**誰補的次數最多**，然後執行：

    ./check 那位織網員的名字

答對會顯示 flag。

## 提示

- `head fixes.csv` 先看看檔案長什麼樣子。
- `cut -d, -f2 檔案` 只取出以逗號分隔的第 2 欄。
- `sort` 排序。`uniq -c` 計算「相鄰且相同」的行有幾行，所以要先排序。
- `sort -n` 依數字排序，`sort -nr` 由大到小。
- 用 `|` 把這些指令接起來。記得第一行是標題，不是織網員。
"""

WEAVERS = ("amy", "ben", "cindy", "david", "emma", "frank", "grace", "henry")
SILK = ("red", "blue", "green", "white", "black")

NORMALIZE = "    return text.strip().lower()\n"
READ_ANSWER = """\
    if len(sys.argv) != 2:
        print("用法：./check 織網員的名字")
        return 2
    answer = sys.argv[1]
"""


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    counts = {name: rng.randint(15, 40) for name in WEAVERS}
    winner = rng.choice(WEAVERS)
    counts[winner] = max(c for n, c in counts.items() if n != winner) + rng.randint(1, 4)
    rows = [name for name, count in counts.items() for _ in range(count)]
    rng.shuffle(rows)
    start = datetime(2026, 9, 1, 6, 0)
    lines = ["時間,織網員,絲線\n"]
    for index, name in enumerate(rows):
        stamp = (start + timedelta(minutes=index * 3 + rng.randint(0, 2))).strftime("%Y-%m-%d %H:%M")
        lines.append(f"{stamp},{name},{rng.choice(SILK)}\n")
    ws.write("fixes.csv", "".join(lines))
    salt = format(rng.getrandbits(64), "016x")
    ws.write(
        "check",
        render_check(
            flag,
            winner,
            salt,
            "檢查答案：./check 織網員的名字",
            NORMALIZE,
            READ_ANSWER,
            "對方接過獎章，愣了一下：「我這週沒補那麼多吧？」\\n小壹默默把獎章收回來。再數一次。",
            art.render(LAB_ID),
        ),
        mode=0o755,
    )
