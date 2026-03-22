from __future__ import annotations

from src.multi_tenant_directory.infrastructure.sqlite import (
    ReplicaSynchronizer,
    ShardDatabasePaths,
)


class ReplicationService:
    def __init__(
        self,
        synchronizer: ReplicaSynchronizer,
        shard_paths: dict[int, ShardDatabasePaths],
    ) -> None:
        self._synchronizer = synchronizer
        self._shard_paths = shard_paths

    def replicate_all(self) -> None:
        for shard_id in sorted(self._shard_paths):
            self.replicate_shard(shard_id)

    def replicate_shard(self, shard_id: int) -> None:
        self._synchronizer.synchronize(self._shard_paths[shard_id])
