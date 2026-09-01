#!/usr/bin/env python3
"""Copilot CLI hook shim: forwards hook events to the running Tamagooshi hub.

Registered per-event in ~/.copilot/hooks/tamagooshi.json (see
`hub/backend/src/features/copilot/install_hooks.py`). Invoked by the Copilot
CLI as `python3 hook_shim.py <event>` with the hook payload on stdin.

Deliberately stdlib-only: the Copilot CLI spawns this directly, not through
the hub's virtualenv, so it can't rely on httpx/fastapi/etc being importable.

For permissionRequest specifically: any failure to reach the hub fails
closed (denies the tool call) rather than printing nothing, which would
silently fall through to Copilot's default permission handling and bypass
this integration entirely without anyone noticing.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BLOCKING_EVENTS = {"permissionRequest"}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: hook_shim.py <event>", file=sys.stderr)
        return 2
    event = sys.argv[1]
    blocking = event in BLOCKING_EVENTS

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    port = os.environ.get("TAMA_HUB_PORT", "8000")
    url = f"http://127.0.0.1:{port}/api/copilot/hook/{event}"
    timeout = float(os.environ.get("TAMA_COPILOT_HOOK_TIMEOUT_SECS", "250"))

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            reply = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        if blocking:
            print(f"tamagooshi hub unreachable: {err}", file=sys.stderr)
            return 1
        return 0

    if blocking:
        print(json.dumps(reply))
    return 0


if __name__ == "__main__":
    sys.exit(main())
