# Low-Level Design (LLD) — IntelliSQL Approved Enhancements

**Status:** Proposal for human review. This LLD specifies modules, responsibilities, and key algorithms to implement the approved enhancements in the existing Python + Streamlit + SQLite + Gemini solution.

---

## 1. Proposed module structure (logical)

> This is a design proposal. The current repo is mostly in `app.py`. The design assumes extracting helper modules for clarity, but the implementation may also be done inside `app.py` if desired.

Recommended logical modules:

- `db_manager.py`
- `schema_introspector.py` (can be merged into db_manager)
- `prompt_builder.py`
- `sql_safety.py`
- `query_executor.py`

---

## 2. DB initialization & schema inspection

### 2.1 DBManager

#### 2.1.1 Constants
- `DB_PATH = "data.db"`
- `SAMPLE_TABLE = "Students"` (canonical table name aligned to existing `sql.py`)

> Note: Current prompt uses `STUDENTS`. This design normalizes to the *actual* SQLite table name returned by schema inspection.

#### 2.1.2 `db_exists(db_path: str) -> bool`
- **Behavior:** returns True if file exists and is a valid SQLite file (basic check can be `os.path.exists`; optional stronger check by attempting connection).
- **Edge cases:**
  - File exists but not a SQLite DB → return False or raise `DBInvalidError`.

#### 2.1.3 `connect(db_path: str) -> sqlite3.Connection`
- Opens a connection with safe defaults.
- Recommended: `sqlite3.connect(db_path)`.

#### 2.1.4 `initialize_if_needed(db_path: str) -> InitResult`
- **Trigger:** called when DB missing or when schema not present.
- **Rules (approved):**
  - Initialize only when required.
  - Create tables safely.
  - Seed only when the relevant table is empty.
  - Never overwrite existing data.
  - No “reset DB” capability.

**Algorithm (pseudo):**
1. Connect to `db_path` (this creates file if missing).
2. Execute `CREATE TABLE IF NOT EXISTS Students(...)`.
3. Check if table empty: `SELECT COUNT(*) FROM Students`.
4. If count == 0 → insert sample rows.
5. Commit and close.

**Outputs:**
- `InitResult(status: Literal["created","already_present","seeded","no_seed"], message: str)`

**Failure modes:**
- SQLite exceptions (permissions, locked DB) → UI should show actionable message.

#### 2.1.5 `get_schema(db_path: str) -> SchemaInfo`
- Tables: `SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';`
- Columns per table: `PRAGMA table_info(<table>);`

**SchemaInfo model (example):**
- `SchemaInfo(tables=[TableInfo(name="Students", columns=[ColumnInfo(name="name", type="TEXT"), ...])])`

**Edge cases:**
- DB missing: return empty schema + message; UI offers initialization.
- Tables with reserved words: ensure table name is safely handled when introspecting.

---

## 3. Prompt construction

### 3.1 PromptBuilder

#### 3.1.1 `build_system_prompt(schema: SchemaInfo) -> str`
- Must:
  - Describe the actual schema.
  - Enforce policy constraints in text.
  - Require SQL-only output.
  - Specify SQLite dialect.
  - Encourage LIMIT usage and mention max 100.

**Proposed prompt template (conceptual):**
- Role: “You convert English questions to SQLite SQL.”
- Schema section: list tables/columns.
- Policy section:
  - Output a single SQL statement.
  - Only `SELECT` or `WITH ... SELECT`.
  - Do not use any write/schema/admin operations.
  - Prefer including `LIMIT 100` when listing rows.

#### 3.1.2 `build_contents(system_prompt: str, question: str) -> list[str]`
- Keeps compatibility with current Gemini call: `contents=[system_prompt, question]`.

**Edge cases:**
- Missing schema: prompt should tell model “database not initialized” and ask for a SELECT against known tables only; however execution will be blocked anyway if DB missing.

---

## 4. SQL validation + sanitization

### 4.1 SQLSafetyGate

#### 4.1.1 Normalization helpers
- `strip_markdown_fences(text: str) -> str`
  - Remove ```sql and ```.
- `normalize_whitespace(sql: str) -> str`
  - Collapse repeated whitespace.

#### 4.1.2 Validation rules (approved)
1. **Single statement only**
   - Reject if multiple statements detected.
   - Heuristic: if semicolons appear not at the end, or more than one semicolon.
2. **Read-only**
   - Must start with `SELECT` or `WITH` (case-insensitive, ignoring leading whitespace/comments).
   - Must not contain forbidden keywords/tokens.
