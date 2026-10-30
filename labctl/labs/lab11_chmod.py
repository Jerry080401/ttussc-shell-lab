"""Lab 11: the student owns a file without read permission and fixes it with chmod."""

from labctl.labs import art

LAB_ID = "11-chmod"
TITLE = "我有檔案，但我打不開"
FLAG = "TTUSSC{chmod_gave_me_the_key}"

README = """\
# 11 我有檔案，但我打不開

`locked.txt` 明明是你的檔案，`cat locked.txt` 卻說「拒絕不符權限的操作」（英文是 `Permission denied`，權限不足）。

## 你要做的事

1. 用 `ls -l` 看看 `locked.txt` 的權限。
2. 替「檔案擁有者（你自己）」加上讀取權限。
3. 再 `cat locked.txt` 一次。

## 提示

- `ls -l` 最左邊的 `-rw-r--r--` 依序是：擁有者、群組、其他人的讀（r）寫（w）執行（x）。
- `chmod u+r 檔案` 替擁有者（u）加上（+）讀取（r）權限。
- 這題請不要用 `sudo`：練習的是用自己的權限把問題解決。
"""


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    ws.write("locked.txt", "恭喜打開了！\n\n" + art.render(LAB_ID) + f"\nflag：{flag}\n", mode=0o000)
