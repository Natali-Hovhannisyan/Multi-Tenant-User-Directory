from __future__ import annotations

import unittest

from src.multi_tenant_directory.domain.models import Session
from src.multi_tenant_directory.exceptions import SessionStoreError
from src.multi_tenant_directory.infrastructure.sessions import (
    InMemorySessionStore,
    RedisSessionStore,
)


class SessionStoreTests(unittest.TestCase):
    def test_in_memory_session_store_returns_none_for_unknown_session(self) -> None:
        store = InMemorySessionStore()
        self.assertIsNone(store.get("missing-session"))

    def test_in_memory_session_store_round_trip(self) -> None:
        store = InMemorySessionStore()
        session = Session(
            session_id="session-42",
            tenant_id="tenant-42",
            user_id="user-42",
            payload='{"scope":"admin"}',
        )

        store.put(session)

        self.assertEqual(store.get("session-42"), session)

    def test_redis_session_store_round_trip_with_fake_client(self) -> None:
        client = FakeRedisClient()
        store = RedisSessionStore(client=client)
        session = Session(
            session_id="session-99",
            tenant_id="tenant-99",
            user_id="user-99",
            payload='{"scope":"owner"}',
        )

        store.put(session)

        self.assertEqual(store.get("session-99"), session)

    def test_redis_session_store_raises_specific_error_for_invalid_payload(
        self,
    ) -> None:
        client = FakeRedisClient()
        client.storage["bad-session"] = "not-json"
        store = RedisSessionStore(client=client)

        with self.assertRaises(SessionStoreError):
            store.get("bad-session")


class FakeRedisClient:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, name: str, value: str) -> object:
        self.storage[name] = value
        return True

    def get(self, name: str) -> str | bytes | None:
        return self.storage.get(name)


if __name__ == "__main__":
    unittest.main()
