"""Prompt Builder: schema-aware prompt with policy constraints."""
from typing import List

from db_manager import SchemaInfo
from sql_safety import MAX_ROWS


def build_system_prompt(schema: SchemaInfo) -> str:
    if schema.tables:
        lines = []
        for t in schema.tables:
            cols = ", ".join(f"{c.name} ({c.type or 'ANY'})" for c in t.columns)
            lines.append(f"- Table {t.name}: {cols}")
        schema_text = "\n".join(lines)
    else:
        schema_text = "The database is not initialized; no tables are available."
    return (
        "You convert English questions to SQLite SQL.\n"
        "The database has the following schema:\n"
        f"{schema_text}\n\n"
        "Rules:\n"
        "- Output exactly one SQL statement and nothing else (no explanation, no markdown).\n"
        "- Use only SELECT or WITH ... SELECT. Never use INSERT, UPDATE, DELETE, DROP, ALTER, "
        "CREATE, ATTACH, PRAGMA or any other write/schema/admin operation.\n"
        f"- Use SQLite syntax. Prefer LIMIT when listing rows; never exceed LIMIT {MAX_ROWS}.\n\n"
        "Example 1 - How many records are present? -> SELECT COUNT(*) FROM Students;\n"
        "Example 2 - Tell me all the students studying in MCom class? -> "
        "SELECT * FROM Students WHERE class = 'MCom';\n"
    )


def build_contents(system_prompt: str, question: str) -> List[str]:
    return [system_prompt, question]
