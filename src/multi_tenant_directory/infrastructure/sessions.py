from __future__ import annotations

from src.multi_tenant_directory.domain.models import Session
from src.multi_tenant_directory.ports.repositories import SessionStore


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def put(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)
