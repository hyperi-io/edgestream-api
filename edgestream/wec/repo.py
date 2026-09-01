"""
Project:   edgestream-api
File:      edgestream/wec/repo.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from typing import List, Optional, Any, Dict
import json
import os
from sqlalchemy import (
    create_engine, Table, Column, MetaData, Integer, String, Boolean,
    Text, select, insert, update, delete
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from edgestream.wec.models import SubscriptionRow, SubscriptionPayload

metadata = MetaData()

def _is_postgres(engine: Engine) -> bool:
    return engine.url.get_backend_name().startswith("postgresql")

def _json_col(engine: Engine, name: str):
    if _is_postgres(engine):
        return Column(name, JSONB)
    return Column(name, Text)  # store as TEXT (JSON serialized)

def make_tables(engine: Engine) -> Table:
    """
    Define the `subscriptions` table once on this module's metadata and reuse it.
    Avoids 'Table "subscriptions" is already defined for this MetaData instance'
    errors when called multiple times.
    """
    # If we've already defined it, just reuse
    if "subscriptions" in metadata.tables:
        subs = metadata.tables["subscriptions"]
        metadata.create_all(engine, tables=[subs])
        return subs

    subscriptions = Table(
        "subscriptions",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(255), unique=True, nullable=False),
        Column("version", String(255), nullable=False),
        Column("uri", String(1024)),
        _json_col(engine, "query"),
        Column("heartbeat_interval", Integer, nullable=False, default=3600),
        Column("connection_retry_count", Integer, nullable=False, default=0),
        Column("connection_retry_interval", Integer, nullable=False, default=60),
        Column("max_time", Integer, nullable=False, default=30),
        Column("max_envelope_size", Integer, nullable=False, default=512000),
        Column("enabled", Boolean, nullable=False, default=True),
        Column("read_existing_events", Boolean, nullable=False, default=True),
        Column("content_format", String(64), nullable=False, default="RenderedText"),
        Column("ignore_channel_error", Boolean, nullable=False, default=True),
        Column("locale", String(64)),
        Column("data_locale", String(64)),
        _json_col(engine, "permitted"),
        _json_col(engine, "prohibited"),
    )

    metadata.create_all(engine, tables=[subscriptions])
    return subscriptions

def get_engine(db_url: str) -> Engine:
    """
    Create SQLAlchemy Engine from either a full URL (e.g.
    'sqlite:////var/lib/pywec/pywec.db', 'postgresql://user:pass@host/db')
    or a bare filesystem path (e.g. '/var/lib/pywec/pywec.db').

    For SQLite, if the DB file does not exist we *do not* create it – we
    raise an OperationalError so the API can treat this as
    "WEC not installed/configured".
    """
    if "://" not in db_url:
        # Absolute path -> sqlite:////var/lib/pywec/pywec.db
        # Relative path -> sqlite:///relative/path.db
        if db_url.startswith("/"):
            db_url = f"sqlite:///{db_url}"  # gives sqlite:////var/lib/pywec/pywec.db
        else:
            db_url = f"sqlite:///{db_url}"

    # Special handling for SQLite file URLs: don't auto-create the file
    if db_url.startswith("sqlite:///"):
        # 'sqlite:////var/lib/pywec/pywec.db' -> '/var/lib/pywec/pywec.db'
        db_path = db_url.replace("sqlite:///", "", 1)

        if db_path != ":memory:" and not os.path.exists(db_path):
            raise OperationalError(
                "unable to open database file",
                params=None,
                orig=Exception("unable to open database file"),
            )

    engine = create_engine(db_url, future=True, pool_pre_ping=True)
    return engine

def _dumps_if_needed(engine: Engine, v: Any) -> Any:
    if v is None:
        return None
    return v if _is_postgres(engine) else json.dumps(v)

def _loads_if_needed(engine: Engine, v: Any) -> Any:
    if v is None:
        return None
    return v if _is_postgres(engine) else json.loads(v)

def _row_to_model(engine: Engine, d: Dict[str, Any]) -> SubscriptionRow:
    return SubscriptionRow(
        id=d["id"],
        name=d["name"],
        version=d["version"],
        uri=d["uri"],
        query=_loads_if_needed(engine, d["query"]) or [],
        heartbeat_interval=d["heartbeat_interval"],
        connection_retry_count=d["connection_retry_count"],
        connection_retry_interval=d["connection_retry_interval"],
        max_time=d["max_time"],
        max_envelope_size=d["max_envelope_size"],
        enabled=d["enabled"],
        read_existing_events=d["read_existing_events"],
        content_format=d["content_format"],
        ignore_channel_error=d["ignore_channel_error"],
        locale=d["locale"],
        data_locale=d["data_locale"],
        permitted=_loads_if_needed(engine, d["permitted"]) or [],
        prohibited=_loads_if_needed(engine, d["prohibited"]) or [],
    )

def list_subscriptions(db_url: str) -> List[SubscriptionRow]:
    engine = get_engine(db_url)
    subs = make_tables(engine)
    with engine.connect() as conn:
        rows = conn.execute(select(subs).order_by(subs.c.id)).mappings().all()
    return [_row_to_model(engine, dict(r)) for r in rows]

def create_subscription(db_url: str, payload: SubscriptionPayload) -> SubscriptionRow:
    engine = get_engine(db_url)
    subs = make_tables(engine)
    record = payload.model_dump()
    record["query"] = _dumps_if_needed(engine, record["query"])
    record["permitted"] = _dumps_if_needed(engine, record["permitted"])
    record["prohibited"] = _dumps_if_needed(engine, record["prohibited"])

    with engine.begin() as conn:
        exists = conn.execute(
            select(subs.c.id).where(subs.c.name == payload.name)
        ).scalar_one_or_none()
        if exists:
            raise ValueError(f"Subscription '{payload.name}' already exists")
        res = conn.execute(insert(subs).values(**record).returning(subs))
        row = res.mappings().one()
    return _row_to_model(engine, dict(row))

def update_subscription(db_url: str, sub_id: int, payload: SubscriptionPayload) -> SubscriptionRow:
    engine = get_engine(db_url)
    subs = make_tables(engine)
    record = payload.model_dump()
    record["query"] = _dumps_if_needed(engine, record["query"])
    record["permitted"] = _dumps_if_needed(engine, record["permitted"])
    record["prohibited"] = _dumps_if_needed(engine, record["prohibited"])

    with engine.begin() as conn:
        # Keep name unique if changed
        if record["name"]:
            clash = conn.execute(
                select(subs.c.id).where(
                    (subs.c.name == record["name"]) & (subs.c.id != sub_id)
                )
            ).scalar_one_or_none()
            if clash:
                raise ValueError(
                    f"Another subscription already uses name '{record['name']}'"
                )
        res = conn.execute(
            update(subs)
            .where(subs.c.id == sub_id)
            .values(**record)
            .returning(subs)
        )
        row = res.mappings().one_or_none()
        if not row:
            raise ValueError(f"Subscription id {sub_id} not found")
    return _row_to_model(engine, dict(row))

def delete_subscription(db_url: str, sub_id: int) -> None:
    engine = get_engine(db_url)
    subs = make_tables(engine)
    with engine.begin() as conn:
        res = conn.execute(delete(subs).where(subs.c.id == sub_id))
        if res.rowcount == 0:
            raise ValueError(f"Subscription id {sub_id} not found")
