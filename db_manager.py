"""DB Manager: existence check, safe initialization and schema inspection."""
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

DB_PATH = "data.db"
SAMPLE_TABLE = "Students"

_SAMPLE_ROWS = [
    ("Sijo", "BTech", 75, "JSW"),
    ("Lijo", "MTech", 69, "TCS"),
    ("Rijo", "BSc", 79, "WIPRO"),
    ("Sibin", "MSc", 89, "INFOSYS"),
    ("Dilsha", "MCom", 99, "Cyient"),
]


@dataclass
class InitResult:
    # "created": table created and seeded; "seeded": table existed but was empty;
    # "already_present": table has data, nothing changed.
    status: str
    message: str


@dataclass
class ColumnInfo:
    name: str
    type: str


@dataclass
class TableInfo:
    name: str
    columns: List[ColumnInfo] = field(default_factory=list)


@dataclass
class SchemaInfo:
    tables: List[TableInfo] = field(default_factory=list)


def db_exists(db_path: str = DB_PATH) -> bool:
    """True if the file exists and looks like a SQLite database (or is empty)."""
    if not os.path.isfile(db_path):
        return False
    try:
        with open(db_path, "rb") as f:
            header = f.read(16)
    except OSError:
        return False
    return header == b"" or header == b"SQLite format 3\x00"


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def connect_readonly(db_path: str = DB_PATH) -> sqlite3.Connection:
    uri_path = Path(db_path).resolve().as_posix().replace("?", "%3f").replace("#", "%23")
    return sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def initialize_if_needed(db_path: str = DB_PATH) -> InitResult:
    """Create the sample table if missing and seed it only when empty.

    Never deletes or overwrites existing rows.
    """
    conn = connect(db_path)
    try:
        existed = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? COLLATE NOCASE",
            (SAMPLE_TABLE,),
        ).fetchone() is not None
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {SAMPLE_TABLE}"
            "(name VARCHAR(30), class VARCHAR(10), marks INT, company VARCHAR(30))"
        )
        count = conn.execute(f"SELECT COUNT(*) FROM {SAMPLE_TABLE}").fetchone()[0]
        if count == 0:
            conn.executemany(
                f"INSERT INTO {SAMPLE_TABLE} VALUES (?, ?, ?, ?)", _SAMPLE_ROWS
            )
            conn.commit()
            if existed:
                return InitResult("seeded", "Table was empty; sample data inserted.")
            return InitResult("created", "Tables created and sample data inserted.")
        conn.commit()
        return InitResult("already_present", "Database already contains data; nothing changed.")
    finally:
        conn.close()


def get_schema(db_path: str = DB_PATH) -> SchemaInfo:
    """Read tables/columns. Returns an empty schema if the DB is missing."""
    if not db_exists(db_path):
        return SchemaInfo()
    conn = connect_readonly(db_path)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        tables = []
        for name in names:
            cols = [ColumnInfo(r[1], r[2]) for r in conn.execute(f"PRAGMA table_info({_quote(name)})")]
            tables.append(TableInfo(name, cols))
        return SchemaInfo(tables)
    finally:
        conn.close()
