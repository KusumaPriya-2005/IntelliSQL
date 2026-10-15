# Wireframes (text) — IntelliSQL Approved Enhancements

**Status:** Proposal for human review. These are text-based wireframes describing the intended UI changes for the approved enhancements.

---

## 1. Query page (Intelligent Query Assistance)

### Layout

```
+-----------------------------------------------------------------------------------+
| IntelliSQL                                                                        |
| [Sidebar]  Home | About | Intelligent Query Assistance                             |
+-----------------------------------------------------------------------------------+
| Intelligent Query Assistance                                                       |
|-----------------------------------------------------------------------------------|
| Description text (brief)                                                          |
|                                                                                   |
| [DB Status Banner]                                                                |
|   - If DB OK:   ✅ Database ready: data.db                                        |
|   - If missing: ⚠️ Database not found. Initialize to continue. [Initialize DB]   |
|                                                                                   |
| [Schema Panel - Collapsible]                                                      |
|   v Database schema                                                               |
|     Table: Students                                                               |
|       - name (TEXT)                                                               |
|       - class (TEXT)                                                              |
|       - marks (INTEGER)                                                           |
|       - company (TEXT)                                                            |
|                                                                                   |
| Ask a question (natural language):                                                |
| [ text input ................................................................. ] |
|                                                                                   |
| [Get Answer]                                                                      |
|                                                                                   |
| [Generated SQL - Collapsible]                                                     |
|   v Generated SQL                                                                 |
|     SELECT ...                                                                    |
|                                                                                   |
| [Validation Messages Area]                                                        |
|   - warnings/errors appear here                                                   |
|                                                                                   |
| Results (max 100 rows)                                                            |
| +-------------------------------------------------------------------------------+ |
| | table output                                                                  | |
| +-------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

### Interactions / validation messages

- User types question → **no execution** yet.
- User clicks **Get Answer**:
  - If `GOOGLE_API_KEY` missing:
    - Show error: “Missing GOOGLE_API_KEY. Set it in your environment or .env file.”
  - If DB missing:
    - Show warning banner and block query execution until user initializes.
  - Otherwise:
    1. Build prompt using live schema.
    2. Call Gemini.
    3. Show generated SQL (collapsed by default).
    4. Validate SQL safety.
    5. If allowed, execute and show results.

---

## 2. Blocked unsafe query state

### Layout

```
+-----------------------------------------------------------------------------------+
| Intelligent Query Assistance                                                       |
|-----------------------------------------------------------------------------------|
| Ask a question:                                                                   |
| [ "Delete all students" ..................................................... ] |
| [Get Answer]                                                                      |
|                                                                                   |
| ⚠️ Query blocked                                                                   |
| Reason: Only single-statement, read-only SELECT queries are allowed.              |
|                                                                                   |
| [Generated SQL - Collapsible]                                                     |
|   v Generated SQL                                                                 |
|     DELETE FROM Students;                                                         |
|                                                                                   |
| What you can try:                                                                 |
|  - Rephrase as a read-only question, e.g., "Show all students"                    |
|  - Ask for filters/aggregations instead of changes                                |
+-----------------------------------------------------------------------------------+
```

### Validation rules reflected in UI
- Multi-statement blocked: “Multiple SQL statements are not allowed.”
- Forbidden operations blocked: “Only SELECT queries are allowed.”
- Missing/invalid SQL blocked: “The model did not generate a valid SQL query.”

---

## 3. Missing-database initialization flow

### State A — DB missing banner

```
[DB Status Banner]
⚠️ Database not found (data.db).
This app needs a local SQLite database to answer queries.
[Initialize database]
```

### State B — Initialization in progress

```
⏳ Initializing database...
- Creating tables (if missing)
- Seeding sample data (only if table empty)
```

### State C — Initialization success

```
✅ Database initialized.
- Tables ready
- Sample data inserted (only if needed)

[Schema Panel expands automatically]
```

### State D — Initialization error

```
❌ Database initialization failed.
Details: <sqlite error>
Next steps:
- Check file permissions
- Ensure the directory is writable
- Retry initialization
```

---

## 4. Notes

- No database reset button is included (explicit non-goal).
- Results area should include a small note: “Showing up to 100 rows.”
- Generated SQL is always visible (expander) for transparency and learning.
