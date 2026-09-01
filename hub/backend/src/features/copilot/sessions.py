from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CopilotSession:
    session_id: str
    cwd: str = ""
    last_seen: float = field(default_factory=time.monotonic)
    current_tool: str | None = None
    waiting: bool = False


def _repo_name(cwd: str) -> str:
    return cwd.rstrip("/").rsplit("/", 1)[-1] if cwd else "session"


class CopilotSessionStore:
    """Tracks local Copilot CLI/app sessions from hook events.

    Sessions are keyed by the CLI's sessionId. There's no guaranteed
    sessionEnd (the app can be force-quit), so a reaper drops sessions that
    haven't sent an event in idle_after_secs.
    """

    def __init__(self, idle_after_secs: int = 180):
        self._idle_after_secs = idle_after_secs
        self._sessions: dict[str, CopilotSession] = {}

    def touch(self, session_id: str, cwd: str | None = None) -> CopilotSession:
        session = self._sessions.get(session_id)
        if session is None:
            session = CopilotSession(session_id=session_id, cwd=cwd or "")
            self._sessions[session_id] = session
        else:
            session.last_seen = time.monotonic()
            if cwd:
                session.cwd = cwd
        return session

    def end(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def reap_stale(self) -> list[str]:
        cutoff = time.monotonic() - self._idle_after_secs
        stale = [sid for sid, s in self._sessions.items() if s.last_seen < cutoff]
        for sid in stale:
            self._sessions.pop(sid, None)
        return stale

    def counts(self) -> tuple[int, int, int]:
        total = len(self._sessions)
        waiting = sum(1 for s in self._sessions.values() if s.waiting)
        running = sum(1 for s in self._sessions.values()
                      if s.current_tool and not s.waiting)
        return total, running, waiting

    def recent_entries(self, limit: int = 4) -> list[str]:
        active = sorted((s for s in self._sessions.values() if s.current_tool),
                         key=lambda s: s.last_seen, reverse=True)
        return [f"{_repo_name(s.cwd)}: {s.current_tool}" for s in active[:limit]]
