"""Lab 09: count rows with cut | sort | uniq -c | sort -n and name the winner."""

from datetime import datetime, timedelta

from labctl.labs import art
from labctl.labs.answer_check import render_check

LAB_ID = "09-sort-uniq"
TITLE = "誰偷吃最多條魚"
FLAG = "TTUSSC{sort_before_you_uniq}"

README = """\
# 09 誰偷吃最多條魚

魚倉庫的監視器把每一次「有企鵝叼走一條魚」都記在 `fish.csv`：

    時間,企鵝,魚

## 你要做的事

算出**誰叼走的魚最多**，然後執行：

    ./check 那隻企鵝的名字

答對會顯示 flag。

## 提示

- `head fish.csv` 先看看檔案長什麼樣子。
- `cut -d, -f2 檔案` 只取出以逗號分隔的第 2 欄。
- `sort` 排序。`uniq -c` 計算「相鄰且相同」的行有幾行，所以要先排序。
- `sort -n` 依數字排序，`sort -nr` 由大到小。
- 用 `|` 把這些指令接起來。記得第一行是標題，不是企鵝。
"""

PENGUINS = ("tux", "pingu", "pororo", "gunter", "skipper", "kowalski", "rico", "mumble")
FISH = ("salmon", "cod", "mackerel", "sardine", "tuna")

NORMALIZE = "    return text.strip().lower()\n"
READ_ANSWER = """\
    if len(sys.argv) != 2:
        print("用法：./check 企鵝的名字")
        return 2
    answer = sys.argv[1]
"""


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    counts = {name: rng.randint(15, 40) for name in PENGUINS}
    winner = rng.choice(PENGUINS)
    counts[winner] = max(c for n, c in counts.items() if n != winner) + rng.randint(1, 4)
    rows = [name for name, count in counts.items() for _ in range(count)]
    rng.shuffle(rows)
    start = datetime(2026, 9, 1, 6, 0)
    lines = ["時間,企鵝,魚\n"]
    for index, name in enumerate(rows):
        stamp = (start + timedelta(minutes=index * 3 + rng.randint(0, 2))).strftime("%Y-%m-%d %H:%M")
        lines.append(f"{stamp},{name},{rng.choice(FISH)}\n")
    ws.write("fish.csv", "".join(lines))
    salt = format(rng.getrandbits(64), "016x")
    ws.write(
        "check",
        render_check(
            flag,
            winner,
            salt,
            "檢查答案：./check 企鵝的名字",
            NORMALIZE,
            READ_ANSWER,
            "不對喔，再數一次。",
            art.render(LAB_ID),
        ),
        mode=0o755,
    )
