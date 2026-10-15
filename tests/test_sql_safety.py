import pytest

from sql_safety import enforce_limit, validate_and_sanitize


def ok(sql):
    r = validate_and_sanitize(sql)
    assert r.allowed, r.reason
    return r


def blocked(sql):
    r = validate_and_sanitize(sql)
    assert not r.allowed
    assert r.sanitized_sql is None
    return r


def test_select_gets_limit_appended():
    r = ok("SELECT * FROM Students;")
    assert r.sanitized_sql == "SELECT * FROM Students LIMIT 100"
    assert r.limit_applied


def test_lowercase_keywords_allowed_and_limited():
    assert ok("select name from students").sanitized_sql == "select name from students LIMIT 100"


def test_lowercase_write_blocked():
    for sql in ("delete from students", "drop table students", "update students set marks=1"):
        blocked(sql)


@pytest.mark.parametrize("sql", [
    "INSERT INTO Students VALUES ('a','b',1,'c')",
    "UPDATE Students SET marks = 0",
    "DELETE FROM Students",
    "DROP TABLE Students",
    "ALTER TABLE Students ADD x INT",
    "CREATE TABLE t(a)",
    "ATTACH DATABASE 'x.db' AS x",
    "PRAGMA table_info(Students)",
    "VACUUM",
    "BEGIN",
    "REPLACE INTO Students VALUES ('a','b',1,'c')",
])
def test_non_select_blocked(sql):
    assert blocked(sql).reason == "Only SELECT queries are allowed."


def test_multiple_statements_blocked():
    r = blocked("SELECT 1; DROP TABLE Students")
    assert r.reason == "Multiple SQL statements are not allowed."
    blocked("SELECT 1; SELECT 2")


def test_trailing_semicolon_and_whitespace_ok():
    assert ok("  SELECT 1 ;  \n ").sanitized_sql == "SELECT 1 LIMIT 100"


def test_semicolon_inside_string_is_not_multi_statement():
    assert ok("SELECT * FROM Students WHERE name = 'a;b'").allowed


def test_forbidden_word_inside_string_literal_is_ok():
    assert ok("SELECT * FROM Students WHERE name = 'drop table'").allowed


def test_leading_comments_ignored_for_first_keyword():
    assert ok("-- hi\n/* x */ SELECT 1").sanitized_sql == "SELECT 1 LIMIT 100"


def test_statement_hidden_in_comment_is_stripped():
    assert ok("SELECT 1 -- ; DROP TABLE Students").sanitized_sql == "SELECT 1 LIMIT 100"


def test_trailing_line_comment_does_not_swallow_limit():
    assert ok("SELECT 1 -- note").sanitized_sql.endswith("LIMIT 100")


def test_comment_before_write_statement_blocked():
    blocked("/* SELECT */ DELETE FROM Students")


def test_comment_between_statements_still_multi():
    assert blocked("SELECT 1; /* c */ DROP TABLE Students").reason.startswith("Multiple")


def test_cte_select_allowed():
    assert ok("WITH t AS (SELECT * FROM Students) SELECT * FROM t").sanitized_sql.endswith("LIMIT 100")


def test_cte_with_write_blocked():
    blocked("WITH t AS (SELECT 1) DELETE FROM Students")
    blocked("WITH t AS (SELECT 1) INSERT INTO Students SELECT * FROM t")
    blocked("WITH t AS (DELETE FROM Students RETURNING *) SELECT * FROM t")


def test_with_without_select_blocked():
    blocked("WITH t AS (SELECT 1)")


def test_limit_over_100_capped():
    r = ok("SELECT * FROM Students LIMIT 1000")
    assert r.sanitized_sql == "SELECT * FROM Students LIMIT 100"
    assert r.limit_applied


def test_limit_under_100_kept():
    r = ok("SELECT * FROM Students LIMIT 5")
    assert r.sanitized_sql == "SELECT * FROM Students LIMIT 5"
    assert not r.limit_applied


def test_lowercase_limit_capped():
    assert ok("select * from students limit 500").sanitized_sql == "select * from students LIMIT 100"


def test_limit_offset_capped():
    assert ok("SELECT * FROM s LIMIT 500 OFFSET 10").sanitized_sql == "SELECT * FROM s LIMIT 100 OFFSET 10"


def test_mysql_style_limit_rewritten():
    assert ok("SELECT * FROM s LIMIT 10, 500").sanitized_sql == "SELECT * FROM s LIMIT 100 OFFSET 10"


def test_non_numeric_limit_blocked():
    blocked("SELECT * FROM s LIMIT (SELECT 1000)")
    blocked("SELECT * FROM s LIMIT -1")
    blocked("SELECT * FROM s LIMIT 1+1000")


def test_inner_limit_does_not_satisfy_outer_cap():
    assert ok("SELECT * FROM (SELECT * FROM s LIMIT 5)").sanitized_sql.endswith(") LIMIT 100")


def test_markdown_fences_stripped():
    assert ok("```sql\nSELECT 1\n```").sanitized_sql == "SELECT 1 LIMIT 100"


def test_empty_blocked():
    assert blocked("").reason == "The model did not generate a valid SQL query."
    blocked("   ")
    blocked("-- only a comment")
    blocked(";")


def test_commentary_blocked():
    blocked("Here is your query: SELECT 1")


def test_case_end_and_replace_function_allowed():
    assert ok("SELECT CASE WHEN marks > 1 THEN 'a' ELSE 'b' END, replace(name,'a','b') FROM s").allowed


def test_enforce_limit_direct():
    assert enforce_limit("SELECT 1") == ("SELECT 1 LIMIT 100", True)
