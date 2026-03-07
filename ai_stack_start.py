import subprocess
import time
from pathlib import Path

from ai_stack_stop import main as stop_main
from ai_stack_common import (
    PID_FILE,
    ROOT_DIR,
    is_pid_running,
    read_state,
    resolve_pythonw,
)


DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def log(message: str) -> None:
    print(f"[ai_stack_start] {message}", flush=True)


def main() -> int:
    log("stopping existing stack if present")
    stop_main()
    time.sleep(0.3)

    pythonw = resolve_pythonw()
    manager_script = Path(ROOT_DIR / "ai_stack_manager.py")
    log(f"starting manager: {manager_script}")
    subprocess.Popen(
        [pythonw, str(manager_script), "--foreground"],
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    )

    manager_pid = None
    log("waiting for manager to write state file")
    for attempt in range(50):
        state = read_state()
        if state and is_pid_running(state.get("manager_pid")):
            manager_pid = state.get("manager_pid")
            log(f"manager is running with pid={manager_pid}")
            break
        if attempt in (0, 10, 20, 30, 40):
            log("manager not ready yet")
        time.sleep(0.1)

    if manager_pid is None:
        log(f"failed to detect manager process from {PID_FILE}")
        return 1

    log(f"state file: {PID_FILE}")
    log("waiting for server_ready=true")
    deadline = time.time() + 90
    while time.time() < deadline:
        state = read_state()
        if not state:
            if not is_pid_running(manager_pid):
                log("manager exited before state became available")
                return 1
            log("state file not available yet")
            time.sleep(1)
            continue

        current_manager_pid = state.get("manager_pid")
        server_pid = state.get("server_pid")
        server_ready = state.get("server_ready") is True
        model_name = state.get("model") or "unknown"

        if server_ready:
            log(f"server is ready for model={model_name} server_pid={server_pid}")
            return 0

        if current_manager_pid and not is_pid_running(current_manager_pid):
            log("manager exited before server_ready became true")
            return 1

        if server_pid and not is_pid_running(server_pid):
            log("server process exited before server_ready became true")
            return 1

        log(
            f"still waiting: model={model_name} manager_pid={current_manager_pid} "
            f"server_pid={server_pid} server_ready={state.get('server_ready')}"
        )
        time.sleep(1)

    log("timed out waiting for server_ready=true")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
