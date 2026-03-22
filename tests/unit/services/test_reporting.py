from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from src.multi_tenant_directory.domain.models import TenantReport
from src.multi_tenant_directory.exceptions import ReplicationError, ShardNotFoundError
from src.multi_tenant_directory.infrastructure.sqlite import (
    ReplicaSynchronizer,
    ShardDatabasePaths,
)
from src.multi_tenant_directory.ports.repositories import AnalyticsRepository
from src.multi_tenant_directory.services.directory import TenantShardResolver
from src.multi_tenant_directory.services.reporting import (
    AnalyticsReportService,
    ReplicaShardContext,
    ReplicaShardResolver,
)
from src.multi_tenant_directory.services.replication import ReplicationService
from src.multi_tenant_directory.services.sharding import HashTenantShardStrategy


class ReportingServiceTests(unittest.TestCase):
    def test_heavy_reports_are_resolved_through_replica_context(self) -> None:
        strategy = HashTenantShardStrategy(2)
        repo0 = RecordingAnalyticsRepository("replica-0")
        repo1 = RecordingAnalyticsRepository("replica-1")
        service = AnalyticsReportService(
            shard_resolver=ReplicaShardResolver(
                strategy=strategy,
                shards={
                    0: ReplicaShardContext(shard_id=0, analytics=repo0),
                    1: ReplicaShardContext(shard_id=1, analytics=repo1),
                },
            )
        )

        tenant_id = tenant_for_shard(strategy, 1)
        report = service.generate_daily_report(tenant_id)

        self.assertEqual(report.tenant_id, tenant_id)
        self.assertEqual(repo1.calls, [tenant_id])
        self.assertEqual(repo0.calls, [])

    def test_missing_replica_shard_configuration_raises_clear_error(self) -> None:
        resolver = ReplicaShardResolver(strategy=HashTenantShardStrategy(2), shards={})

        with self.assertRaises(ShardNotFoundError):
            resolver.resolve("tenant-any")

    def test_missing_primary_shard_configuration_raises_clear_error(self) -> None:
        resolver = TenantShardResolver(strategy=HashTenantShardStrategy(2), shards={})

        with self.assertRaises(ShardNotFoundError):
            resolver.resolve("tenant-any")

    def test_replication_service_raises_specific_error_for_unknown_shard(self) -> None:
        service = ReplicationService(
            synchronizer=ReplicaSynchronizer(),
            shard_paths={},
        )

        with self.assertRaises(ReplicationError):
            service.replicate_shard(99)

    def test_replica_synchronizer_raises_specific_error_for_missing_primary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = ShardDatabasePaths(
                primary=Path(temp_dir) / "missing-primary.db",
                replica=Path(temp_dir) / "replica.db",
            )

            with self.assertRaises(ReplicationError):
                ReplicaSynchronizer().synchronize(paths)


@dataclass
class RecordingAnalyticsRepository(AnalyticsRepository):
    name: str
    calls: list[str] = field(default_factory=list)

    def build_tenant_report(self, tenant_id: str) -> TenantReport:
        self.calls.append(tenant_id)
        return TenantReport(
            tenant_id=tenant_id,
            active_users=10,
            inactive_users=2,
            total_balance=Decimal("230.50"),
        )


def tenant_for_shard(strategy: HashTenantShardStrategy, expected_shard: int) -> str:
    for candidate in range(500):
        tenant_id = f"tenant-{candidate}"
        if strategy.shard_for(tenant_id) == expected_shard:
            return tenant_id
    raise AssertionError("failed to find tenant for shard")


if __name__ == "__main__":
    unittest.main()
