from __future__ import annotations

import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.multi_tenant_directory.config import AppConfig
from src.multi_tenant_directory.domain.models import Session, User
from src.multi_tenant_directory.exceptions import (
    BillingAccountNotFoundError,
    UserAlreadyExistsError,
)
from src.multi_tenant_directory.services.bootstrap import ApplicationContainer
from src.multi_tenant_directory.services.sharding import HashTenantShardStrategy


class UserDirectoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.container: ApplicationContainer = ApplicationContainer(
            AppConfig(data_dir=self.temp_dir.name, shard_count=2)
        )
        self.strategy: HashTenantShardStrategy = HashTenantShardStrategy(2)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_register_user_persists_only_to_assigned_primary_shard(self) -> None:
        tenant_id = self._tenant_for_shard(1)
        user = User(
            tenant_id=tenant_id,
            user_id="user-1",
            email="ops@example.com",
            full_name="Ops User",
            is_active=True,
        )

        self.container.user_directory.register_user(
            user=user,
            starting_balance=Decimal("42.00"),
            currency="USD",
        )

        shard_id = self.strategy.shard_for(tenant_id)
        target_db = Path(self.temp_dir.name) / f"primary-shard-{shard_id}.db"
        other_db = Path(self.temp_dir.name) / f"primary-shard-{1 - shard_id}.db"

        self.assertTrue(target_db.exists())
        self.assertTrue(other_db.exists())
        self.assertIsNotNone(
            self.container.user_directory.get_user(tenant_id, user.user_id)
        )
        self.assertEqual(self._count_users_in_db(target_db), 1)
        self.assertEqual(self._count_users_in_db(other_db), 0)

    def test_billing_charge_updates_balance_transactionally_on_primary(self) -> None:
        tenant_id = self._tenant_for_shard(0)
        user = User(
            tenant_id=tenant_id,
            user_id="user-2",
            email="finance@example.com",
            full_name="Finance User",
            is_active=True,
        )
        self.container.user_directory.register_user(
            user=user,
            starting_balance=Decimal("100.00"),
            currency="USD",
        )

        updated = self.container.user_directory.charge_user(
            tenant_id=tenant_id,
            user_id=user.user_id,
            amount=Decimal("9.99"),
        )

        self.assertEqual(updated.balance, Decimal("109.99"))

    def test_charge_user_raises_for_missing_billing_account(self) -> None:
        with self.assertRaises(BillingAccountNotFoundError):
            self.container.user_directory.charge_user(
                tenant_id=self._tenant_for_shard(0),
                user_id="missing-user",
                amount=Decimal("1.00"),
            )

    def test_registering_duplicate_user_raises_specific_error(self) -> None:
        tenant_id = self._tenant_for_shard(0)
        user = User(
            tenant_id=tenant_id,
            user_id="duplicate-user",
            email="duplicate@example.com",
            full_name="Duplicate User",
            is_active=True,
        )

        self.container.user_directory.register_user(
            user=user,
            starting_balance=Decimal("20.00"),
            currency="USD",
        )

        with self.assertRaises(UserAlreadyExistsError):
            self.container.user_directory.register_user(
                user=user,
                starting_balance=Decimal("20.00"),
                currency="USD",
            )

    def test_reports_read_from_replica_and_require_replication_to_see_latest_data(
        self,
    ) -> None:
        tenant_id = self._tenant_for_shard(0)
        user = User(
            tenant_id=tenant_id,
            user_id="user-3",
            email="owner@example.com",
            full_name="Owner User",
            is_active=True,
        )
        self.container.user_directory.register_user(
            user=user,
            starting_balance=Decimal("75.00"),
            currency="USD",
        )

        report_before_sync = self.container.reporting.generate_daily_report(tenant_id)
        self.assertEqual(report_before_sync.active_users, 0)
        self.assertEqual(report_before_sync.total_balance, Decimal("0"))

        self.container.replication.replicate_all()
        report_after_sync = self.container.reporting.generate_daily_report(tenant_id)

        self.assertEqual(report_after_sync.active_users, 1)
        self.assertEqual(report_after_sync.inactive_users, 0)
        self.assertEqual(report_after_sync.total_balance, Decimal("75.00"))

    def test_replica_remains_stale_until_replicated_after_additional_primary_write(
        self,
    ) -> None:
        tenant_id = self._tenant_for_shard(1)
        user = User(
            tenant_id=tenant_id,
            user_id="user-4",
            email="billing@example.com",
            full_name="Billing User",
            is_active=True,
        )
        self.container.user_directory.register_user(
            user=user,
            starting_balance=Decimal("10.00"),
            currency="USD",
        )
        self.container.replication.replicate_all()

        self.container.user_directory.charge_user(
            tenant_id=tenant_id,
            user_id=user.user_id,
            amount=Decimal("5.50"),
        )

        stale_report = self.container.reporting.generate_daily_report(tenant_id)
        self.assertEqual(stale_report.total_balance, Decimal("10.00"))

        self.container.replication.replicate_all()
        fresh_report = self.container.reporting.generate_daily_report(tenant_id)
        self.assertEqual(fresh_report.total_balance, Decimal("15.50"))

    def test_session_store_round_trip_supports_fast_lookup(self) -> None:
        session = Session(
            session_id="session-42",
            tenant_id="tenant-42",
            user_id="user-42",
            payload='{"scope":"admin"}',
        )

        self.container.user_directory.create_session(session)

        stored = self.container.user_directory.get_session("session-42")
        self.assertEqual(stored, session)

    def _tenant_for_shard(self, expected_shard: int) -> str:
        for candidate in range(500):
            tenant_id = f"tenant-{candidate}"
            if self.strategy.shard_for(tenant_id) == expected_shard:
                return tenant_id
        raise AssertionError("failed to find tenant for shard")

    @staticmethod
    def _count_users_in_db(db_path: Path) -> int:
        with sqlite3.connect(db_path) as connection:
            row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0])


if __name__ == "__main__":
    unittest.main()
