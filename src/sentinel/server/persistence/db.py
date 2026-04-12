from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


def _split_sql_migration_statements(sql: str) -> list[str]:
    """
    Split migration file text into executable statements.

    Naive ``sql.split(";")`` breaks on semicolons inside ``--`` line comments (and
    would break on ``;`` inside string literals). This scanner skips full-line
    ``--`` comments and respects single-quoted SQL string literals (``''`` escape).
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    in_squote = False

    def flush() -> None:
        stmt = "".join(buf).strip()
        buf.clear()
        if stmt:
            statements.append(stmt)

    while i < n:
        c = sql[i]

        if not in_squote:
            if c == "-" and i + 1 < n and sql[i + 1] == "-":
                while i < n and sql[i] != "\n":
                    i += 1
                continue
            if c == "'":
                in_squote = True
                buf.append(c)
                i += 1
                continue
            if c == ";":
                flush()
                i += 1
                continue
        else:
            buf.append(c)
            if c == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                in_squote = False
            i += 1
            continue

        buf.append(c)
        i += 1

    flush()
    return statements


def apply_migrations(database_url: str) -> None:
    migrations_dir = _migrations_dir()
    sql_paths = sorted(migrations_dir.glob("*.sql"))
    if not sql_paths:
        return

    con = connect(database_url)
    try:
        cur = con.cursor()
        for sql_path in sql_paths:
            raw = sql_path.read_text(encoding="utf-8")
            for stmt in _split_sql_migration_statements(raw):
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
    return [dict(zip(cols, [_normalize(v) for v in row], strict=False)) for row in cur.fetchall()]


def _normalize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    # pg8000 returns uuid.UUID for uuid columns
    if value.__class__.__name__ == "UUID":  # pragma: no cover
        return str(value)
    return value


def fetch_one(con: pg8000.dbapi.Connection, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    rows = fetch_all(con, sql, params)
    return rows[0] if rows else None
