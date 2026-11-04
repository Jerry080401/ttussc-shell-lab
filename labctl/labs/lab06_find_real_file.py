"""Lab 06: pick the one real file with find -name and -size."""

from labctl.labs import art

LAB_ID = "06-find-real-file"
TITLE = "找出那束好絲"
FLAG = "is1ab{one_real_item_among_many_fakes}"

README = """\
# 06 找出那束好絲

小壹要補網，請你去儲藏室 `storage/` 領一束絲。裡面的絲束看起來都一樣，每束都掛著一組 `is1ab{{...}}` 標籤，但只有一束符合訂單。

## 訂單

要領的那一束：

- 種類是蜘蛛絲：檔名以 `.silk` 結尾
- 長度剛好：檔案大小 {size} 位元組（bytes）

## 你要做的事

用 `find` 把符合「兩個條件」的檔案找出來，再用 `cat` 讀它。

## 提示

- `find 資料夾 條件` 會在資料夾裡一層一層往下找。常用的條件有：
  - `-name 檔名`：依檔名找，檔名可以用 `*` 代表任意文字，例如 `-name '*.txt'`（記得加引號）
  - `-type f`：只找檔案，`-type d`：只找資料夾
  - `-size 100c`：大小剛好 100 位元組（`c` 代表位元組，`k` 代表 KB）
  - `-size +100c`：比 100 位元組大，`-size -100c`：比 100 位元組小
- 條件可以寫很多個，要全部符合才會列出來。
"""

EXTENSIONS = ("silk", "rope", "string")
# 每束都印著同一張圖（只放真的那束的話，grep 圖就能繞過 find），大小從圖的大小往上加。
PICTURE = art.render(LAB_ID)
BASE = len(PICTURE.encode("utf-8"))
PADDING_WIDTH = 39


def _item(label, flag, size):
    # 填充放在前面、切成短行：cat 的時候 flag 留在畫面最下面，不會被推走。
    tail = (PICTURE + f"\n絲束 {label}\n標籤：{flag}\n").encode("utf-8")
    if len(tail) >= size:
        raise ValueError("item too small for its label")
    padding = size - len(tail)
    full, rest = divmod(padding, PADDING_WIDTH + 1)
    return (b"~" * PADDING_WIDTH + b"\n") * full + (b"~" * (rest - 1) + b"\n" if rest else b"") + tail


def _fake_flag(rng):
    return "is1ab{" + "".join(rng.choice("0123456789abcdef") for _ in range(16)) + "}"


def seed(ws, flag, rng, student_id):
    real_size = BASE + rng.randint(1000, 1999)
    ws.write("README.md", README.format(size=real_size))
    shelves = [f"box{number}" for number in range(1, 13)]
    # 至少 4 束「副檔名對、大小錯」與 4 束「大小對、副檔名錯」的干擾。
    kinds = ["real"] + ["silk-wrong-size"] * 4 + ["right-size-wrong-ext"] * 4 + ["random"] * 27
    rng.shuffle(kinds)
    for number, kind in enumerate(kinds, start=100):
        shelf = shelves[number % len(shelves)]
        if kind == "real":
            ext, size, content_flag = "silk", real_size, flag
        elif kind == "silk-wrong-size":
            ext, size, content_flag = (
                "silk",
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
        ws.write(f"storage/{shelf}/item-{number}.{ext}", _item(number, content_flag, size))
