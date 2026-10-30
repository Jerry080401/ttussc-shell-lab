"""Lab 06: pick the one real file with find -name and -size."""

from labctl.labs import art

LAB_ID = "06-find-real-file"
TITLE = "倉庫裡只有一份真的"
FLAG = "TTUSSC{one_real_box_among_many_fakes}"

README = """\
# 06 倉庫裡只有一份真的

魚倉庫 `warehouse/` 裡堆滿了箱子，每個箱子上都寫著一組 `TTUSSC{{...}}`，但只有一份是真的。

## 線索

真的那一份：

- 檔名以 `.fish` 結尾
- 大小剛好 {size} 位元組（bytes）

## 你要做的事

用 `find` 把符合「兩個條件」的檔案找出來，再用 `cat` 讀它。

## 提示

- `find 資料夾 -name '*.fish'` 依檔名找。
- `find 資料夾 -size 100c` 找大小剛好 100 位元組的檔案（`c` 代表位元組）。
- 兩個條件可以寫在同一個 `find` 指令裡。
"""

EXTENSIONS = ("fish", "food", "ice")
# 每個箱子都印著同一張圖（只放真箱子的話，grep 圖就能繞過 find），大小從圖的大小往上加。
PICTURE = art.render(LAB_ID)
BASE = len(PICTURE.encode("utf-8"))


def _box(label, flag, size):
    head = (PICTURE + f"\n箱子 {label}\n內容物：{flag}\n").encode("utf-8")
    if len(head) >= size:
        raise ValueError("box too small for its label")
    return head + b"~" * (size - len(head) - 1) + b"\n"


def _fake_flag(rng):
    return "TTUSSC{" + "".join(rng.choice("0123456789abcdef") for _ in range(16)) + "}"


def seed(ws, flag, rng, student_id):
    real_size = BASE + rng.randint(1000, 1999)
    ws.write("README.md", README.format(size=real_size))
    shelves = [f"{area}/{shelf}" for area in ("north", "south", "east", "west") for shelf in ("a", "b", "c")]
    # 至少 4 個「副檔名對、大小錯」與 4 個「大小對、副檔名錯」的干擾箱。
    kinds = ["real"] + ["fish-wrong-size"] * 4 + ["right-size-wrong-ext"] * 4 + ["random"] * 27
    rng.shuffle(kinds)
    for number, kind in enumerate(kinds, start=100):
        shelf = shelves[number % len(shelves)]
        if kind == "real":
            ext, size, content_flag = "fish", real_size, flag
        elif kind == "fish-wrong-size":
            ext, size, content_flag = (
                "fish",
                rng.choice([real_size - rng.randint(1, 300), real_size + rng.randint(1, 300)]),
                _fake_flag(rng),
            )
        elif kind == "right-size-wrong-ext":
            ext, size, content_flag = rng.choice(EXTENSIONS[1:]), real_size, _fake_flag(rng)
        else:
            ext = rng.choice(EXTENSIONS)
            size = BASE + rng.randint(800, 2300)
            while size == real_size:
                size = BASE + rng.randint(800, 2300)
            content_flag = _fake_flag(rng)
        ws.write(f"warehouse/{shelf}/box-{number}.{ext}", _box(number, content_flag, size))
