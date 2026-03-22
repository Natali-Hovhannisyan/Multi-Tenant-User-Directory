from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    data_dir: str = os.getenv("APP_DATA_DIR", "data")
    shard_count: int = int(os.getenv("SHARD_COUNT", "2"))
    session_backend: str = os.getenv("SESSION_BACKEND", "memory")
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
