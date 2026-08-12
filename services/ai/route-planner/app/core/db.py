import datetime as dt

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
metadata = MetaData()

bmkg_cache = Table(
    "bmkg_cache",
    metadata,
    Column("cache_key", String, primary_key=True),
    Column("payload", Text, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
)

_schema_ready = False


def _ensure_schema() -> None:
    """Creates the cache table on first actual use rather than at import time.
    The offline training scripts import this module only transitively (via
    enrichment_service -> temperature_service) for constants and the pure
    temperature-simulation functions -- they never touch the cache, so they
    must not require a reachable Postgres just to be importable."""
    global _schema_ready
    if _schema_ready:
        return
    metadata.create_all(engine)
    _schema_ready = True


def get_cached(cache_key: str, ttl_seconds: int) -> str | None:
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            select(bmkg_cache.c.payload, bmkg_cache.c.fetched_at).where(bmkg_cache.c.cache_key == cache_key)
        ).first()
    if row is None:
        return None
    payload, fetched_at = row
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=dt.timezone.utc)
    age = (dt.datetime.now(dt.timezone.utc) - fetched_at).total_seconds()
    if age > ttl_seconds:
        return None
    return payload


def set_cached(cache_key: str, payload: str) -> None:
    _ensure_schema()
    stmt = pg_insert(bmkg_cache).values(
        cache_key=cache_key, payload=payload, fetched_at=dt.datetime.now(dt.timezone.utc)
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[bmkg_cache.c.cache_key],
        set_={"payload": stmt.excluded.payload, "fetched_at": stmt.excluded.fetched_at},
    )
    with engine.begin() as conn:
        conn.execute(stmt)
