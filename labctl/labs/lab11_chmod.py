"""Lab 11: the student owns a file without read permission and fixes it with chmod."""

from labctl.labs import art

LAB_ID = "11-chmod"
TITLE = "打不開的食譜"
FLAG = "is1ab{chmod_gave_me_the_key}"

README = """\
# 11 打不開的食譜

小壹送你一份露水茶食譜 `locked.txt`。它明明是你的檔案，`cat locked.txt` 卻說「拒絕不符權限的操作」（英文是 `Permission denied`，權限不足）。

## 你要做的事

查出它為什麼打不開，只替自己打開需要的權限，然後讀出食譜。

## 提示

- `ls -l` 最左邊的 `-rw-r--r--` 依序是：擁有者、群組、其他人的讀（r）寫（w）執行（x）。
- `chmod 對象+權限 檔案` 加上權限，`-` 是拿掉。對象有 `u`（擁有者）、`g`（群組）、`o`（其他人），權限有 `r`、`w`、`x`。例如 `chmod g+w 檔案` 是替群組加上寫入權限。
- 這題請不要用 `sudo`：練習的是用自己的權限把問題解決。
- 順帶一提，別養成 `chmod 777` 的習慣：那會讓所有人都能改你的檔案，需要什麼權限就開什麼。
"""


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    ws.write(
        "locked.txt",
        "露水茶食譜：清晨的露水三滴，慢慢煮開。\n\n" + art.render(LAB_ID) + f"\nflag：{flag}\n",
        mode=0o000,
    )
