"""Lab 13: a deleted password is still in the git history."""

import os
import subprocess

from labctl.labs import art

LAB_ID = "13-git-history"
TITLE = "不小心寫下的密碼"
FLAG = "is1ab{git_never_forgets}"

README = """\
# 13 不小心寫下的密碼

小壹在 `notes/` 裡用 Git 寫接待筆記，有一天順手把點心櫃的密碼也寫了進去。隔天發現不對，趕快把那個檔案刪掉，以為這樣就沒事了。
可是 Git 會記得每一次提交（commit）的內容。點心櫃的密碼就是 flag。

## 你要做的事

1. `cd notes`，用 `git log` 看看有哪些提交。
2. 找出「刪掉之前」的那一次提交，看它的內容。

## 提示

- `git log --oneline` 一行列出一個提交，前面那串是提交編號。
- `git show 提交編號` 顯示那次提交改了什麼。
- `git log -p` 會把每次提交的變更一起列出來。
"""

COMMITS = [
    ("2026-09-01T21:00:00+08:00", "開始寫接待筆記", {"notes.txt": "9/1 今天有新朋友來報到，有點緊張，但很認真。\n"}),
    # 內容要夠長、有重複，zlib 才會真的壓縮。太短會原文存進 .git/objects，grep -ra 就找得到。
    (
        "2026-09-02T21:10:00+08:00",
        "記下點心櫃密碼",
        {
            "password.txt": "點心櫃的密碼：\n\n{picture}\nflag：{flag}\n"
            + "這是祕密，不要告訴別人。\n" * 6
            + "—— 小壹\n"
        },
    ),
    ("2026-09-03T08:05:00+08:00", "糟糕，密碼不該寫在這裡", {"password.txt": None}),
    (
        "2026-09-03T21:20:00+08:00",
        "第三天",
        {"notes.txt": "9/1 今天有新朋友來報到，有點緊張，但很認真。\n9/3 新朋友會用 man 了。\n"},
    ),
    (
        "2026-09-04T21:30:00+08:00",
        "第四天",
        {"notes.txt": "9/1 今天有新朋友來報到，有點緊張，但很認真。\n9/3 新朋友會用 man 了。\n9/4 網補好了一大片。\n"},
    ),
]


def _git_env(date):
    # 不讀老師電腦上的 git 設定（簽章、使用者名稱、hooks），確保每次產生的歷史完全相同。
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "小壹",
        "GIT_AUTHOR_EMAIL": "xiaoyi@is1ab.invalid",
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_NAME": "小壹",
        "GIT_COMMITTER_EMAIL": "xiaoyi@is1ab.invalid",
        "GIT_COMMITTER_DATE": date,
    }


def _git(repo, date, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        env=_git_env(date),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    repo = ws.mkdir("notes")
    _git(repo, COMMITS[0][0], "init", "-q", "-b", "main", "--template=")
    for date, message, files in COMMITS:
        for name, content in files.items():
            if content is None:
                _git(repo, date, "rm", "-q", name)
            else:
                ws.write(f"notes/{name}", content.format(flag=flag, picture=art.render(LAB_ID)))
                _git(repo, date, "add", name)
        _git(repo, date, "commit", "-q", "-m", message)
