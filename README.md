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

### 6. 啟動背景 AI 工具

```powershell
python .\promptpocket.py --start
```

這個指令會自動：

- 讀取 `config.json`
- 檢查 `model_path` 指向的模型檔是否存在
- 若本機缺模型，根據 `model_repo` 自動從 Hugging Face 下載
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
  "model_path": "models/Qwen3.5-9B-Q4_K_M.gguf",
  "model_repo": "unsloth/Qwen3.5-9B-GGUF"
}
```

預設模型是 `Qwen3.5-9B`，對應的 GGUF 檔案是 `models/Qwen3.5-9B-Q4_K_M.gguf`。
如果你要改模型，請同時修改 `config.json` 裡的 `model`、`model_path` 和 `model_repo`。
修改後請重新執行 `python .\promptpocket.py --start`。


### 切換新模型

修改 `config.json`：

```json
{
  "model": "gpt-oss-9B",
  "model_path": "models/gpt-oss-20b-Q4_K_M.gguf",
  "model_repo": "unsloth/gpt-oss-20b-GGUF"
}
```

然後重新啟動背景程式：

```powershell
python .\promptpocket.py --start
```

如果你要確認目前載入的是不是新模型：

```powershell
python .\promptpocket.py --status
```

重點：

- `model` 是 API / UI 顯示的模型名稱，可以自己命名
- `model_path` 是 `llama-server` 實際載入的 GGUF 檔案路徑，必須和實際檔案一致
- `model_repo` 是 Hugging Face 的 repo 名稱；如果本機缺少 `model_path` 指向的檔案，`python .\promptpocket.py --start` 會用它自動下載

### 調整 System Prompt

系統提示詞放在專案根目錄下的 [system_prompt.txt](/c:/repos/PromptPocket/system_prompt.txt)。

你可以直接用純文字編輯這個檔案，不需要處理 JSON 跳脫字元。
修改完成後，重新執行：

```powershell
python .\promptpocket.py --start
```

如果 `system_prompt.txt` 不存在或內容讀取失敗，程式會自動退回內建的預設 prompt。

### 推薦模型

下面是幾組適合本專案的 `config.json` 範例。

#### 1. gpt-oss-20b

適合：想要接近 20B 規模、可在本地跑的推理模型

```json
{
  "model": "gpt-oss-20b",
  "model_path": "models/gpt-oss-20b-Q4_K_M.gguf",
  "model_repo": "unsloth/gpt-oss-20b-GGUF"
}
```

- 官方模型頁：https://huggingface.co/openai/gpt-oss-20b
- GGUF repo：https://huggingface.co/unsloth/gpt-oss-20b-GGUF

#### 2. DeepSeek-R1-Distill-Qwen-7B

適合：資源較少、想要保留推理能力

```json
{
  "model": "DeepSeek-R1-Distill-Qwen-7B",
  "model_path": "models/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
  "model_repo": "bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF"
}
```

- 官方模型頁：https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
- GGUF repo：https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF

#### 3. DeepSeek-R1-Distill-Qwen-14B

適合：目前這個專案的平衡選擇，推理能力和資源需求比較折衷

```json
{
  "model": "DeepSeek-R1-Distill-Qwen-14B",
  "model_path": "models/DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf",
  "model_repo": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF"
}
```

- 官方模型頁：https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
- GGUF repo：https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF

#### 4. Qwen3-14B

適合：泛用、穩定、多語言能力不錯，速度通常比 reasoning 模型好一些

```json
{
  "model": "Qwen3-14B",
  "model_path": "models/qwen3-14b-q4_k_m.gguf",
  "model_repo": "Qwen/Qwen3-14B-GGUF"
}
```

- 官方模型頁：https://huggingface.co/Qwen/Qwen3-14B
- GGUF repo：https://huggingface.co/Qwen/Qwen3-14B-GGUF

#### 5. QwQ-32B

適合：想要更強的 reasoning / thinking，且機器資源足夠

```json
{
  "model": "QwQ-32B",
  "model_path": "models/qwq-32b-q4_k_m.gguf",
  "model_repo": "Qwen/QwQ-32B-GGUF"
}
```

- 官方模型頁：https://huggingface.co/Qwen/QwQ-32B
- GGUF repo：https://huggingface.co/Qwen/QwQ-32B-GGUF





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
python .\promptpocket.py --start
```

### 停止背景程式

```powershell
python .\promptpocket.py --stop
```

### 查詢目前狀態

```powershell
python .\promptpocket.py --status
```

注意：

- `Ctrl+Space` 在部分 Windows 輸入法環境可能衝突；若有衝突，可把 [`src/ai_hotkey_app.py`](/c:/repos/PromptPocket/src/ai_hotkey_app.py) 裡的 `hotkey` 改成別組快捷鍵。
- `貼上` 依賴 Windows 焦點切換；大多數文字輸入框可正常工作，但少數高權限或特殊 UI 程式可能無法直接貼入。
- 狀態資訊會寫在 [.runtime/ai_stack.json](/c:/repos/PromptPocket/.runtime/ai_stack.json)。

## 備註

- `Q4_K_M` 是量化後的 GGUF 模型，適合在本機資源有限的情況下使用。
- `--ctx-size 16384` 會增加記憶體使用量，如果機器不夠大，可以改小。
- 第一次載入模型可能會比較久，屬於正常現象。






