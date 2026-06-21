import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generic, TypeVar
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field, create_engine, Session

engine = create_engine("sqlite:///pqa.db")

def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS docs (
            doc_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_hash TEXT NOT NULL UNIQUE,
            file_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            error_msg TEXT,
            chunk_count INTEGER DEFAULT 0,
            embed_model TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()

def get_db(data_dir: str = "data") -> sqlite3.Connection:
    db_path = Path(data_dir) / "pqa.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):

    model_cls: type[T]
    table: str = ""
    pk: str = "rowid"

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _dict(self, record: T, *, exclude_none: bool = False) -> dict:
        return record.model_dump(exclude_none=exclude_none, mode="python")

    def _from_row(self, row: sqlite3.Row | None) -> T | None:
        if row is None:
            return None
        return self.model_cls(**dict(row))

    def _rows(self, rows: list[sqlite3.Row]) -> list[T]:
        return [self._from_row(r) for r in rows]

    def insert(self, record: T, *, auto_commit: bool = True) -> T:
        d = self._dict(record)
        cols = ", ".join(d)
        q = ", ".join("?" for _ in d)
        self._conn.execute(
            f"INSERT INTO {self.table} ({cols}) VALUES ({q})",
            list(d.values()),
        )
        if auto_commit:
            self._conn.commit()
        return record

    def get(self, pk_val: str) -> T | None:
        row = self._conn.execute(
            f"SELECT * FROM {self.table} WHERE {self.pk} = ?",
            (pk_val,),
        ).fetchone()
        return self._from_row(row)

    def update(self, record: T) -> T:
        d = self._dict(record, exclude_none=True)
        pk_val = d.pop(self.pk, None)
        if pk_val is None:
            raise ValueError(f"主键 {self.pk} 不能为空")
        sets = ", ".join(f"{k} = ?" for k in d)
        self._conn.execute(
            f"UPDATE {self.table} SET {sets} WHERE {self.pk} = ?",
            list(d.values()) + [pk_val],
        )
        self._conn.commit()
        return record

    def delete(self, pk_val: str):
        self._conn.execute(
            f"DELETE FROM {self.table} WHERE {self.pk} = ?",
            (pk_val,),
        )
        self._conn.commit()

    def list_all(self, where: str | None = None, params: list | None = None,
                 order: str | None = None) -> list[T]:
        sql = f"SELECT * FROM {self.table}"
        if where:
            sql += f" WHERE {where}"
        if order:
            sql += f" ORDER BY {order}"
        return self._rows(self._conn.execute(sql, params or []).fetchall())

    def get_one(self, where: str, params: list | None = None) -> T | None:
        row = self._conn.execute(
            f"SELECT * FROM {self.table} WHERE {where}",
            params or [],
        ).fetchone()
        return self._from_row(row)
