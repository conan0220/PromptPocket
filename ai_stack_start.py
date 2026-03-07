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


def main() -> int:
    stop_main()
    time.sleep(0.3)

    pythonw = resolve_pythonw()
    manager_script = Path(ROOT_DIR / "ai_stack_manager.py")
    subprocess.Popen(
        [pythonw, str(manager_script), "--foreground"],
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    )

    manager_pid = None
    for _ in range(50):
        state = read_state()
        if state and is_pid_running(state.get("manager_pid")):
            manager_pid = state.get("manager_pid")
            break
        time.sleep(0.1)

    print(f"started manager pid={manager_pid}")
    print(f"pid file: {PID_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
