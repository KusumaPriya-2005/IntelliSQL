"""Query Executor: runs already-sanitized SQL on a read-only connection."""
from dataclasses import dataclass
from typing import List

from db_manager import connect_readonly
from sql_safety import MAX_ROWS


@dataclass
class QueryResult:
    columns: List[str]
    rows: list
    returned_rows: int


def run_query(db_path: str, sql: str) -> QueryResult:
    conn = connect_readonly(db_path)
    try:
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchmany(MAX_ROWS)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        return QueryResult(columns, rows, len(rows))
    finally:
        conn.close()
