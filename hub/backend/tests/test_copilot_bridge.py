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


def test_prompt_survives_unrelated_snapshots_while_pending():
    # Regression test: firmware clears the approve/deny overlay whenever a
    # snapshot omits the "prompt" key (see codec.cpp), so anything sent
    # while a request is still pending - a heartbeat tick, another hook
    # event - must keep echoing the active prompt, not just the snapshot
    # that first raised it.
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        task = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/myrepo", "toolName": "npm install",
        }))
        await asyncio.sleep(0)
        request_id = prompts(channel)[0]["id"]

        bridge._send_snapshot()  # simulate a heartbeat tick firing mid-wait
        await bridge.handle_hook("sessionStart", {"sessionId": "s2", "cwd": "/repos/other"})

        assert prompts(channel)[-1]["id"] == request_id

        await bridge._handle_line(json.dumps({"cmd": "permission", "id": request_id,
                                               "decision": "once"}))
        await task

        assert prompts(channel)[-1] == prompts(channel)[-2]  # last prompt-carrying snapshot
        assert "prompt" not in snapshots(channel)[-1]  # cleared once resolved

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


def test_second_concurrent_request_queues_until_first_resolves():
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        first = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/repo-one", "toolName": "npm install",
        }))
        await asyncio.sleep(0)
        second = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s2", "cwd": "/repos/repo-two", "toolName": "npm test",
        }))
        await asyncio.sleep(0)

        # Only the first shows on the device; the second is queued, not
        # merged into the visible prompt or lost.
        assert prompts(channel)[-1]["tool"] == "npm install"
        first_id = prompts(channel)[-1]["id"]
        assert bridge._active_id == first_id
        assert len(bridge._queue) == 1

        await bridge._handle_line(json.dumps({"cmd": "permission", "id": first_id,
                                               "decision": "once"}))
        first_result = await first

        # Second request is now shown and gets its own full decision window.
        assert prompts(channel)[-1]["tool"] == "npm test"
        second_id = prompts(channel)[-1]["id"]
        assert second_id != first_id
        assert bridge._active_id == second_id
        assert bridge._queue == []

        await bridge._handle_line(json.dumps({"cmd": "permission", "id": second_id,
                                               "decision": "deny"}))
        second_result = await second

        assert first_result == {"behavior": "allow"}
        assert second_result == {"behavior": "deny"}
        assert bridge._active_id is None
        assert "prompt" not in snapshots(channel)[-1]

    asyncio.run(run())


def test_queued_request_denied_immediately_does_not_wait_its_turn_forever():
    # A request resolved (e.g. device disconnects mid-queue, or stop())
    # while still queued shouldn't leave it stuck in the queue list.
    async def run():
        bridge, channel = make_bridge()
        await start(bridge)

        first = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s1", "cwd": "/repos/repo-one", "toolName": "npm install",
        }))
        await asyncio.sleep(0)
        second = asyncio.create_task(bridge.handle_hook("permissionRequest", {
            "sessionId": "s2", "cwd": "/repos/repo-two", "toolName": "npm test",
        }))
        await asyncio.sleep(0)
        assert len(bridge._queue) == 1

        await bridge.stop()
        first_result = await first
        second_result = await second

        assert first_result == {"behavior": "deny"}
        assert second_result == {"behavior": "deny"}
        assert bridge._queue == []

    asyncio.run(run())
