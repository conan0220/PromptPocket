import argparse
import json
import subprocess
import time

from src.ai_stack_common import (
    DEFAULT_SERVER_READY_TIMEOUT_SECONDS,
    PID_FILE,
    ROOT_DIR,
    clear_state,
    ensure_model_available,
    is_server_ready,
    is_pid_running,
    kill_process_tree,
    load_config,
    read_state,
    resolve_pythonw,
    write_state,
)


DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the PromptPocket background AI stack."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Start the AI stack")
    group.add_argument("--stop", action="store_true", help="Stop the AI stack")
    group.add_argument("--status", action="store_true", help="Show stack status")
    return parser


def log(message: str) -> None:
    print(f"[ai_stack] {message}", flush=True)


def stop_stack() -> int:
    state = read_state()
    if not state:
        print("not running")
        clear_state()
        return 0

    manager_pid = state.get("manager_pid")
    if not is_pid_running(manager_pid):
        print("stale pid file removed")
        clear_state()
        return 0

    stopped = kill_process_tree(manager_pid)
    clear_state()
    print(f"stopped={stopped} manager_pid={manager_pid}")
    return 0


def status_stack() -> int:
    state = read_state()
    if not state:
        print("running: false")
        print(f"pid_file: {PID_FILE}")
        return 0

    manager_pid = state.get("manager_pid")
    server_pid = state.get("server_pid")
    manager_running = is_pid_running(manager_pid)
    server_running = is_pid_running(server_pid)

    print(f"running: {manager_running}")
    print(f"manager_running: {manager_running}")
    print(f"server_running: {server_running}")
    print(f"pid_file: {PID_FILE}")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def start_stack() -> int:
    config = load_config()
    try:
        model_path = ensure_model_available(config, log)
        log(f"model is ready: {model_path}")
    except Exception as exc:  # noqa: BLE001
        log(str(exc))
        return 1

    log("stopping existing stack if present")
    stop_stack()
    time.sleep(0.3)

    pythonw = resolve_pythonw()
    log("starting manager: src.ai_stack_manager")
    subprocess.Popen(
        [pythonw, "-m", "src.ai_stack_manager", "--foreground"],
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    )

    manager_pid = None
    log("waiting for manager to write state file")
    for attempt in range(200):
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
    log("waiting for server API to become ready")
    deadline = time.time() + DEFAULT_SERVER_READY_TIMEOUT_SECONDS
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
        server_url = state.get("server_url") or "unknown"
        server_ready = is_server_ready(server_url) if server_url != "unknown" else False
        model_name = state.get("model") or "unknown"

        if server_ready:
            if state.get("server_ready") is not True:
                state["server_ready"] = True
                write_state(state)
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
            f"server_pid={server_pid} server_url={server_url} "
            f"server_ready={state.get('server_ready')}"
        )
        time.sleep(1)

    log("timed out waiting for server API to become ready")
    return 1


def main() -> int:
    args = build_parser().parse_args()
    if args.start:
        return start_stack()
    if args.stop:
        return stop_stack()
    return status_stack()


if __name__ == "__main__":
    raise SystemExit(main())
