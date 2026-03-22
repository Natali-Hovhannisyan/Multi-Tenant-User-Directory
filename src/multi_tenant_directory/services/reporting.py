from __future__ import annotations

from dataclasses import dataclass
import logging

from src.multi_tenant_directory.domain.models import TenantReport
from src.multi_tenant_directory.exceptions import ShardNotFoundError
from src.multi_tenant_directory.ports.repositories import AnalyticsRepository
from src.multi_tenant_directory.services.sharding import ShardStrategy

logger = logging.getLogger(__name__)


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
        logger.debug("Resolved tenant to replica shard %s", shard_id)
        try:
            return self._shards[shard_id]
        except KeyError as exc:
            logger.error("Missing replica shard configuration for tenant %s", tenant_id)
            raise ShardNotFoundError(
                f"missing replica shard for tenant {tenant_id}"
            ) from exc


class AnalyticsReportService:
    def __init__(self, shard_resolver: ReplicaShardResolver) -> None:
        self._shard_resolver = shard_resolver

    def generate_daily_report(self, tenant_id: str) -> TenantReport:
        logger.info("Generating daily report for tenant %s", tenant_id)
        shard = self._shard_resolver.resolve(tenant_id)
        report = shard.analytics.build_tenant_report(tenant_id)
        logger.debug("Generated daily report for tenant %s", tenant_id)
        return report
