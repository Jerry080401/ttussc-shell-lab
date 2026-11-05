"""Lab 07: identify an unknown file with `file`, then tar and gunzip it."""

import gzip
import io
import tarfile

from labctl.labs import art

LAB_ID = "07-archive"
TITLE = "蜜蜂的包裹"
FLAG = "never_trust_a_file_extension"

README = """\
# 07 蜜蜂的包裹

隔壁花園的蜜蜂聽說你來了，寄來一個包了好幾層的包裹 `package.bin`。看不出來是什麼格式，直接 `cat` 只會看到亂碼。小壹請你幫忙拆開。

## 你要做的事

查出它到底是什麼，然後一層一層解開，直到讀到 flag。

## 提示

- `file 檔案` 會告訴你檔案其實是什麼，不看副檔名。
- `.tar.gz`（gzip 壓縮的 tar）要用 `tar` 解開，副檔名不對也沒關係。`tar` 的選項可以連著寫：`x` 解開、`t` 列出內容、`z` 處理 gzip、`f` 後面接檔名。例如 `tar tzf 檔案` 會列出裡面有什麼。
- 單獨用 gzip 壓縮的檔案（`.gz`）用 `gunzip 檔案.gz` 解開。
- 每解開一層，就用 `ls` 和 `file` 看看得到了什麼。
"""

FIXED_MTIME = 1780783620  # 台北時間 2026-06-07 06:07，6 7 的梗。固定時間也讓每次產生的檔案完全相同


def _add(tar, name, data=None, mode=0o644):
    info = tarfile.TarInfo(name)
    info.mtime = FIXED_MTIME
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = mode
    if data is None:
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    else:
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))


def seed(ws, flag, rng, student_id):
    ws.write("README.md", README)
    note = (
        "最裡面的卡片寫著：\n\n" + art.render(LAB_ID) + f"\nflag：{flag}\n"
        "\nP.S. 用 ls -l 看看這個包裹是幾月幾號幾點包好的。\n"
    )
    inner = gzip.compress(note.encode("utf-8"), mtime=0)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        _add(tar, "package", mode=0o755)
        _add(
            tar,
            "package/card.txt",
            (
                "我是隔壁花園的蜜蜂，歡迎你搬來！\n你的幸運數字是 6767。唸出來的時候，兩隻前腳記得一上一下。\n賀禮在 inner.gz 裡。\n"
            ).encode(),
        )
        _add(tar, "package/inner.gz", inner)
    ws.write("package.bin", gzip.compress(buffer.getvalue(), mtime=0))
