# 開發

## 準備環境

需要 `python3`（含 venv）和 [Terraform](https://developer.hashicorp.com/terraform/install) 1.16.4。ruff 和 shellcheck 裝在專案的虛擬環境裡，版本寫在 `pyproject.toml`：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --group dev
```

每開一個新的終端機，都要先執行 `source .venv/bin/activate`。

## 檢查

| 指令 | 做什麼 |
|---|---|
| `make test` | 測試 |
| `make lint` | ruff、shellcheck、terraform fmt |
| `make fmt` | 自動整理格式 |

防火牆的封包測試需要 `unshare`、`nsenter`、`ip`、`ping` 和 `nft`，缺了會跳過。CI 會用 root 跑。

要改題目的話，請看[題目](docs/LABS.md)。
