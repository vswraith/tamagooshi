import asyncio
import json

from src.features.copilot.bridge import CopilotBridge
from src.network.transport.base import LinkStatus


class FakeChannel:
    def __init__(self, state="connected"):
        self.sent = []
        self.handler = None
        self._state = state

    def on_line(self, handler):
        self.handler = handler

    def send_line(self, line):
        self.sent.append(json.loads(line))

    def status(self):
        return LinkStatus(state=self._state)


def snapshots(channel):
    return [m for m in channel.sent if "total" in m]


def prompts(channel):
    return [m["prompt"] for m in snapshots(channel) if "prompt" in m]


def make_bridge(**kwargs):
    channel = FakeChannel()
    bridge = CopilotBridge(channel, permission_timeout_secs=kwargs.pop("permission_timeout_secs", 5),
                            idle_after_secs=kwargs.pop("idle_after_secs", 900))
    return bridge, channel


async def start(bridge):
    bridge._loop = asyncio.get_running_loop()
    bridge._channel.on_line(bridge._on_line)


def test_session_start_reflected_in_snapshot():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)
        await bridge.handle_hook("sessionStart", {"sessionId": "s1", "cwd": "/repos/myrepo"})

        assert snapshots(channel)[-1]["total"] == 1
        assert snapshots(channel)[-1]["msg"] == "copilot idle"

    asyncio.run(run())


def test_session_end_removes_it():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)
        await bridge.handle_hook("sessionStart", {"sessionId": "s1", "cwd": "/repos/myrepo"})
        await bridge.handle_hook("sessionEnd", {"sessionId": "s1"})

        assert snapshots(channel)[-1]["total"] == 0

    asyncio.run(run())


def test_pretooluse_updates_activity_feed_without_blocking():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        result = await bridge.handle_hook("preToolUse", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "cat hello.txt",
        })

        # Non-blocking: returns immediately with no decision, so Copilot's
        # own permission flow (and permissionRequest, if needed) still runs.
        assert result == {}
        assert bridge._pending == {}
        assert prompts(channel) == []
        assert snapshots(channel)[-1]["msg"] == "myrepo: cat hello.txt"
        assert snapshots(channel)[-1]["running"] == 1

    asyncio.run(run())


def test_permissionrequest_raises_prompt_and_waits():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        task = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "npm install",
            "toolArgs": {"cmd": "npm install"},
        }))
        await asyncio.sleep(0)  # let it register the pending future

        pending = prompts(channel)
        assert len(pending) == 1
        assert pending[0]["tool"] == "npm install"
        request_id = pending[0]["id"]

        await bridge._handle_line(json.dumps({"cmd": "permission", "id": request_id,
                                               "decision": "once"}))
        result = await task
        assert result == {"behavior": "allow"}

    asyncio.run(run())


def test_permissionrequest_denied_on_device():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        task = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "rm -rf build",
        }))
        await asyncio.sleep(0)
        request_id = prompts(channel)[0]["id"]

        await bridge._handle_line(json.dumps({"cmd": "permission", "id": request_id,
                                               "decision": "deny"}))
        result = await task
        assert result == {"behavior": "deny"}

    asyncio.run(run())


def test_permissionrequest_times_out_denied():
    async def run():
        bridge, channel = make_bridge(permission_timeout_secs=0.05)
        await start(bridge)

        result = await bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "npm install",
        })
        assert result == {"behavior": "deny"}

    asyncio.run(run())


def test_permissionrequest_fails_closed_when_device_disconnected():
    async def run():
        bridge, channel = make_bridge()
        channel._state = "connecting"
        await start(bridge)

        result = await bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "npm install",
        })
        assert result["behavior"] == "deny"
        assert prompts(channel) == []

    asyncio.run(run())


def test_unknown_permission_id_is_ignored():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)
        assert bridge.resolve("c999", True) is False

    asyncio.run(run())


def test_posttooluse_clears_running_state():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        task = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "npm install",
        }))
        await asyncio.sleep(0)
        request_id = prompts(channel)[0]["id"]
        await bridge._handle_line(json.dumps({"cmd": "permission", "id": request_id,
                                               "decision": "once"}))
        await task

        await bridge.handle_hook("postToolUse", {"sessionId": "s1", "cwd": "/repos/myrepo"})
        assert snapshots(channel)[-1]["running"] == 0
        assert snapshots(channel)[-1]["waiting"] == 0

    asyncio.run(run())


def test_stop_resolves_pending_as_denied():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        task = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "npm install",
        }))
        await asyncio.sleep(0)
        await bridge.stop()

        result = await task
        assert result == {"behavior": "deny"}

    asyncio.run(run())
