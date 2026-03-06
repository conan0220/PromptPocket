from ai_stack_common import clear_state, is_pid_running, kill_process_tree, read_state


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
