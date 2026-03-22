from __future__ import annotations

from dataclasses import dataclass

from src.multi_tenant_directory.domain.models import TenantReport
from src.multi_tenant_directory.ports.repositories import AnalyticsRepository
from src.multi_tenant_directory.services.sharding import ShardStrategy


@dataclass(frozen=True)
class ReplicaShardContext:
    shard_id: int
    analytics: AnalyticsRepository


class ReplicaShardResolver:
    def __init__(
        self, strategy: ShardStrategy, shards: dict[int, ReplicaShardContext]
    ) -> None:
        self._strategy = strategy
        self._shards = shards

    def resolve(self, tenant_id: str) -> ReplicaShardContext:
        shard_id = self._strategy.shard_for(tenant_id)
        try:
            return self._shards[shard_id]
        except KeyError as exc:
            raise LookupError(f"missing replica shard for tenant {tenant_id}") from exc


class AnalyticsReportService:
    def __init__(self, shard_resolver: ReplicaShardResolver) -> None:
        self._shard_resolver = shard_resolver

    def generate_daily_report(self, tenant_id: str) -> TenantReport:
        shard = self._shard_resolver.resolve(tenant_id)
        return shard.analytics.build_tenant_report(tenant_id)
