from __future__ import annotations

import logging

from ...config.models import CopilotConfig
from ...network.transport.base import LineChannel
from .bridge import CopilotBridge

log = logging.getLogger("tamagooshi.copilot")

__all__ = ["CopilotBridge", "create_copilot_bridge"]


def create_copilot_bridge(transport: object, cfg: CopilotConfig) -> CopilotBridge | None:
    if not cfg.enabled:
        return None
    if not isinstance(transport, LineChannel):
        log.info("transport has no agent line channel; copilot bridge disabled")
        return None
    return CopilotBridge(transport, permission_timeout_secs=cfg.permission_timeout_secs,
                          idle_after_secs=cfg.idle_after_secs)
