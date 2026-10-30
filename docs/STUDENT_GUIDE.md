# 學生連線說明

每個人都有一台自己的 Linux（Ubuntu 26.04）。你會先在筆電裝 **NetBird**（讓你的筆電進到課程的私人網路），再用 **SSH** 登入你的 Linux。

需要：自己的筆電（Windows 10／11、macOS 或 Linux），而且可以安裝軟體（有系統管理員權限）。

## 課前準備（在家先做）

### 1. 確認電腦有 ssh

**Windows**：開始 → 輸入 `Windows PowerShell` → 開啟（Windows 內建，不用另外安裝），輸入：

```powershell
ssh -V
```

看到 `OpenSSH_for_Windows_...` 就可以了（Windows 10、11 內建）。
如果出現「無法辨識」：設定 → 系統 → 選用功能 → 新增功能（檢視功能）→ 搜尋 **OpenSSH 用戶端** → 安裝，裝完關掉 Windows PowerShell 再開一次。

**macOS**：開啟「終端機」，輸入 `ssh -V`（內建）。

**Linux**：開終端機輸入 `ssh -V`，沒有的話安裝 `openssh-client`。

### 2. 安裝 NetBird

**Windows**：在 Windows PowerShell 輸入：

```powershell
curl.exe -L -o netbird-installer.exe https://pkgs.netbird.io/windows/x64
.\netbird-installer.exe
```

- 一定要打 `curl.exe`，不能只打 `curl`：Windows PowerShell 裡的 `curl` 是另一個指令（`Invoke-WebRequest`）的別名，會出現「找不到符合參數名稱 'L' 的參數」。
- 第二行會打開安裝程式：跳出「是否允許此 App 變更你的裝置」按「是」，再照畫面按下一步完成。
- 想確認下載到的是官方檔案（可選）：`Get-AuthenticodeSignature .\netbird-installer.exe`，`Status` 要是 `Valid`。

**macOS**：在終端機輸入（依晶片選一行下載）：

```bash
curl -L -o netbird.pkg https://pkgs.netbird.io/macos/arm64   # Apple M 系列晶片
curl -L -o netbird.pkg https://pkgs.netbird.io/macos/amd64   # Intel 晶片
open netbird.pkg
```

**Linux**：

```bash
curl -fsSL https://pkgs.netbird.io/install.sh | sh
```

安裝時會要求系統管理員權限。裝好後**開一個新的 Windows PowerShell 視窗**（macOS／Linux 開新的終端機），輸入：

```powershell
netbird version
```

看到版本號就代表裝好了。如果出現「無法辨識」，確認是不是還在安裝前就開著的舊視窗，關掉再開一個新的。裝好後工作列（或選單列）會出現 NetBird 圖示，**先不要按裡面的 Connect／Login**，上課時照下面的指令加入。

## 上課時

老師會私下給你一張**連線卡**，上面有：註冊碼、你的 Linux 位址、帳號 `student`、密碼。連線卡只給你一個人，不要拍照傳到群組。

### 3. 加入課程網路（每台筆電只做一次）

打開 Windows PowerShell（macOS／Linux 用終端機）。連線卡上印著**你專屬、已經填好的完整指令**，整行複製貼上就好。長得像這樣（下面是範例，每個人的註冊碼都不同）：

```powershell
netbird up --management-url https://netbird.example.com --setup-key 3F2A9C1E-7B4D-4E8A-9C61-2D5B8F0A1E47
```

要自己打的話，只換掉最後那一串註冊碼。**不要打 `<`、`>` 這類符號**，Windows PowerShell 會出現「'<' 運算子保留供未來使用」的錯誤。

- 出現權限錯誤時：Windows 改用「以系統管理員身分執行」開 Windows PowerShell，Linux 在指令前面加 `sudo`。
- 確認有連上：`netbird status`，看到 `Management: Connected` 就好了。
- 註冊碼**只能用一次**，而且有期限。換電腦或重灌要找老師拿新的。

### 4. 登入你的 Linux

```powershell
ssh student@100.92.10.21
```

上面是範例，`@` 後面換成連線卡上你的 Linux 位址（一樣整行複製最保險）。

1. 第一次連線會問 `Are you sure you want to continue connecting (yes/no)?`，輸入 `yes`。
2. 輸入密碼。**打字時畫面不會顯示任何東西，這是正常的**，打完按 Enter。
3. 看到 `student@lab-studentXX:~$` 就登入成功了。題目在 `~/lab`：輸入 `cat ~/lab/README.md` 開始。

離開：輸入 `exit`。下次上課只要做第 4 步（NetBird 會自己連上，沒連上就執行 `netbird up`）。

## 常見問題

| 狀況 | 怎麼辦 |
|---|---|
| 輸入密碼看不到字 | 正常，直接打完按 Enter |
| `Connection timed out`、連不上 | 先 `netbird status` 看有沒有 `Connected`，沒有就執行 `netbird up` |
| `Permission denied` | 密碼打錯，注意大小寫。連續錯很多次請找老師 |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | 你的 Linux 被老師重建過。找老師確認，**不要自己隨便刪設定** |
| 中文變成亂碼 | Windows 請用「Windows 終端機」（Windows 11 內建）開 Windows PowerShell |
| 想看英文原文的說明 | 在你的 Linux 裡輸入 `export LANG=C.UTF-8 LANGUAGE=` |

你的 Linux 裡可以用 `sudo`（輸入自己的密碼）。如果把系統弄壞了也沒關係，告訴老師，老師可以幫你重建一台新的。
