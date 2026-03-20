from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pg8000.dbapi


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def parse_database_url(database_url: str) -> DbConfig:
    parsed = urlparse(database_url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError("DATABASE_URL must be postgresql://...")
    if not parsed.hostname or not parsed.username or parsed.password is None:
        raise ValueError("DATABASE_URL must include host, username, and password.")
    db_name = (parsed.path or "").lstrip("/")
    if not db_name:
        raise ValueError("DATABASE_URL must include a database name path.")
    return DbConfig(
        host=parsed.hostname,
        port=int(parsed.port or 5432),
        user=parsed.username,
        password=parsed.password,
        database=db_name,
    )


def connect(database_url: str) -> pg8000.dbapi.Connection:
    cfg = parse_database_url(database_url)
    return pg8000.dbapi.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        timeout=5,
    )


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def apply_migrations(database_url: str) -> None:
    sql_path = _migrations_dir() / "001_init.sql"
    sql = sql_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    con = connect(database_url)
    try:
        cur = con.cursor()
        for stmt in statements:
            cur.execute(stmt)
        con.commit()
    finally:
        try:
            con.close()
        except Exception:  # pragma: no cover
            pass


def fetch_all(con: pg8000.dbapi.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    cur = con.cursor()
    cur.execute(sql, params)
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def fetch_one(con: pg8000.dbapi.Connection, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    rows = fetch_all(con, sql, params)
    return rows[0] if rows else None

