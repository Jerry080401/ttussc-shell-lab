"""Lab 04: find a hidden file with pwd / cd / ls -a / cat."""

from labctl.labs import art

LAB_ID = "04-hidden-file"
TITLE = "葉子背面的便條"
FLAG = "is1ab{dotfiles_are_just_shy}"

README = """\
# 04 葉子背面的便條

小壹寫了一張便條給你，怕被風吹走，就收在某棵樹的葉子背面。名字以 `.` 開頭的檔案平常看不到，就像藏在葉子背面。

## 你要做的事

走到每一棵樹上找找看，找到便條就讀出來。讀到 `is1ab{...}` 就完成了，把它記下來。

## 提示

- 葉子都長在每棵樹的樹枝 `branch` 上。
- `ls` 有很多選項：`-l` 顯示詳細資料，`-a` 連隱藏檔也列出來，`-t` 依時間排序。
- `cd ..` 回到上一層，`cd ~/lab/04-hidden-file` 回到這一題的起點。
"""

TREES = {"apple-tree": "蘋果樹", "lemon-tree": "檸檬樹", "orange-tree": "橘子樹"}


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    hiding_place = rng.choice(sorted(TREES))
    for tree, name in sorted(TREES.items()):
        ws.write(f"{tree}/sign", art.item("tree") + f"\n這裡是{name}，樹枝上有很多葉子。\n")
        ws.write(f"{tree}/branch/leaf", art.item("leaf") + "\n這是葉子的正面，什麼都沒有。翻到背面看看？\n")
        if tree == hiding_place:
            ws.write(
                f"{tree}/branch/.note",
                "給新朋友：\n找到這裡，表示你已經會看隱藏檔了！\n\n" + art.render(LAB_ID) + f"\nflag：{flag}\n"
                "\nP.S. 巢穴該大掃除了，下一題見。 —— 小壹\n",
            )
        else:
            ws.write(f"{tree}/branch/.water", art.item("water") + "\n葉子背面只有一滴露水，便條不在這裡。\n")
