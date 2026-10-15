import sqlite3

import pytest

import db_manager
from db_manager import db_exists, get_schema, initialize_if_needed
from prompt_builder import build_contents, build_system_prompt
from query_executor import run_query
from sql_safety import validate_and_sanitize

DDL = "CREATE TABLE Students(name VARCHAR(30), class VARCHAR(10), marks INT, company VARCHAR(30))"


def count(path):
    c = sqlite3.connect(path)
    try:
        return c.execute("SELECT COUNT(*) FROM Students").fetchone()[0]
    finally:
        c.close()


def test_missing_db_not_created_by_exists_or_schema(tmp_path):
    p = str(tmp_path / "data.db")
    assert not db_exists(p)
    assert get_schema(p).tables == []
    assert not (tmp_path / "data.db").exists()


def test_initialize_creates_and_seeds(tmp_path):
    p = str(tmp_path / "data.db")
    assert initialize_if_needed(p).status == "created"
    assert db_exists(p)
    assert count(p) == 5
    t = get_schema(p).tables[0]
    assert t.name == "Students"
    assert [c.name for c in t.columns] == ["name", "class", "marks", "company"]


def test_initialize_twice_is_idempotent(tmp_path):
    p = str(tmp_path / "data.db")
    initialize_if_needed(p)
    assert initialize_if_needed(p).status == "already_present"
    assert count(p) == 5


def test_non_empty_db_not_reseeded_or_overwritten(tmp_path):
    p = str(tmp_path / "data.db")
    c = sqlite3.connect(p)
    c.execute(DDL)
    c.execute("INSERT INTO Students VALUES ('Only','X',1,'Y')")
    c.commit()
    c.close()
    assert initialize_if_needed(p).status == "already_present"
    c = sqlite3.connect(p)
    assert c.execute("SELECT name FROM Students").fetchall() == [("Only",)]
    c.close()


def test_empty_existing_table_gets_seeded(tmp_path):
    p = str(tmp_path / "data.db")
    c = sqlite3.connect(p)
    c.execute(DDL)
    c.commit()
    c.close()
    assert initialize_if_needed(p).status == "seeded"
    assert count(p) == 5


def test_invalid_file_not_treated_as_db(tmp_path):
    f = tmp_path / "data.db"
    f.write_bytes(b"this is not sqlite at all")
    assert not db_exists(str(f))


def test_executor_caps_rows_at_100(tmp_path):
    p = str(tmp_path / "big.db")
    c = sqlite3.connect(p)
    c.execute(DDL)
    c.executemany("INSERT INTO Students VALUES (?,?,?,?)", [(f"n{i}", "c", i, "x") for i in range(500)])
    c.commit()
    c.close()
    for sql in ("SELECT * FROM Students", "SELECT * FROM Students LIMIT 1000"):
        res = run_query(p, validate_and_sanitize(sql).sanitized_sql)
        assert res.returned_rows == 100
        assert res.columns == ["name", "class", "marks", "company"]
    assert run_query(p, "SELECT * FROM Students").returned_rows == 100  # fetchmany backstop


def test_executor_is_read_only(tmp_path):
    p = str(tmp_path / "data.db")
    initialize_if_needed(p)
    with pytest.raises(sqlite3.Error):
        run_query(p, "DELETE FROM Students")
    assert count(p) == 5


def test_prompt_uses_live_schema(tmp_path):
    p = str(tmp_path / "data.db")
    initialize_if_needed(p)
    prompt = build_system_prompt(get_schema(p))
    assert "Table Students: name (VARCHAR(30))" in prompt
    assert "100" in prompt
    assert build_contents(prompt, "q") == [prompt, "q"]
    assert "not initialized" in build_system_prompt(db_manager.SchemaInfo())
