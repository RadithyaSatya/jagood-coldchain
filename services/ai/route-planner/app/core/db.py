import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
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

shipment_records = Table(
    "shipment_records",
    metadata,
    Column("shipment_id", String, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # request context
    Column("commodity_type", String, nullable=False, index=True),
    Column("origin_lat", Float, nullable=False),
    Column("origin_lon", Float, nullable=False),
    Column("destination_lat", Float, nullable=False),
    Column("destination_lon", Float, nullable=False),
    Column("departure_time", DateTime(timezone=True), nullable=False, index=True),
    Column("transport_mode_preference", String, nullable=True),
    Column("cold_chain_equipment", String, nullable=False),
    Column("insulation_quality", String, nullable=False),
    Column("ranking_preference", String, nullable=False),
    # recommended route, flattened (mirrors RouteCandidate's key predictive fields)
    Column("recommended_route_id", String, nullable=False),
    Column("transport_mode", String, nullable=False, index=True),
    Column("distance_km", Float, nullable=False),
    Column("estimated_duration_hours", Float, nullable=False),
    Column("expected_delay_hours", Float, nullable=False, default=0),
    Column("estimated_arrival", DateTime(timezone=True), nullable=False),
    Column("risk_level", String, nullable=False, index=True),
    Column("risk_probability", Float, nullable=False),
    Column("confidence_score", Float, nullable=False),
    Column("historical_delay_avg_hours", Float, nullable=False),
    Column("historical_damage_rate", Float, nullable=False),
    Column("data_quality", String, nullable=False),
    Column("environmental_data_quality", String, nullable=False),
    Column("cargo_temperature_data_quality", String, nullable=False),
    # full-fidelity snapshot (recommended_route + alternative_routes exactly as served)
    Column("prediction_snapshot", JSONB, nullable=False),
    # outcome (governance: PREDICTED until an outcome is reported = first REAL data point)
    Column("outcome_status", String, nullable=False, default="predicted_only", index=True),
    Column("actual_delay_hours", Float, nullable=True),
    Column("actual_damage_occurred", Boolean, nullable=True),
    Column("outcome_notes", Text, nullable=True),
    Column("outcome_reported_at", DateTime(timezone=True), nullable=True),
    # which of recommended_route_id/alternative_routes[].route_id was actually driven,
    # set via POST /shipments/{id}/select-route -- lets weather-delay segment analysis
    # compare against that specific route's own ORS-estimated speed, not a flat constant
    Column("selected_route_id", String, nullable=True),
)

shipment_checkpoints = Table(
    "shipment_checkpoints",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("shipment_id", String, nullable=False, index=True),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("checkpoint_label", String, nullable=True),
)

weather_delay_stats = Table(
    "weather_delay_stats",
    metadata,
    Column("transport_mode", String, primary_key=True),
    Column("weather_severity", String, primary_key=True),
    Column("sample_count", Integer, nullable=False, default=0),
    Column("delay_hours_sum", Float, nullable=False, default=0.0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

corridor_baseline_stats = Table(
    "corridor_baseline_stats",
    metadata,
    Column("transport_mode", String, primary_key=True),
    Column("distance_bucket_km", Integer, primary_key=True),
    Column("sample_count", Integer, nullable=False, default=0),
    Column("delay_hours_sum", Float, nullable=False, default=0.0),
    Column("damage_occurred_count", Integer, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
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


def insert_shipment_record(record: dict) -> None:
    _ensure_schema()
    with engine.begin() as conn:
        conn.execute(shipment_records.insert().values(**record))


def select_shipment_by_id(shipment_id: str) -> dict | None:
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            select(shipment_records).where(shipment_records.c.shipment_id == shipment_id)
        ).mappings().first()
    return dict(row) if row is not None else None


def select_shipments(
    commodity_type: str | None,
    transport_mode: str | None,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    _ensure_schema()
    conditions = []
    if commodity_type is not None:
        conditions.append(shipment_records.c.commodity_type == commodity_type)
    if transport_mode is not None:
        conditions.append(shipment_records.c.transport_mode == transport_mode)
    if date_from is not None:
        conditions.append(shipment_records.c.departure_time >= date_from)
    if date_to is not None:
        conditions.append(shipment_records.c.departure_time <= date_to)

    with engine.connect() as conn:
        count_stmt = select(func.count()).select_from(shipment_records)
        list_stmt = select(shipment_records).order_by(shipment_records.c.created_at.desc()).limit(limit).offset(offset)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)
        total = conn.execute(count_stmt).scalar_one()
        rows = conn.execute(list_stmt).mappings().all()
    return [dict(row) for row in rows], total


def update_shipment_outcome(shipment_id: str, outcome: dict) -> dict | None:
    _ensure_schema()
    with engine.begin() as conn:
        result = conn.execute(
            update(shipment_records)
            .where(shipment_records.c.shipment_id == shipment_id)
            .values(**outcome)
        )
        if result.rowcount == 0:
            return None
        row = conn.execute(
            select(shipment_records).where(shipment_records.c.shipment_id == shipment_id)
        ).mappings().first()
    return dict(row) if row is not None else None


def upsert_corridor_stats(
    transport_mode: str, distance_bucket_km: int, delay_hours: float, damage_occurred: bool
) -> None:
    _ensure_schema()
    stmt = pg_insert(corridor_baseline_stats).values(
        transport_mode=transport_mode,
        distance_bucket_km=distance_bucket_km,
        sample_count=1,
        delay_hours_sum=delay_hours,
        damage_occurred_count=1 if damage_occurred else 0,
        updated_at=dt.datetime.now(dt.timezone.utc),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[corridor_baseline_stats.c.transport_mode, corridor_baseline_stats.c.distance_bucket_km],
        set_={
            "sample_count": corridor_baseline_stats.c.sample_count + stmt.excluded.sample_count,
            "delay_hours_sum": corridor_baseline_stats.c.delay_hours_sum + stmt.excluded.delay_hours_sum,
            "damage_occurred_count": corridor_baseline_stats.c.damage_occurred_count + stmt.excluded.damage_occurred_count,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def get_corridor_stats(transport_mode: str, distance_bucket_km: int) -> dict | None:
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            select(corridor_baseline_stats).where(
                corridor_baseline_stats.c.transport_mode == transport_mode,
                corridor_baseline_stats.c.distance_bucket_km == distance_bucket_km,
            )
        ).mappings().first()
    return dict(row) if row is not None else None


def update_selected_route(shipment_id: str, route_id: str) -> dict | None:
    _ensure_schema()
    with engine.begin() as conn:
        result = conn.execute(
            update(shipment_records)
            .where(shipment_records.c.shipment_id == shipment_id)
            .values(selected_route_id=route_id)
        )
        if result.rowcount == 0:
            return None
        row = conn.execute(
            select(shipment_records).where(shipment_records.c.shipment_id == shipment_id)
        ).mappings().first()
    return dict(row) if row is not None else None


def insert_checkpoints(shipment_id: str, points: list[dict]) -> None:
    _ensure_schema()
    with engine.begin() as conn:
        conn.execute(
            shipment_checkpoints.insert(),
            [{**point, "shipment_id": shipment_id} for point in points],
        )


def select_checkpoints(shipment_id: str) -> list[dict]:
    _ensure_schema()
    with engine.connect() as conn:
        rows = conn.execute(
            select(shipment_checkpoints)
            .where(shipment_checkpoints.c.shipment_id == shipment_id)
            .order_by(shipment_checkpoints.c.recorded_at.asc())
        ).mappings().all()
    return [dict(row) for row in rows]


def upsert_weather_delay_stats(transport_mode: str, weather_severity: str, delay_hours: float) -> None:
    _ensure_schema()
    stmt = pg_insert(weather_delay_stats).values(
        transport_mode=transport_mode,
        weather_severity=weather_severity,
        sample_count=1,
        delay_hours_sum=delay_hours,
        updated_at=dt.datetime.now(dt.timezone.utc),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[weather_delay_stats.c.transport_mode, weather_delay_stats.c.weather_severity],
        set_={
            "sample_count": weather_delay_stats.c.sample_count + stmt.excluded.sample_count,
            "delay_hours_sum": weather_delay_stats.c.delay_hours_sum + stmt.excluded.delay_hours_sum,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def get_weather_delay_stats(transport_mode: str, weather_severity: str) -> dict | None:
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            select(weather_delay_stats).where(
                weather_delay_stats.c.transport_mode == transport_mode,
                weather_delay_stats.c.weather_severity == weather_severity,
            )
        ).mappings().first()
    return dict(row) if row is not None else None
