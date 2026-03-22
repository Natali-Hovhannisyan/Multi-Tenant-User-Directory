from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    data_dir: str = os.getenv("APP_DATA_DIR", "data")
    shard_count: int = int(os.getenv("SHARD_COUNT", "2"))
