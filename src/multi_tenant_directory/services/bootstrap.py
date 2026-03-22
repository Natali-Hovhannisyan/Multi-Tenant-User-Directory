from __future__ import annotations

from pathlib import Path
from typing import cast
import redis

from src.multi_tenant_directory.config import AppConfig
from src.multi_tenant_directory.exceptions import SessionStoreError
from src.multi_tenant_directory.infrastructure.sessions import (
    InMemorySessionStore,
    RedisClientProtocol,
    RedisSessionStore,
)
from src.multi_tenant_directory.infrastructure.sqlite import (
    ReplicaSynchronizer,
    ShardDatabasePaths,
    SqliteAnalyticsRepository,
    SqliteBillingRepository,
    SqliteConnectionFactory,
    SqliteUserRepository,
)
from src.multi_tenant_directory.services.directory import (
    TenantShardContext,
    TenantShardResolver,
    UserDirectoryService,
)
from src.multi_tenant_directory.services.reporting import (
    AnalyticsReportService,
    ReplicaShardContext,
    ReplicaShardResolver,
)
from src.multi_tenant_directory.services.replication import ReplicationService
from src.multi_tenant_directory.services.sharding import HashTenantShardStrategy


class ApplicationContainer:
    def __init__(self, config: AppConfig) -> None:
        strategy = HashTenantShardStrategy(config.shard_count)
        data_dir = Path(config.data_dir)

        primary_shards: dict[int, TenantShardContext] = {}
        replica_shards: dict[int, ReplicaShardContext] = {}
        shard_paths: dict[int, ShardDatabasePaths] = {}

        for shard_id in range(config.shard_count):
            primary_path = data_dir / f"primary-shard-{shard_id}.db"
            replica_path = data_dir / f"replica-shard-{shard_id}.db"
            primary_factory = SqliteConnectionFactory(primary_path)
            replica_factory = SqliteConnectionFactory(replica_path)

            primary_shards[shard_id] = TenantShardContext(
                shard_id=shard_id,
                users=SqliteUserRepository(primary_factory),
                billing=SqliteBillingRepository(primary_factory),
            )
            replica_shards[shard_id] = ReplicaShardContext(
                shard_id=shard_id,
                analytics=SqliteAnalyticsRepository(replica_factory),
            )
            shard_paths[shard_id] = ShardDatabasePaths(
                primary=primary_path, replica=replica_path
            )

        self.user_directory: UserDirectoryService = UserDirectoryService(
            shard_resolver=TenantShardResolver(
                strategy=strategy, shards=primary_shards
            ),
            session_store=self._build_session_store(config),
        )
        self.reporting: AnalyticsReportService = AnalyticsReportService(
            shard_resolver=ReplicaShardResolver(
                strategy=strategy, shards=replica_shards
            )
        )
        self.replication: ReplicationService = ReplicationService(
            synchronizer=ReplicaSynchronizer(),
            shard_paths=shard_paths,
        )

    @staticmethod
    def _build_session_store(
        config: AppConfig,
    ) -> InMemorySessionStore | RedisSessionStore:
        if config.session_backend == "memory":
            return InMemorySessionStore()

        if config.session_backend == "redis":
            return RedisSessionStore(
                client=cast(
                    RedisClientProtocol,
                    redis.Redis(
                        host=config.redis_host,
                        port=config.redis_port,
                        db=config.redis_db,
                    ),
                )
            )

        raise SessionStoreError(
            f"unsupported session backend: {config.session_backend}"
        )
