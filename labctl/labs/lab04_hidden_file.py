"""Lab 04: find a hidden file with pwd / cd / ls -a / cat."""

from labctl.labs import art

LAB_ID = "04-hidden-file"
TITLE = "企鵝把檔案藏起來了"
FLAG = "TTUSSC{dotfiles_are_just_shy}"

README = """\
# 04 企鵝把檔案藏起來了

企鵝 Tux 把日記藏在這個資料夾裡的某個地方，還特地取了一個「一般 ls 看不到」的名字。

## 你要做的事

1. 用 `pwd` 確認你現在在哪裡。
2. 用 `ls` 看看有哪些資料夾，再用 `cd` 走進去找。
3. 找到日記後，用 `cat` 讀出內容。

## 提示

- 名字以 `.` 開頭的檔案是「隱藏檔」，要用 `ls -a` 才看得到。
- `cd ..` 回到上一層，`cd ~/lab/04-hidden-file` 回到這一題的起點。

讀到 `TTUSSC{...}` 就完成了，把它記下來。
"""

AREAS = {
    "glacier": ("冰河", "cave"),
    "iceberg": ("冰山", "tunnel"),
    "snowfield": ("雪原", "igloo"),
}


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    hiding_place = rng.choice(sorted(AREAS))
    for area, (name, nook) in sorted(AREAS.items()):
        ws.write(f"{area}/note.txt", f"這裡是{name}。風很大，什麼都沒有。\n")
        ws.write(f"{area}/fish.txt", "".join(f"魚 #{rng.randint(1, 99)}\n" for _ in range(rng.randint(3, 6))))
        ws.write(f"{area}/{nook}/rock.txt", "只是一塊石頭。\n")
        if area == hiding_place:
            ws.write(
                f"{area}/{nook}/.diary",
                "親愛的日記：\n今天又偷吃了三條魚，沒有人發現。\n\n" + art.render(LAB_ID) + f"\n我的 flag 是 {flag}\n",
            )
        else:
            ws.write(f"{area}/{nook}/.footprints", "有企鵝的腳印……但日記不在這裡。\n")
