from __future__ import annotations

import unittest

from src.multi_tenant_directory.domain.models import Session
from src.multi_tenant_directory.infrastructure.sessions import InMemorySessionStore


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


if __name__ == "__main__":
    unittest.main()
