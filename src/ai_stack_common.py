import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / ".runtime"
PID_FILE = RUNTIME_DIR / "ai_stack.json"
CONFIG_FILE = ROOT_DIR / "config.json"
DEFAULT_MODEL_PATH = ROOT_DIR / "models" / "Qwen3.5-9B-Q4_K_M.gguf"
DEFAULT_MODEL_REPO = "unsloth/Qwen3.5-9B-GGUF"
DEFAULT_SERVER_URL = "http://localhost:8080/v1"
DEFAULT_MODEL_NAME = "Qwen3.5-9B"
DEFAULT_HOTKEY = "ctrl+space"
DEFAULT_CONFIG = {
    "model": DEFAULT_MODEL_NAME,
    "model_path": str(DEFAULT_MODEL_PATH),
    "model_repo": DEFAULT_MODEL_REPO,
}


def ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if not CONFIG_FILE.exists():
        return config
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return config
    if not isinstance(raw, dict):
        return config
    for key in config:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            config[key] = value.strip()
    return config


def resolve_model_path(config: dict | None = None) -> Path:
    config = config or load_config()
    raw_path = config.get("model_path", str(DEFAULT_MODEL_PATH))
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = ROOT_DIR / candidate
    return candidate.resolve()


def ensure_model_available(config: dict | None = None, log=None) -> Path:
    config = config or load_config()
    model_path = resolve_model_path(config)
    if model_path.exists():
        return model_path

    model_repo = str(config.get("model_repo", "")).strip()
    if not model_repo:
        raise FileNotFoundError(
            "找不到模型檔，且 config.json 缺少 model_repo。"
            f" model={config.get('model')} model_path={config.get('model_path')}"
        )

    model_path.parent.mkdir(parents=True, exist_ok=True)
    if log is not None:
        log(
            "model file not found, downloading from Hugging Face: "
            f"repo={model_repo} file={model_path.name}"
        )
    try:
        try:
            from huggingface_hub import hf_hub_download

            hf_hub_download(
                repo_id=model_repo,
                filename=model_path.name,
                local_dir=str(model_path.parent),
            )
        except ModuleNotFoundError:
            result = subprocess.run(
                [
                    "hf",
                    "download",
                    model_repo,
                    "--include",
                    model_path.name,
                    "--local-dir",
                    str(model_path.parent),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(
                    "huggingface_hub 未安裝，且 hf download 也無法使用。"
                    f" detail={detail}"
                ) from None
    except Exception as exc:  # noqa: BLE001
        raise FileNotFoundError(
            "無法根據 config.json 下載模型。"
            f" model={config.get('model')} model_repo={model_repo} "
            f"model_path={config.get('model_path')} error={exc}"
        ) from exc

    if not model_path.exists():
        raise FileNotFoundError(
            "模型下載流程已完成，但找不到下載後的檔案。"
            f" model={config.get('model')} model_repo={model_repo} "
            f"model_path={config.get('model_path')}"
        )
    return model_path


def read_state() -> dict | None:
    if not PID_FILE.exists():
        return None
    try:
        return json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_state(data: dict) -> None:
    ensure_runtime_dir()
    PID_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_state() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def is_pid_running(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout.strip()
    if not output or "No tasks are running" in output:
        return False
    return f'"{pid}"' in output or f",{pid}," in output


def kill_process_tree(pid: int | None) -> bool:
    if not is_pid_running(pid):
        return False
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def resolve_pythonw() -> str:
    candidate = ROOT_DIR / ".venv" / "Scripts" / "pythonw.exe"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def resolve_python() -> str:
    candidate = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def resolve_llama_server() -> str:
    env_path = os.environ.get("LLAMA_SERVER_PATH")
    if env_path:
        return env_path

    result = subprocess.run(
        ["where", "llama-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if lines:
        return lines[0]

    raise FileNotFoundError(
        "找不到 llama-server。請把它加入 PATH，或設定 LLAMA_SERVER_PATH。"
    )


