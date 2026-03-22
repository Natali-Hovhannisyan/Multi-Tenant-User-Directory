from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib


class ShardStrategy(ABC):
    @abstractmethod
    def shard_for(self, tenant_id: str) -> int:
        raise NotImplementedError


class HashTenantShardStrategy(ShardStrategy):
    def __init__(self, shard_count: int) -> None:
        if shard_count < 1:
            raise ValueError("shard_count must be positive")
        self._shard_count = shard_count

    def shard_for(self, tenant_id: str) -> int:
        digest = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        return int(digest, 16) % self._shard_count
