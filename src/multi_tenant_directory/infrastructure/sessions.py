from __future__ import annotations

import json
import logging
from typing import Protocol

from src.multi_tenant_directory.domain.models import Session
from src.multi_tenant_directory.exceptions import SessionStoreError
from src.multi_tenant_directory.ports.repositories import SessionStore

logger = logging.getLogger(__name__)


class RedisClientProtocol(Protocol):
    def set(self, name: str, value: str) -> object: ...

    def get(self, name: str) -> str | bytes | None: ...


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def put(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)


class RedisSessionStore(SessionStore):
    def __init__(self, client: RedisClientProtocol) -> None:
        self._client = client

    def put(self, session: Session) -> None:
        payload = json.dumps(
            {
                "session_id": session.session_id,
                "tenant_id": session.tenant_id,
                "user_id": session.user_id,
                "payload": session.payload,
            }
        )
        try:
            self._client.set(session.session_id, payload)
            logger.debug("Stored session %s in Redis", session.session_id)
        except OSError as exc:
            logger.error("Failed to store session %s in Redis", session.session_id)
            raise SessionStoreError("failed to store session") from exc

    def get(self, session_id: str) -> Session | None:
        try:
            raw_value = self._client.get(session_id)
        except OSError as exc:
            logger.error("Failed to fetch session %s from Redis", session_id)
            raise SessionStoreError("failed to fetch session") from exc

        if raw_value is None:
            return None

        encoded = (
            raw_value.decode("utf-8") if isinstance(raw_value, bytes) else raw_value
        )
        try:
            data = json.loads(encoded)
        except json.JSONDecodeError as exc:
            logger.error("Invalid session payload in Redis for %s", session_id)
            raise SessionStoreError("invalid session payload") from exc

        return Session(
            session_id=str(data["session_id"]),
            tenant_id=str(data["tenant_id"]),
            user_id=str(data["user_id"]),
            payload=str(data["payload"]),
        )
