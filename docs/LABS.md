# 題目

13 題命令列練習，程式在 `labctl/labs/`。題號就是上課的順序，章節順序參考 pwn.college 的 Linux Luminarium，每章講完就做那一章的題目（[簡報](https://canva.link/ebc3teparl7gopj)）。

| 題號 | 章節 | 題目 | 練習的指令 | 怎麼算解開 |
|---|---|---|---|---|
| 01 | 環境準備 | 報到 | `whoami`、`hostname`、參數 | 把帳號和主機名稱交給 `check` |
| 02 | 環境準備 | 看說明書 | `--help`、`man`、長短選項 | 從 man page 找到頻道，用 `radio` 調頻並解碼 |
| 03 | 路徑與目錄 | 迷宮裡的門 | `pwd`、`cd`、絕對和相對路徑 | 站在 `/tmp`，用絕對路徑呼叫迷宮深處的門 |
| 04 | 檔案操作 | 企鵝把檔案藏起來了 | `ls -a`、`cat` | 找到隱藏檔 |
| 05 | 檔案操作 | 整理倉庫 | `mkdir`、`mv`、`rm`、`cp`、萬用字元 | 整理好之後用 `check` 檢查 |
| 06 | 檔案操作 | 倉庫裡只有一份真的 | `find`、檔名和大小條件 | 找到符合線索的檔案 |
| 07 | 檔案操作 | 壓縮包裡還有一層 | `file`、`tar`、`gzip` | 一層一層解開壓縮檔 |
| 08 | 管線與重導向 | 企鵝只登入成功一次 | `grep`、`less`、pipe | 在 log 裡找出唯一一次成功的登入 |
| 09 | 資料處理 | 誰偷吃最多條魚 | `cut`、`sort`、`uniq -c`、pipe | 算出答案交給 `check` |
| 10 | 行程管理 | 叫醒企鵝 | `&`、`ps`、`kill -USR1` | 對背景的程式送 USR1 |
| 11 | 使用者與權限 | 我有檔案，但我打不開 | `ls -l`、`chmod` | 替自己的檔案加上讀取權限 |
| 12 | 加分 | 設定檔差在哪 | `diff`、文字編輯器 | 改好設定檔，用 `check` 檢查 |
| 13 | 加分 | 被刪掉的日記 | `git log`、`git show` | 在這題的 git repo 裡找到舊版本 |

## 學生拿到什麼

每個學生的 `~/lab/` 有一份總覽 `README.md`，每題一個資料夾，裡面的 `README.md` 寫故事、要做的事和提示。檔名用英文，因為學生在終端機裡不一定打得出中文。

解開會拿到 flag，格式是 `TTUSSC{...}`，內容是一句跟這題有關的英文。第 1、2、3、5、9、10、12 題的 flag 是用正確答案推出來的金鑰加密的，要照題目用對方法跑附的程式才會印出來，直接 `grep` 找不到。

除了第 8 題，答對時會一起印出一張點陣圖，左邊是照社團 logo 描的牛仔帽企鵝，右邊是跟這題有關的道具（`labctl/labs/art.py`）。第 8 題的 flag 寫在 log 的其中一行，放不下圖。第 6 題每個箱子都印著同一張圖，不然 grep 圖案就找得到真的箱子。

flag 放在學生自己的 VM 裡，有心的學生可以去讀 `check` 的原始碼。這套題目是給上課練習用的，不適合拿來比賽。

## 答案

每題的 flag 全班一樣，`python3 -m labctl labs flags` 也印得出來。

| 題號 | 題目 | flag |
|---|---|---|
| 01 | 報到 | `TTUSSC{whoami_is_a_deep_question}` |
| 02 | 看說明書 | `TTUSSC{always_read_the_manual}` |
| 03 | 迷宮裡的門 | `TTUSSC{absolute_paths_never_get_lost}` |
| 04 | 企鵝把檔案藏起來了 | `TTUSSC{dotfiles_are_just_shy}` |
| 05 | 整理倉庫 | `TTUSSC{rm_has_no_recycle_bin}` |
| 06 | 倉庫裡只有一份真的 | `TTUSSC{one_real_box_among_many_fakes}` |
| 07 | 壓縮包裡還有一層 | `TTUSSC{never_trust_a_file_extension}` |
| 08 | 企鵝只登入成功一次 | `TTUSSC{grep_finds_the_needle}` |
| 09 | 誰偷吃最多條魚 | `TTUSSC{sort_before_you_uniq}` |
| 10 | 叫醒企鵝 | `TTUSSC{kill_just_sends_a_signal}` |
| 11 | 我有檔案，但我打不開 | `TTUSSC{chmod_gave_me_the_key}` |
| 12 | 設定檔差在哪 | `TTUSSC{spot_the_difference_with_diff}` |
| 13 | 被刪掉的日記 | `TTUSSC{git_never_forgets}` |

## 題目資料

每個學生拿到的資料不一樣，例如頻道、檔案大小、名字，但 flag 一樣。資料的亂數種子由 `.env` 的 `LAB_SECRET` 算出來：`HMAC-SHA256(secret, "seed", cohort, student, lab, round)`。同一個學生每次產生的內容完全相同，加 `--round 2` 會換一輪新的資料。

```bash
python3 -m labctl labs build student01 --out /tmp/lab-student01   # 目標資料夾要是空的
python3 -m labctl labs flags
```

第 6、8 題的假 flag 是 16 位十六進位的亂碼，真的是一句話，所以 `grep TTUSSC` 一眼就看得出哪個是真的。這是刻意保留的，上課時請學生照題目要求用 `find` 和 `grep` 的條件找。

## 改題目

| 檔案 | 內容 |
|---|---|
| `labctl/labs/labNN_*.py` | 一題一個模組：`LAB_ID`、`TITLE`、`FLAG`、說明 `README` 和產生資料的 `seed()` |
| `labctl/labs/__init__.py` | 題目順序和總覽說明 |
| `labctl/labs/workspace.py` | 只能寫進那一題的資料夾，檔案權限寫死，不受 umask 影響 |
| `labctl/labs/flags.py` | 用 `LAB_SECRET` 推出資料的亂數種子 |
| `labctl/labs/art.py` | 答對時印出的點陣圖 |
| `labctl/labs/answer_check.py` | 加密 flag 的 `seal()`，還有第 1、9、12 題共用的 `check` |

改故事或提示，就改模組裡的 `README` 字串，改完跑 `make test`。`seed()` 只能透過 `ws` 寫進自己的資料夾，也不連網路。第 13 題產生時會呼叫 `git`，所以實驗主機要有 git，`make host` 會裝。

## 重設

`make reset-lab STUDENT=student05 LAB=05-organize` 只重做那一題，舊的資料夾會改名成 `~/lab/.05-organize.old-時間` 留著。整份 `~/lab` 只有空的時候才會放題目，不會蓋掉學生的作業。放題目是用學生自己的身分寫檔案，所以學生在 `~/lab` 裡做的連結指不到系統檔案。
