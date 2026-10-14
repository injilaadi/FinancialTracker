"""Settings read from environment variables (set by docker-compose)."""
import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    ml_url: str          # empty = skip categorization on import
    import_workers: int  # max concurrent calls to the ML service during an import
    ml_batch_size: int   # descriptions per ML request
    redis_url: str       # empty = no cache
    cache_enabled: bool  # CACHE_ENABLED=false turns the cache off even when REDIS_URL is set
    cache_ttl_seconds: int


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return Settings(
        database_url=database_url,
        ml_url=os.environ.get("ML_URL", "").rstrip("/"),
        import_workers=_env_int("IMPORT_WORKERS", 1),
        ml_batch_size=_env_int("ML_BATCH_SIZE", 200),
        redis_url=os.environ.get("REDIS_URL", ""),
        cache_enabled=_env_bool("CACHE_ENABLED", True),
        cache_ttl_seconds=_env_int("CACHE_TTL_SECONDS", 300),
    )
