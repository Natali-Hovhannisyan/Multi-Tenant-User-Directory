from __future__ import annotations

import logging

from src.multi_tenant_directory.exceptions import ReplicationError
from src.multi_tenant_directory.infrastructure.sqlite import (
    ReplicaSynchronizer,
    ShardDatabasePaths,
)

logger = logging.getLogger(__name__)


class ReplicationService:
    def __init__(
        self,
        synchronizer: ReplicaSynchronizer,
        shard_paths: dict[int, ShardDatabasePaths],
    ) -> None:
        self._synchronizer = synchronizer
        self._shard_paths = shard_paths

    def replicate_all(self) -> None:
        logger.info("Starting replication across all shards")
        for shard_id in sorted(self._shard_paths):
            self.replicate_shard(shard_id)
        logger.info("Completed replication across all shards")

    def replicate_shard(self, shard_id: int) -> None:
        try:
            shard_paths = self._shard_paths[shard_id]
        except KeyError as exc:
            logger.error("Missing shard paths for shard %s", shard_id)
            raise ReplicationError(f"missing shard paths for shard {shard_id}") from exc

        logger.debug("Replicating shard %s", shard_id)
        self._synchronizer.synchronize(shard_paths)
