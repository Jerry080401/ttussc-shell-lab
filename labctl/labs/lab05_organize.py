"""Lab 05: mkdir, mv, rm, cp with wildcards. ./check verifies the final layout."""

import hashlib
import json

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "05-organize"
TITLE = "大掃除"
FLAG = "is1ab{rm_has_no_recycle_bin}"

README = """\
# 05 大掃除

巢穴 `nest/` 堆滿了東西：絲線（`.silk`）、落葉（`.leaf`）和露水（`.water`）。小壹請你幫忙整理好。絲線和露水都是大家辛苦收集的，不能丟。

## 你要做的事

1. 建立一個資料夾 `box`（和 `map.txt` 放在同一層），這是收絲線的地方。
2. 把 `nest` 裡**所有的絲線**搬進 `box`。
3. 把 `nest` 裡**所有的落葉**刪掉。露水要留在 `nest`。
4. 把地圖 `map.txt` **複製**一份，取名 `map.bak`。
5. 執行 `./check`，全部做對就會顯示 flag，哪裡不對它會告訴你。

## 提示

- `mkdir 名稱` 建立資料夾、`mv 來源 目的地` 搬移、`rm 檔案` 刪除、`cp 來源 新檔名` 複製。
- 每個檔案都可以用 `cat` 看看是什麼。
- 萬用字元 `*` 代表「任意長度的任何字」：`*.txt` 就是所有 `.txt` 結尾的檔案。
- **`rm` 刪掉的檔案不會進資源回收筒**。刪之前先用 `ls` 確認會刪到哪些。
"""

CHECK = r'''#!/usr/bin/env python3
"""檢查巢穴整理好了沒：./check"""
import hashlib
import json
import os
import sys

SALT = "@SALT@"
ANSWER_SHA256 = "@ANSWER@"
SEALED_FLAG = "@SEALED@"
PICTURE = @PICTURE@
SILK = set(json.loads(@SILK@))
WATER = set(json.loads(@WATER@))
KEEP = json.loads(@KEEP@)
MAP_TEXT = @MAP@


def listing(path):
    return set(os.listdir(path)) if os.path.isdir(path) else None


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def put_back(name, content):
    os.makedirs("nest", exist_ok=True)
    path = os.path.join("nest", name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def rescue():
    """誤刪的東西放回去，學生不會卡住。"""
    found = {name for _, _, names in os.walk(".") for name in names}
    missing = sorted(set(KEEP) - found)
    for name in missing:
        put_back(name, KEEP[name])
    if any(name.endswith(".silk") for name in missing):
        print("小壹趕緊把絲線撿回來：「這是大家吐了好幾天的絲，不能丟！」")
    if any(name.endswith(".water") for name in missing):
        print("小壹趕緊把露水接回來：「這是早上才收的，要拿來泡茶的！」")
    if not os.path.exists("map.txt") and not os.path.exists("map.bak"):
        with open("map.txt", "w", encoding="utf-8") as handle:
            handle.write(MAP_TEXT)
        print("小壹從抽屜拿出另一份地圖：「只留一份太危險了，這就是要你備份的原因。」")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rescue()
    problems = []
    box, nest = listing("box"), listing("nest")
    if box is None and os.path.isdir(os.path.join("nest", "box")):
        problems.append("box 建到 nest 裡面了：它要和 map.txt 在同一層，用 mv nest/box . 搬出來")
    elif box is None:
        problems.append("還沒有 box 資料夾：用 mkdir 建立")
    else:
        if SILK - box:
            problems.append("box 裡少了 " + str(len(SILK - box)) + " 束絲線")
        if box - SILK:
            problems.append("box 裡放了不是絲線的東西：" + "、".join(sorted(box - SILK)))
    if nest is None:
        problems.append("nest 資料夾不見了：只要搬走絲線、刪掉落葉，nest 要留著")
    else:
        if nest & SILK:
            problems.append("nest 裡還有 " + str(len(nest & SILK)) + " 束絲線沒搬")
        if any(name.endswith(".leaf") for name in nest):
            problems.append("nest 裡還有落葉（.leaf）")
        if WATER - nest:
            problems.append("露水不在 nest 裡：露水要留在 nest")
    if not os.path.isfile("map.txt"):
        problems.append("map.txt 不見了：要用 cp 複製，不是用 mv 搬走")
    elif not os.path.isfile("map.bak"):
        problems.append("還沒有 map.bak：用 cp 複製 map.txt")
    elif sha256_file("map.bak") != sha256_file("map.txt"):
        problems.append("map.bak 和 map.txt 的內容不一樣")
    if problems:
        print("還沒整理好：")
        for problem in problems:
            print("  - " + problem)
        return 1
    state = ("box:" + ",".join(sorted(box)) + "|nest:" + ",".join(sorted(nest))
             + "|map:" + sha256_file("map.bak"))
    if hashlib.sha256((SALT + state).encode("utf-8")).hexdigest() != ANSWER_SHA256:
        print("看起來整理好了，但內容和原本的不一樣。請老師幫你重設這一題。")
        return 1
    key = hashlib.sha256((SALT + ":key:" + state).encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    print(PICTURE, end="")
    print("巢穴煥然一新！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"))
    return 0


raise SystemExit(main())
'''