3. **Row limit enforcement**
   - Ensure effective limit is <= 100.
   - If query has no LIMIT: append `LIMIT 100`.
   - If query has LIMIT > 100: rewrite to `LIMIT 100`.

#### 4.1.3 Forbidden keyword list
Block if any appear as standalone tokens (case-insensitive):
- DML/DDL/admin: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `TRUNCATE`
- Attach/admin: `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, `REINDEX`, `ANALYZE`
- Transaction controls: `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `RELEASE`

> Note: SQLite allows many operations; this list is intentionally conservative.

#### 4.1.4 `validate_and_sanitize(sql_text: str) -> GateResult`

**GateResult model:**
- `allowed: bool`
- `reason: str | None`
- `sanitized_sql: str | None`
- `limit_applied: bool`

**Algorithm (pseudo):**
1. `sql = strip_markdown_fences(sql_text)`
2. `sql = normalize_whitespace(sql)`
3. If empty → block: “Empty SQL generated.”
4. If multi-statement → block: “Multiple statements are not allowed.”
5. If not startswith `SELECT` or `WITH` → block.
6. If contains forbidden tokens → block.
7. `sql2 = enforce_limit(sql, max_rows=100)`
8. Return allowed with `sql2`.

#### 4.1.5 `enforce_limit(sql: str, max_rows: int = 100) -> tuple[str, bool]`
- If `LIMIT` not present → append `LIMIT 100`.
- If `LIMIT n` and n > 100 → replace with `LIMIT 100`.
- Handle patterns:
  - `LIMIT n`
  - `LIMIT n OFFSET m`
  - `LIMIT m, n` (SQLite supports this MySQL-style form; decide whether to support or block)

**Design choice (recommendation):**
- Support `LIMIT n` and `LIMIT n OFFSET m`.
- If `LIMIT m, n` detected, rewrite to `LIMIT n OFFSET m` if safely parseable; otherwise block with guidance.

---

## 5. Query execution flow

### 5.1 QueryExecutor

#### 5.1.1 `run_query(db_path: str, sql: str) -> QueryResult`
- Steps:
  1. `conn = sqlite3.connect(db_path)`
  2. `cursor = conn.cursor()`
  3. `cursor.execute(sql)`
  4. `rows = cursor.fetchmany(100)` (optional extra safety even if LIMIT applied)
  5. Determine column names: `cursor.description`
  6. Close connection.

**QueryResult model:**
- `columns: list[str]`
- `rows: list[tuple]`
- `returned_rows: int`

**Edge cases:**
- Empty result set: show “No rows returned.”
- Very wide rows: UI should still render.

---

## 6. Streamlit UI behavior (LLD level)

### 6.1 Submit gating (approved)
- Only trigger Gemini call and query execution on button click.
- Avoid `if submit or que:` pattern.

### 6.2 UI blocks
- **DB missing**: show warning + Initialize button.
- **Schema panel**: show tables/columns.
- **Generated SQL**: show in expander.
- **Blocked query**: show reason + SQL (read-only) + rephrase hints.
- **Execution error**: show error + schema reference.

---

## 7. Input/Output contracts

### 7.1 Inputs
- `question: str` — user natural language.
- `GOOGLE_API_KEY: str` — env var.
- `db_path: str` — defaults to `data.db`.

### 7.2 Outputs
- Table results (≤100 rows).
- Validation messages.
- Initialization status.

---

## 8. Edge cases and error handling (detailed)

- **Missing API key**: block query and show setup instructions.
- **Gemini returns markdown or commentary**: strip fences; if still non-SQL, block.
- **Gemini returns multiple statements**: block.
- **Gemini returns write op**: block.
- **User asks for “update marks”**: model may generate UPDATE; block with explanation.
- **Query without LIMIT**: append LIMIT 100.
- **Query with LIMIT 1000**: cap to 100.
- **CTE queries**: allow only if final statement is SELECT and no forbidden tokens.
- **SQL comments**: allow, but ensure validation strips/ignores comments when checking first keyword.

---

## 9. Testing considerations

> No tests exist currently; these are recommendations for future work.

### 9.1 Unit tests
- `SQLSafetyGate`:
  - allows `SELECT ...`
  - allows `WITH ... SELECT ...`
  - blocks `UPDATE/DELETE/DROP`
  - blocks multi-statement
  - enforces/caps limit
- `DBManager.initialize_if_needed`:
  - creates schema idempotently
  - seeds only when empty

### 9.2 Integration tests
- End-to-end (without calling Gemini):
  - feed a known safe SQL and ensure results <=100
  - verify UI flow conditions (can be manual, or automated later)
