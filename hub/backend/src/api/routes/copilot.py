from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/api/copilot/hook/{event}")
async def copilot_hook(event: str, payload: dict, request: Request) -> dict:
    bridge = getattr(request.app.state, "copilot_bridge", None)
    if bridge is None:
        return {}
    return await bridge.handle_hook(event, payload)
