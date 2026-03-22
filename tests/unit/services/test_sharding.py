from __future__ import annotations

import unittest

from src.multi_tenant_directory.services.sharding import HashTenantShardStrategy


class HashTenantShardStrategyTests(unittest.TestCase):
    def test_shard_strategy_is_deterministic_for_same_tenant(self) -> None:
        strategy = HashTenantShardStrategy(2)
        tenant_id = "tenant-deterministic"

        first = strategy.shard_for(tenant_id)
        second = strategy.shard_for(tenant_id)

        self.assertEqual(first, second)

    def test_invalid_shard_count_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            HashTenantShardStrategy(0)


if __name__ == "__main__":
    unittest.main()
