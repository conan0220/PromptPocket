# PromptPocket

這個專案用本機的 `Qwen3.5-9B-Q4_K_M.gguf` 模型搭配 `llama.cpp` 執行推論。

目前模型檔位置：

```text
./models/Qwen3.5-9B-Q4_K_M.gguf
```

## Quick Start

### 1. 安裝 llama.

官方安裝文件：

- https://github.com/ggml-org/llama.cpp/blob/master/docs/install.md

安裝完成後，確認下面指令可在終端機使用：

- `llama-cli`
- `llama-server`

可用下面指令確認：

```powershell
llama-server --version
llama-cli --version
```

### 2. 建立 Python venv

在專案根目錄執行：

```powershell
python -m venv .venv
```

### 3. 進入 venv

依你使用的 terminal 不同，啟用方式如下。

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Command Prompt (`cmd.exe`):

```bat
.\.venv\Scripts\activate.bat
```

Git Bash:

```bash
source .venv/Scripts/activate
```

啟用後，終端機前面通常會出現 `(.venv)`。

### 4. 安裝 Python 套件

```powershell
python -m pip install --upgrade pip
python -m pip install openai PySide6 keyboard pyperclip pywin32 huggingface_hub hf_transfer
```

### 5. 下載模型

先安裝 Hugging Face CLI 後，下載模型到 `./models`：

```powershell
python -m hf download unsloth/Qwen3.5-9B-GGUF --include "Qwen3.5-9B-Q4_K_M.gguf" --local-dir ./models
```

如果你的環境已經能直接用 `hf` 指令，也可以這樣：

```powershell
hf download unsloth/Qwen3.5-9B-GGUF --include "Qwen3.5-9B-Q4_K_M.gguf" --local-dir ./models
```

下載完成後，模型檔應該會在：

```text
./models/Qwen3.5-9B-Q4_K_M.gguf
```

### 6. 啟動背景 AI 工具

```powershell
python .\ai_stack_start.py
```

這個指令會自動：

- 啟動 `llama-server`
- 啟動背景 manager
- 啟動快捷鍵小視窗

### 7. 實際使用

1. 先切到任何一個可輸入文字的地方，例如瀏覽器輸入框、記事本、IDE 編輯器
2. 按 `Ctrl+Space` 打開小視窗
3. 在 Prompt 輸入框輸入需求，例如：

```text
我想要知道目前的路徑下有哪些檔案(powershell)
```

或：

```text
給我 1000 字的小作文，題目是「我的家鄉」
```

4. 按 `生成`
5. 等待模型輸出完成
6. 按 `貼上`
7. 內容會回貼到你原本的輸入框

補充：

- `Ctrl+Enter`：在小視窗內送出生成
- `Esc`：關閉小視窗
- 打開小視窗的快捷鍵目前是 `Ctrl+Space`，不是 `Ctrl+Enter`

## 直接在終端機聊天

```bash
llama-cli -m ./models/Qwen3.5-9B-Q4_K_M.gguf --ctx-size 16384 -cnv
```

## 啟動本機 API 服務

```bash
llama-server -m ./models/Qwen3.5-9B-Q4_K_M.gguf --ctx-size 16384 --port 8080
```

啟動後，API 位址通常是：

```text
http://localhost:8080/v1
```

## 背景程式管理

### 啟動或重啟背景程式

```powershell
python .\ai_stack_start.py
```

### 停止背景程式

```powershell
python .\ai_stack_stop.py
```

### 查詢目前狀態

```powershell
python .\ai_stack_status.py
```

注意：

- `Ctrl+Space` 在部分 Windows 輸入法環境可能衝突；若有衝突，可把 [`ai_hotkey_app.py`](/c:/repos/local_ai/ai_hotkey_app.py) 裡的 `hotkey` 改成別組快捷鍵。
- `貼上` 依賴 Windows 焦點切換；大多數文字輸入框可正常工作，但少數高權限或特殊 UI 程式可能無法直接貼入。
- 狀態資訊會寫在 [.runtime/ai_stack.json](/c:/repos/local_ai/.runtime/ai_stack.json)。

## 備註

- `Q4_K_M` 是量化後的 GGUF 模型，適合在本機資源有限的情況下使用。
- `--ctx-size 16384` 會增加記憶體使用量，如果機器不夠大，可以改小。
- 第一次載入模型可能會比較久，屬於正常現象。
