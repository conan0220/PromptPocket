# PromptPocket

這個專案預設使用本機的 `Qwen3.5-9B-Q4_K_M.gguf` 模型，搭配 `llama.cpp` 執行推論。

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

### 2. 確認已安裝 Python

請先確認電腦已安裝 Python，並且 `python` 指令可用。

可先在專案根目錄或任意 terminal 視窗執行：

```powershell
python --version
```

如果能看到版本號，例如 `Python 3.11.x`，再繼續下一步。

### 3. 建立 Python venv

在專案根目錄執行：

```powershell
python -m venv .venv
```

### 4. 進入 venv

依你使用的 terminal 不同，啟用方式如下。

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Command Prompt (`cmd.exe`):

```bat
.\.venv\Scripts\activate.bat
```

macOS / Linux:

```bash
source .venv/bin/activate
```

啟用後，終端機前面通常會出現 `(.venv)`。

### 5. 安裝 Python 套件

```powershell
python -m pip install --upgrade pip
python -m pip install openai PySide6 keyboard pyperclip pywin32 huggingface_hub hf_transfer
```

### 6. 下載模型

下載模型到 `./models`：

```powershell
hf download unsloth/Qwen3.5-9B-GGUF --include "Qwen3.5-9B-Q4_K_M.gguf" --local-dir ./models
```

下載完成後，模型檔應該會在：

```text
./models/Qwen3.5-9B-Q4_K_M.gguf
```

### 7. 啟動背景 AI 工具

```powershell
python .\ai_stack_start.py
```

這個指令會自動：

- 啟動 `llama-server`
- 啟動背景 manager
- 啟動快捷鍵小視窗

### 8. 實際使用

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

4. 如果想看思考過程，可以勾選 `Thinking` (注意有些模型沒有這個模式)
5. 按 `Enter` 直接生成
6. 等待模型輸出完成
7. 按 `貼上` 或按 `Ctrl+P`
8. 內容會回貼到你原本的輸入框

補充：

- `Thinking`：顯示額外的 Thinking 輸出框
- `Enter`：在小視窗內直接生成
- `Shift+Enter`：在 Prompt 輸入框內換行
- `Ctrl+P`：貼上目前輸出結果
- `Ctrl+Space`：打開或隱藏小視窗

## 套用新模型

### 設定模型名稱

程式會讀取專案根目錄下的 `config.json`。

例如：

```json
{
  "model": "Qwen3.5-9B",
  "model_path": "models/Qwen3.5-9B-Q4_K_M.gguf"
}
```

預設模型是 `Qwen3.5-9B`，對應的 GGUF 檔案是 `models/Qwen3.5-9B-Q4_K_M.gguf`。
如果你要改模型，請同時修改 `config.json` 裡的 `model` 和 `model_path`。
修改後請重新執行 `python .\ai_stack_start.py`。


### 如果要下載新模型

如果你要改用新的 GGUF 模型，建議先去 Hugging Face 網站找模型：

- 模型首頁：https://huggingface.co/models
- GGUF 作者頁常見例子：https://huggingface.co/bartowski

流程如下。

1. 先停止目前背景程式：

```powershell
python .\ai_stack_stop.py
```

2. 打開 Hugging Face 網站，搜尋你想要的模型。

3. 進入模型頁面後，確認兩件事：

- repo 名稱
  - 例如：`unsloth/gpt-oss-20b-GGUF`
- 檔案名稱
  - 到模型頁面的 `Files and versions` 分頁找 GGUF 檔案
  - 例如：`gpt-oss-20b-Q4_K_M.gguf`

4. 根據頁面上的資訊，組出下載指令。

如果你知道完整檔名，可以直接寫完整名稱：

```powershell
hf download unsloth/gpt-oss-20b-GGUF --include "gpt-oss-20b-Q4_K_M.gguf" --local-dir ./models
```

如果你只想抓某一種量化版本，也可以用萬用字元，例如：

```powershell
hf download unsloth/gpt-oss-20b-GGUF --include "*Q4_K_M.gguf" --local-dir ./models
```

這裡的意思是：

- `unsloth/gpt-oss-20b-GGUF` 是 Hugging Face repo 名稱
- `*Q4_K_M.gguf` 代表抓所有檔名尾巴符合 `Q4_K_M.gguf` 的 GGUF 檔案
- `--local-dir ./models` 代表下載到專案的 `models/` 資料夾

5. 確認下載後的 GGUF 檔案路徑，例如：

```text
models/gpt-oss-20b-Q4_K_M.gguf
```

6. 修改 `config.json`：

```json
{
  "model": "gpt-oss-9B",  
  "model_path": "models/gpt-oss-20b-Q4_K_M.gguf"
}
```

7. 重新啟動背景程式：

```powershell
python .\ai_stack_start.py
```

8. 用下面指令確認目前載入的是不是新模型：

```powershell
python .\ai_stack_status.py
```

重點：

- `model` 是 API / UI 顯示的模型名稱，可以自己命名
- `model_path` 是 `llama-server` 實際載入的 GGUF 檔案路徑，必須和實際檔案一致
- `Files and versions` 是最重要的地方，因為你要從那裡看 repo 裡到底有哪些 GGUF 檔名





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

- `Ctrl+Space` 在部分 Windows 輸入法環境可能衝突；若有衝突，可把 [`ai_hotkey_app.py`](/c:/repos/PromptPocket/ai_hotkey_app.py) 裡的 `hotkey` 改成別組快捷鍵。
- `貼上` 依賴 Windows 焦點切換；大多數文字輸入框可正常工作，但少數高權限或特殊 UI 程式可能無法直接貼入。
- 狀態資訊會寫在 [.runtime/ai_stack.json](/c:/repos/PromptPocket/.runtime/ai_stack.json)。

## 備註

- `Q4_K_M` 是量化後的 GGUF 模型，適合在本機資源有限的情況下使用。
- `--ctx-size 16384` 會增加記憶體使用量，如果機器不夠大，可以改小。
- 第一次載入模型可能會比較久，屬於正常現象。






