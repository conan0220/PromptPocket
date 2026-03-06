import json

from ai_stack_common import PID_FILE, is_pid_running, read_state


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
