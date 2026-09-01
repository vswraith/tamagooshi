"""One-time setup: registers the Tamagooshi hook shim in ~/.copilot/hooks/.

Run with `make hub-install-copilot-hooks` (or `python -m
src.features.copilot.install_hooks` from hub/backend). Personal hooks apply
to every Copilot CLI session across every repo, so this only needs running
once per machine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ...config.models import CopilotConfig

SHIM_PATH = Path(__file__).resolve().with_name("hook_shim.py")


def hooks_config(permission_timeout_secs: int) -> dict:
    # Give the hook a few seconds more than the hub's own deadline so the
    # hub's explicit deny (see CopilotBridge._request_permission) always
    # reaches the CLI before the hook's own fail-open timeout would.
    hook_timeout = permission_timeout_secs + 15
    command = f'python3 "{SHIM_PATH}"'

    def entry(event: str, timeout_sec: int) -> dict:
        return {"type": "command", "bash": f"{command} {event}", "timeoutSec": timeout_sec}

    return {
        "version": 1,
        "hooks": {
            "sessionStart": [entry("sessionStart", 10)],
            "sessionEnd": [entry("sessionEnd", 10)],
            # preToolUse fires on every tool call and only drives the
            # device's activity feed (non-blocking) - short timeout.
            "preToolUse": [entry("preToolUse", 10)],
            "postToolUse": [entry("postToolUse", 10)],
            # permissionRequest is the one that blocks for a device
            # approve/deny, so it gets the long timeout.
            "permissionRequest": [entry("permissionRequest", hook_timeout)],
            "notification": [entry("notification", 10)],
        },
    }


def install(idle_after_secs: int = CopilotConfig().idle_after_secs,
            permission_timeout_secs: int = CopilotConfig().permission_timeout_secs) -> Path:
    hooks_dir = Path(os.environ.get("COPILOT_HOME", Path.home() / ".copilot")) / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target = hooks_dir / "tamagooshi.json"
    target.write_text(json.dumps(hooks_config(permission_timeout_secs), indent=2) + "\n")
    return target


def main() -> None:
    target = install()
    print(f"wrote {target}")
    print("restart any running `copilot`/`gh copilot` sessions to pick it up.")


if __name__ == "__main__":
    main()
