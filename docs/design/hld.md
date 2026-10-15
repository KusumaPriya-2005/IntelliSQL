# High-Level Design (HLD) — IntelliSQL Approved Enhancements

**Status:** Proposal for human design review. This HLD covers the approved enhancements for IntelliSQL while keeping the existing Python + Streamlit + SQLite + Gemini stack.

---

## 1. Goals

1. **Safe querying**: Execute only read-only SQL (`SELECT` and validated `WITH ... SELECT`).
2. **Predictable results**: Return at most **100 rows** per query by enforcing/capping `LIMIT`.
3. **Explicit execution**: Run Gemini + SQL execution **only after user submission**.
4. **Reliable first run**: Initialize the SQLite database only when missing/required.
5. **Non-destructive initialization**: Create tables safely and seed sample data only when the table is empty; never overwrite existing data.
6. **Schema-aware prompting**: Use the actual schema to reduce invalid SQL generation.

## 2. Non-goals

- Supporting write operations (`INSERT`, `UPDATE`, `DELETE`) or schema changes.
- Multi-database support (Postgres/MySQL/etc.).
- Authentication/authorization or multi-tenant access.
- Adding a **database reset button**.
- Production-grade audit logging (beyond basic debug logs).

---

## 3. Primary user journeys

### 3.1 Journey A — First run, database missing
1. User opens app.
2. App detects `data.db` is missing.
3. UI shows a clear message: “Database not found” with an **Initialize database** button.
4. User clicks Initialize.
5. App creates the DB (if missing), creates required tables (if not exist), and seeds sample rows only if the table is empty.
6. UI confirms success and reveals schema.

**Success outcome:** user can run queries without leaving the UI.

### 3.2 Journey B — Ask a question and get results safely
1. User navigates to “Intelligent Query Assistance”.
2. User types a natural-language question.
3. User clicks **Get Answer**.
4. App builds schema-aware prompt and calls Gemini.
5. App displays generated SQL (collapsed/expandable).
6. App validates SQL:
   - If blocked: show reason and do not execute.
   - If allowed: enforce `LIMIT <= 100` and execute.
7. UI shows results (≤100 rows).

### 3.3 Journey C — Blocked unsafe query
1. User asks something that triggers unsafe SQL (or attempts prompt injection).
2. Gemini returns non-SELECT or multi-statement SQL.
3. Safety gate blocks execution.
4. UI shows:
   - “Query blocked”
   - reason (e.g., “Only SELECT queries are allowed”)
   - generated SQL for transparency
   - guidance: “Rephrase your question as a read-only request.”

---

## 4. Major components

### 4.1 Streamlit UI
- Collects input and manages user actions.
- Calls Gemini only on submit.
- Shows schema, generated SQL, results, and validation errors.

### 4.2 DB Manager (proposed helper)
- Detects DB existence.
- Initializes schema when required.
- Seeds sample data only when table empty.
- Provides schema introspection.

### 4.3 Prompt Builder (proposed helper)
- Builds prompt using live schema.
- Adds policy constraints to reduce unsafe outputs.

### 4.4 SQL Safety Gate (proposed helper)
- Validates query is single-statement and read-only.
- Rejects any write/schema/admin tokens.
- Enforces/caps `LIMIT` to 100.

### 4.5 Query Executor
- Executes sanitized SQL with SQLite.
- Returns structured results.

---

## 5. High-level data flow and interfaces

### 5.1 Data flow

1. **UI submit** → (optional) DB check/init → schema fetch
2. **Prompt Builder**(schema, question) → prompt
3. **Gemini**(prompt, question) → SQL text
4. **SQL Safety Gate**(sql text) → allow/block + sanitized SQL
5. **Query Executor**(sanitized SQL) → rows (≤100)
6. UI renders output

### 5.2 Interface contracts (high-level)

- `DBManager.db_exists(db_path) -> bool`
- `DBManager.initialize_if_needed(db_path) -> InitResult(status, message)`
- `DBManager.get_schema(db_path) -> SchemaInfo(tables=[...])`
- `PromptBuilder.build_prompt(schema_info) -> str`
- `SQLSafetyGate.validate_and_sanitize(sql_text) -> GateResult(allowed, reason, sanitized_sql, limit_applied)`
- `QueryExecutor.run(db_path, sanitized_sql) -> QueryResult(columns, rows, row_count)`

---

## 6. Error handling

### 6.1 Categories
- **Configuration errors**: missing `GOOGLE_API_KEY`.
- **DB errors**: missing file, locked DB, schema init failures.
- **Model errors**: request failures, empty response.
- **Validation errors**: blocked SQL, multi-statement, forbidden tokens.
- **Execution errors**: SQL syntax error, table/column not found.

### 6.2 User-visible behavior
- Always show a clear message with next steps.
- When blocked, show the generated SQL and the block reason.
- When execution fails, show:
  - human-friendly message
  - underlying SQLite error (sanitized)
  - schema panel to help rephrase

---

## 7. Security

- **Read-only enforcement** via allowlist.
- **Statement count enforcement** (single statement only).
- **Max rows enforcement** to reduce accidental heavy queries.
- **No secret exposure**: never print API keys.
- **Prompt hardening**: include policy constraints in the prompt, but rely on server-side validation.

---

## 8. Acceptance criteria (HLD)

1. **First-run success**: With no `data.db`, a user can initialize the DB from the UI and then successfully execute a query.
2. **Explicit submit**: Gemini is called only after clicking Get Answer.
3. **Read-only**: Any non-SELECT or multi-statement SQL is blocked, and the DB is not modified.
4. **Row cap**: Results never exceed 100 rows; if query lacks a limit, one is added; if it exceeds 100, it is capped.
5. **Schema-aware**: The prompt uses the actual SQLite schema; UI exposes schema for user reference.
6. **No reset**: UI contains no “reset database” option.
