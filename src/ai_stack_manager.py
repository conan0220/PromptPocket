import atexit
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

from src.ai_hotkey_app import AppConfig, main as run_app
from src.ai_stack_common import (
    DEFAULT_HOTKEY,
    DEFAULT_MODEL_NAME,
    DEFAULT_SERVER_URL,
    ROOT_DIR,
    clear_state,
    ensure_model_available,
    is_pid_running,
    load_config,
    now_iso,
    resolve_llama_server,
    resolve_pythonw,
    write_state,
)


CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


class StackManager:
    def __init__(self) -> None:
        self.server_process: subprocess.Popen | None = None
        self.config = load_config()
        self.model_path = ensure_model_available(self.config)
        self.state = {
            "manager_pid": os.getpid(),
            "server_pid": None,
            "started_at": now_iso(),
            "server_url": DEFAULT_SERVER_URL,
            "model": self.config.get("model", DEFAULT_MODEL_NAME),
            "hotkey": DEFAULT_HOTKEY,
            "model_path": str(self.model_path),
            "llama_server_path": None,
            "server_ready": False,
        }

    def write_state(self) -> None:
        write_state(self.state)

    def start_server(self) -> None:
        llama_server = resolve_llama_server()
        if not self.model_path.exists():
            raise FileNotFoundError(f"找不到模型檔: {self.model_path}")

        self.server_process = subprocess.Popen(
            [
                llama_server,
                "-m",
                str(self.model_path),
                "--ctx-size",
                "16384",
                "--port",
                "8080",
            ],
            cwd=str(self.model_path.parent.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        self.state["server_pid"] = self.server_process.pid
        self.state["llama_server_path"] = llama_server
        self.write_state()

    def wait_until_ready(self, timeout_seconds: int = 45) -> bool:
        deadline = time.time() + timeout_seconds
        url = f"{self.state['server_url']}/models"
        while time.time() < deadline:
            if self.server_process and self.server_process.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if 200 <= response.status < 300:
                        self.state["server_ready"] = True
                        self.write_state()
                        return True
            except (urllib.error.URLError, TimeoutError):
                time.sleep(1)
        return False

    def shutdown(self) -> None:
        server_pid = self.state.get("server_pid")
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
        elif is_pid_running(server_pid):
            subprocess.run(
                ["taskkill", "/PID", str(server_pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
        clear_state()


def run_foreground() -> int:
    manager = StackManager()
    atexit.register(manager.shutdown)

    def handle_exit(_signum, _frame) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    manager.write_state()
    manager.start_server()
    manager.wait_until_ready()

    config_data = load_config()
    config = AppConfig(
        base_url=DEFAULT_SERVER_URL,
        api_key="EMPTY",
        model=config_data.get("model", DEFAULT_MODEL_NAME),
        hotkey=DEFAULT_HOTKEY,
    )
    return run_app(config=config, show_on_start=False)


def main() -> int:
    if "--foreground" not in sys.argv:
        pythonw = resolve_pythonw()
        subprocess.Popen(
            [pythonw, "-m", "src.ai_stack_manager", "--foreground"],
            cwd=str(ROOT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
        )
        print("ai_stack_manager started in background")
        return 0

    return run_foreground()


if __name__ == "__main__":
    raise SystemExit(main())


