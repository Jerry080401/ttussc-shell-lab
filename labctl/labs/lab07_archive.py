"""Lab 07: identify an unknown file with `file`, then tar and gunzip it."""

import gzip
import io
import tarfile

from labctl.labs import art

LAB_ID = "07-archive"
TITLE = "壓縮包裡還有一層"
FLAG = "TTUSSC{never_trust_a_file_extension}"

README = """\
# 07 壓縮包裡還有一層

有人送企鵝一個禮物 `gift.bin`，看不出來是什麼格式，直接 `cat` 只會看到亂碼。

## 你要做的事

1. 用 `file gift.bin` 查出它到底是什麼。
2. 把它解開，看看裡面有什麼。
3. 裡面還包著一層，繼續解開，直到讀到 flag。

## 提示

- `.tar.gz`（gzip 壓縮的 tar）可以用 `tar xzf 檔案` 解開，副檔名不對也沒關係。
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
        "最裡面的紙條寫著：\n\n" + art.render(LAB_ID) + f"\nflag：{flag}\n"
        "\nP.S. 用 ls -l 看看這份禮物是幾月幾號幾點包好的。\n"
    )
    inner = gzip.compress(note.encode("utf-8"), mtime=0)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        _add(tar, "gift", mode=0o755)
        _add(
            tar,
            "gift/card.txt",
            ("祝你生日快樂！你的幸運數字是 6767。\n唸出來的時候，兩手記得一上一下。\n禮物在 inner.gz 裡。\n").encode(),
        )
        _add(tar, "gift/inner.gz", inner)
    ws.write("gift.bin", gzip.compress(buffer.getvalue(), mtime=0))
