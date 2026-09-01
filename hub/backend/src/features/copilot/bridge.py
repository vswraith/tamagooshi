from __future__ import annotations

import asyncio
import json
import logging

from ...network.transport.base import LineChannel
from .sessions import CopilotSessionStore

log = logging.getLogger("tamagooshi.copilot.bridge")

# Firmware's BuddyController marks the device "Offline" if it hasn't seen a
# snapshot in 30s (kStaleMs in firmware/lib/features/buddy/controller.cpp),
# regardless of whether the BLE link is actually still up. Heartbeat well
# under that so idle stretches between Copilot activity don't flicker the
# device to Offline.
HEARTBEAT_INTERVAL_SECS = 15.0
HINT_LIMIT = 60


def _summarize_args(args: dict, limit: int = HINT_LIMIT) -> str:
    if not args:
        return ""
    text = ", ".join(f"{k}={v}" for k, v in args.items())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class CopilotBridge:
    """Watches local GitHub Copilot CLI/app sessions via `~/.copilot/hooks`
    and relays status + tool-permission prompts to the device over the
    buddy NUS line, the same protocol the on-device buddy screen already
    understands (bare snapshot lines, `cmd:"permission"` decisions).

    Speaks the same line channel VoiceBridge uses, but owns it outright for
    brands that enable copilot tracking instead of voice chat.
    """

    def __init__(self, channel: LineChannel, permission_timeout_secs: int = 240,
                 idle_after_secs: int = 180):
        self._channel = channel
        self._permission_timeout_secs = permission_timeout_secs
        self._sessions = CopilotSessionStore(idle_after_secs)
        self._pending: dict[str, asyncio.Future] = {}
        self._seq = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._heartbeat_task: asyncio.Task | None = None
        # The device only ever shows one pending prompt. Every snapshot line
        # must carry it (or explicitly omit it) - the firmware codec treats
        # a missing "prompt" key as "no active prompt" and clears the
        # approve/deny overlay, so this has to survive heartbeat ticks too,
        # not just the snapshot that first raised it.
        self._active_prompt: dict | None = None
        self._active_id: str | None = None
        # Concurrent permission requests (from separate sessions) can't all
        # be shown at once, so anything that arrives while one is already
        # displayed waits its turn here, FIFO. Each request's own timeout
        # only starts counting once it's actually shown - waiting in queue
        # doesn't burn down its decision window before the user can see it.
        self._queue: list[str] = []
        self._prompts: dict[str, dict] = {}
        self._activated: dict[str, asyncio.Event] = {}

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._channel.on_line(self._on_line)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._send_snapshot()
        log.info("copilot bridge attached")

    async def stop(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
        for fut in self._pending.values():
            if not fut.done():
                fut.set_result(False)
        self._pending.clear()
        for ev in self._activated.values():
            ev.set()
        self._activated.clear()
        self._queue.clear()
        self._prompts.clear()
        self._active_id = None
        self._active_prompt = None

    def _on_line(self, line: str) -> None:
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._handle_line(line), self._loop)

    async def _handle_line(self, line: str) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            log.debug("ignoring non-json line: %.80s", line)
            return
        if msg.get("cmd") == "permission":
            self.resolve(str(msg.get("id", "")), msg.get("decision") == "once")

    def resolve(self, request_id: str, approved: bool) -> bool:
        fut = self._pending.pop(request_id, None)
        if fut is None or fut.done():
            return False
        fut.set_result(approved)
        return True

    async def handle_hook(self, event: str, payload: dict) -> dict:
        session_id = str(payload.get("sessionId") or "")
        cwd = payload.get("cwd")
        tool_name = payload.get("toolName")

        if event == "sessionEnd":
            self._sessions.end(session_id)
            self._send_snapshot()
            return {}

        if event == "permissionRequest":
            return await self._request_permission(session_id, cwd, tool_name, payload)

        if event == "preToolUse":
            # Fires on every tool call, not just the ones needing approval —
            # this is what drives the device's live activity feed. Only
            # `permissionRequest` (above) actually blocks for a decision.
            session = self._sessions.touch(session_id, cwd=cwd)
            session.current_tool = tool_name or "tool"
            self._send_snapshot()
            return {}

        if event == "postToolUse":
            session = self._sessions.touch(session_id, cwd=cwd)
            session.current_tool = None
            session.waiting = False
            self._send_snapshot()
            return {}

        # sessionStart, notification, errorOccurred, etc: just keep the
        # session alive and reflect it on the device.
        self._sessions.touch(session_id, cwd=cwd)
        self._send_snapshot()
        return {}

    async def _request_permission(self, session_id: str, cwd: str | None,
                                   tool_name: str | None, payload: dict) -> dict:
        assert self._loop is not None
        session = self._sessions.touch(session_id, cwd=cwd)
        session.current_tool = tool_name or "tool"

        if self._channel_disconnected():
            self._send_snapshot()
            return {"behavior": "deny", "message": "Tamagooshi device not connected"}

        session.waiting = True
        self._seq += 1
        request_id = f"c{self._seq}"
        fut: asyncio.Future = self._loop.create_future()
        self._pending[request_id] = fut
        self._prompts[request_id] = {
            "id": request_id, "tool": session.current_tool,
            "hint": _summarize_args(payload.get("toolArgs") or {}),
        }
        activated = asyncio.Event()
        self._activated[request_id] = activated

        if self._active_id is None:
            self._activate(request_id)
        else:
            self._queue.append(request_id)

        await activated.wait()

        try:
            approved = await asyncio.wait_for(fut, timeout=self._permission_timeout_secs)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            log.warning("permission request %s timed out, denying", request_id)
            approved = False
        finally:
            session.waiting = False
            self._prompts.pop(request_id, None)
            self._activated.pop(request_id, None)
            if self._active_id == request_id:
                if not self._advance_queue():
                    self._send_snapshot()
            else:
                try:
                    self._queue.remove(request_id)
                except ValueError:
                    pass
                self._send_snapshot()

        return {"behavior": "allow" if approved else "deny"}

    def _activate(self, request_id: str) -> None:
        self._active_id = request_id
        self._active_prompt = self._prompts.get(request_id)
        activated = self._activated.get(request_id)
        if activated is not None:
            activated.set()
        self._send_snapshot()

    def _advance_queue(self) -> bool:
        if self._queue:
            self._activate(self._queue.pop(0))
            return True
        self._active_id = None
        self._active_prompt = None
        return False

    def _channel_disconnected(self) -> bool:
        status = getattr(self._channel, "status", None)
        if status is None:
            return False
        try:
            return status().state != "connected"
        except Exception:
            return False

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECS)
                self._sessions.reap_stale()
                self._send_snapshot()
        except asyncio.CancelledError:
            pass

    def _send_snapshot(self) -> None:
        total, running, waiting = self._sessions.counts()
        entries = self._sessions.recent_entries()
        body: dict = {
            "total": total,
            "running": running,
            "waiting": waiting,
            "msg": entries[0] if entries else "copilot idle",
        }
        if entries:
            body["entries"] = entries
        if self._active_prompt is not None:
            body["prompt"] = self._active_prompt
        self._channel.send_line(json.dumps(body, separators=(",", ":")))
