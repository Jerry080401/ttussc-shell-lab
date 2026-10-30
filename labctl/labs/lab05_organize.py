"""Lab 05: mkdir, mv, rm, cp with wildcards. ./check verifies the final layout."""

import hashlib
import json

from labctl.labs import art
from labctl.labs.answer_check import seal

LAB_ID = "05-organize"
TITLE = "整理倉庫"
FLAG = "TTUSSC{rm_has_no_recycle_bin}"

README = """\
# 05 整理倉庫

碼頭 `dock/` 堆滿了東西：魚（`.fish`）、垃圾（`.trash`）和冰塊（`.ice`）。請幫企鵝整理好。

## 你要做的事

1. 建立一個資料夾 `fridge`（和 `dock` 放在同一層）。
2. 把 `dock` 裡**所有的魚**搬進 `fridge`。
3. 把 `dock` 裡**所有的垃圾**刪掉。冰塊要留在 `dock`。
4. 把 `map.txt` **複製**一份，取名 `map.bak`。
5. 執行 `./check`，全部做對就會顯示 flag，哪裡不對它會告訴你。

## 提示

- `mkdir 名稱` 建立資料夾、`mv 來源 目的地` 搬移、`rm 檔案` 刪除、`cp 來源 新檔名` 複製。
- 萬用字元 `*` 代表「任意長度的任何字」：`dock/*.fish` 就是 dock 裡所有 `.fish` 結尾的檔案。
- **`rm` 刪掉的檔案不會進資源回收筒**。刪之前先用 `ls dock/*.trash` 確認會刪到哪些。
"""

CHECK = r'''#!/usr/bin/env python3
"""檢查倉庫整理好了沒：./check"""
import hashlib
import json
import os
import sys

SALT = "@SALT@"
ANSWER_SHA256 = "@ANSWER@"
SEALED_FLAG = "@SEALED@"
PICTURE = @PICTURE@
FISH = set(json.loads(@FISH@))
ICE = set(json.loads(@ICE@))


def listing(path):
    return set(os.listdir(path)) if os.path.isdir(path) else None


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    problems = []
    fridge, dock = listing("fridge"), listing("dock")
    if fridge is None and os.path.isdir(os.path.join("dock", "fridge")):
        problems.append("fridge 建到 dock 裡面了：它要和 dock 在同一層，用 mv dock/fridge . 搬出來")
    elif fridge is None:
        problems.append("還沒有 fridge 資料夾：用 mkdir 建立")
    else:
        if FISH - fridge:
            problems.append("fridge 裡少了 " + str(len(FISH - fridge)) + " 條魚")
        if fridge - FISH:
            problems.append("fridge 裡放了不是魚的東西：" + "、".join(sorted(fridge - FISH)))
    if dock is None:
        problems.append("dock 資料夾不見了：只要搬走魚、刪掉垃圾，dock 要留著")
    else:
        if dock & FISH:
            problems.append("dock 裡還有 " + str(len(dock & FISH)) + " 條魚沒搬")
        if any(name.endswith(".trash") for name in dock):
            problems.append("dock 裡還有垃圾（.trash）")
        if ICE - dock:
            problems.append("冰塊不見了！只要刪 .trash，冰塊要留在 dock")
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
    state = ("fridge:" + ",".join(sorted(fridge)) + "|dock:" + ",".join(sorted(dock))
             + "|map:" + sha256_file("map.bak"))
    if hashlib.sha256((SALT + state).encode("utf-8")).hexdigest() != ANSWER_SHA256:
        print("看起來整理好了，但內容和原本的不一樣。請老師幫你重設這一題。")
        return 1
    key = hashlib.sha256((SALT + ":key:" + state).encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    print(PICTURE, end="")
    print("整理完成！flag：" + bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8"))
    return 0


raise SystemExit(main())
'''

FISH_KINDS = ("salmon", "cod", "tuna", "mackerel", "sardine", "herring")
TRASH_KINDS = ("can", "bottle", "bag", "net")
ICE_KINDS = ("block", "cube", "slab")


def _names(rng, kinds, count, ext):
    names = set()
    while len(names) < count:
        names.add(f"{rng.choice(kinds)}-{rng.randint(1, 99)}.{ext}")
    return sorted(names)


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    fish = _names(rng, FISH_KINDS, rng.randint(8, 12), "fish")
    trash = _names(rng, TRASH_KINDS, rng.randint(5, 8), "trash")
    ice = _names(rng, ICE_KINDS, rng.randint(3, 5), "ice")
    for name in fish + trash + ice:
        ws.write(f"dock/{name}", f"{name}\n")
    map_text = "倉庫地圖\n" + "".join(f"第 {i} 排：{rng.choice(['魚', '冰', '空'])}\n" for i in range(1, 6))
    ws.write("map.txt", map_text)
    state = (
        "fridge:"
        + ",".join(fish)
        + "|dock:"
        + ",".join(ice)
        + "|map:"
        + hashlib.sha256(map_text.encode("utf-8")).hexdigest()
    )
    salt = format(rng.getrandbits(64), "016x")
    check = (
        CHECK.replace("@SALT@", salt)
        .replace("@ANSWER@", hashlib.sha256((salt + state).encode("utf-8")).hexdigest())
        .replace("@SEALED@", seal(flag, state, salt))
        .replace("@FISH@", repr(json.dumps(fish)))
        .replace("@ICE@", repr(json.dumps(ice)))
        .replace("@PICTURE@", repr(art.render(LAB_ID)))
    )
    ws.write("check", check, mode=0o755)
