"""Lab exercises: each lab seeds a student's workspace under ~/lab/<lab-id>/."""

import random
from pathlib import Path

from labctl.labs import (
    lab01_check_in,
    lab02_read_the_manual,
    lab03_paths,
    lab04_hidden_file,
    lab05_organize,
    lab06_find_real_file,
    lab07_archive,
    lab08_grep_log,
    lab09_sort_uniq,
    lab10_signals,
    lab11_chmod,
    lab12_diff_config,
    lab13_git_history,
)
from labctl.labs.flags import derive_seed
from labctl.labs.workspace import DIR_MODE, Workspace

# 題號就是上課做的順序。
LABS = [
    lab01_check_in,
    lab02_read_the_manual,
    lab03_paths,
    lab04_hidden_file,
    lab05_organize,
    lab06_find_real_file,
    lab07_archive,
    lab08_grep_log,
    lab09_sort_uniq,
    lab10_signals,
    lab11_chmod,
    lab12_diff_config,
    lab13_git_history,
]

OVERVIEW = """\
# TTUSSC Linux Lab

每一題一個資料夾，先進資料夾看說明：

    cd ~/lab/01-check-in
    cat README.md

{table}
解開每一題都會得到一個 flag，格式是 `TTUSSC{{...}}`，把它記下來。
flag 是一句和這題重點有關的英文，字和字之間用 `_` 連接。
"""


def build_labs(root, secret, cohort, student_id, round_=1):
    """Create every lab for one student under an empty `root`, returning {lab_id: flag}.

    Flags are one fixed sentence per lab (the same for everyone). The secret only
    decides each student's data.
    """
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"{root} is not empty; refusing to overwrite student work")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(DIR_MODE)
    flags = {}
    for lab in LABS:
        flag = lab.FLAG
        rng = random.Random(derive_seed(secret, cohort, student_id, lab.LAB_ID, round_))
        lab.seed(Workspace(Workspace(root).mkdir(lab.LAB_ID)), flag, rng, student_id)
        flags[lab.LAB_ID] = flag
    table = "".join(f"    {lab.LAB_ID:<20} {lab.TITLE}\n" for lab in LABS)
    Workspace(root).write("README.md", OVERVIEW.format(table=table))
    return flags