# 裝進學生的 shell（/etc/profile.d）：rm 要刪這題該留下的東西時直接拒絕，並說明原因。
# 用 command rm 或 /bin/rm 還是刪得掉，刪掉的話 ./check 會放回去。
RM_GUARD = r"""# 第 05 題：絲線、露水和地圖不能用 rm 刪。其他檔案照常刪除。
rm() {
    local arg path lab why
    lab="$HOME/lab/05-organize"
    for arg in "$@"; do
        case "$arg" in -*) continue ;; esac
        path=$(realpath -m -- "$arg")
        why=""
        case "$path" in
            "$lab"/*.silk) why="這是大家吐了好幾天的絲。" ;;
            "$lab"/*.water) why="這是早上才收的露水，要拿來泡茶的。" ;;
            "$lab/map.txt") why="地圖只有這一份，丟了就找不到路了。" ;;
        esac
        if [ -z "$why" ] && [ -d "$path" ]; then
            case "$lab/" in
                "$path"/*) why="整個巢穴都在裡面。" ;;
            esac
            case "$path/" in
                "$lab"/*)
                    if [ -n "$(find "$path" \( -name '*.silk' -o -name '*.water' \) -print -quit)" ]; then
                        why="裡面還有絲線或露水。"
                    fi
                    ;;
            esac
        fi
        if [ -n "$why" ]; then
            echo "小壹攔住你：「$arg 不能刪！$why」" >&2
            echo "這次什麼都沒有刪。要刪的只有落葉（.leaf）。" >&2
            return 1
        fi
    done
    command rm "$@"
}
"""

SILK_KINDS = ("red", "blue", "green", "white", "black", "gold")
LEAF_KINDS = ("apple", "lemon", "orange", "mango")
WATER_KINDS = ("morning", "night", "rain")


def _names(rng, kinds, count, ext):
    names = set()
    while len(names) < count:
        names.add(f"{rng.choice(kinds)}-{rng.randint(1, 99)}.{ext}")
    return sorted(names)


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    silk = _names(rng, SILK_KINDS, rng.randint(8, 12), "silk")
    leaves = _names(rng, LEAF_KINDS, rng.randint(5, 8), "leaf")
    water = _names(rng, WATER_KINDS, rng.randint(3, 5), "water")
    keep = {name: art.item("silk") + f"\n{name}\n" for name in silk}
    keep |= {name: art.item("water") + f"\n{name}\n" for name in water}
    for name, content in keep.items():
        ws.write(f"nest/{name}", content)
    for name in leaves:
        ws.write(f"nest/{name}", art.item("leaf") + f"\n{name}\n")
    map_text = (
        "巢穴地圖\n\n"
        + art.item("map")
        + "\n"
        + "".join(f"第 {i} 排：{rng.choice(['絲', '露', '空'])}\n" for i in range(1, 6))
    )
    ws.write("map.txt", map_text)
    state = (
        "box:"
        + ",".join(silk)
        + "|nest:"
        + ",".join(water)
        + "|map:"
        + hashlib.sha256(map_text.encode("utf-8")).hexdigest()
    )
    salt = format(rng.getrandbits(64), "016x")
    check = (
        CHECK.replace("@SALT@", salt)
        .replace("@ANSWER@", hashlib.sha256((salt + state).encode("utf-8")).hexdigest())
        .replace("@SEALED@", seal(flag, state, salt))
        .replace("@SILK@", repr(json.dumps(silk)))
        .replace("@WATER@", repr(json.dumps(water)))
        .replace("@KEEP@", repr(json.dumps(keep)))
        .replace("@MAP@", repr(map_text))
        .replace("@PICTURE@", repr(art.render(LAB_ID)))
    )
    ws.write("check", check, mode=0o755)
