"""SQL Safety Gate: validates LLM-generated SQL and enforces the row cap."""
import re
from dataclasses import dataclass
from typing import Optional

MAX_ROWS = 100

FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX", "ANALYZE",
    "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE",
    "LOAD_EXTENSION",
}

MSG_EMPTY = "The model did not generate a valid SQL query."
MSG_MULTI = "Multiple SQL statements are not allowed."
MSG_READ_ONLY = "Only SELECT queries are allowed."
MSG_LIMIT = "Could not safely determine the LIMIT of this query; use a numeric LIMIT."

_TOKEN_RE = re.compile(
    r"""
    (?P<line_comment>--[^\n]*)
  | (?P<block_comment>/\*.*?(?:\*/|\Z))
  | (?P<string>'(?:[^']|'')*(?:'|\Z))
  | (?P<quoted>"(?:[^"]|"")*(?:"|\Z)|`[^`]*(?:`|\Z)|\[[^\]]*(?:\]|\Z))
  | (?P<word>[A-Za-z_][A-Za-z0-9_$]*)
  | (?P<number>\d+(?:\.\d*)?|\.\d+)
  | (?P<space>\s+)
  | (?P<punct>.)
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class GateResult:
    allowed: bool
    reason: Optional[str] = None
    sanitized_sql: Optional[str] = None
    limit_applied: bool = False


def strip_markdown_fences(text: str) -> str:
    text = text.replace("```sql", "").replace("```SQL", "").replace("```", "")
    return text.strip()


def _tokenize(sql: str):
    """Return [(kind, text)] with comments replaced by a single space."""
    tokens = []
    for m in _TOKEN_RE.finditer(sql):
        kind = m.lastgroup
        if kind in ("line_comment", "block_comment"):
            tokens.append(("space", " "))
        else:
            tokens.append((kind, m.group()))
    return tokens


def _collapse(tokens):
    """Collapse whitespace runs and trim."""
    out = []
    for kind, text in tokens:
        if kind == "space":
            if out and out[-1][0] != "space":
                out.append(("space", " "))
        else:
            out.append((kind, text))
    while out and out[-1][0] == "space":
        out.pop()
    return out


def _split_statements(tokens):
    """Strip trailing semicolons. Return (tokens, multiple); multiple is True
    if a semicolon (outside strings/comments) remains inside the statement."""
    toks = list(tokens)
    while toks and (toks[-1][0] == "space" or toks[-1] == ("punct", ";")):
        toks.pop()
    multiple = any(t == ("punct", ";") for t in toks)
    return _collapse(toks), multiple


def _render(tokens) -> str:
    return "".join(t for _, t in tokens).strip()


def enforce_limit(sql: str, max_rows: int = MAX_ROWS):
    """Return (sql, limit_applied) with a top-level LIMIT <= max_rows.

    Supports `LIMIT n`, `LIMIT n OFFSET m` and `LIMIT m, n` (rewritten to
    `LIMIT n OFFSET m`). Raises ValueError if the limit is not a plain integer.
    Input must already be comment-free, single-statement SQL.
    """
    tokens = _collapse(_tokenize(sql))
    original = _render(tokens)
    depth = 0
    limit_idx = None
    for i, (kind, text) in enumerate(tokens):
        if kind == "punct" and text == "(":
            depth += 1
        elif kind == "punct" and text == ")":
            depth -= 1
        elif kind == "word" and depth == 0 and text.upper() == "LIMIT":
            limit_idx = i  # last top-level LIMIT is the outer one
    if limit_idx is None:
        return f"{original} LIMIT {max_rows}", True

    rest = [t for t in tokens[limit_idx + 1:] if t[0] != "space"]
    texts = [t[1] for t in rest]
    kinds = [t[0] for t in rest]

    def num(i):
        return kinds[i] == "number" and texts[i].isdigit()

    if len(rest) == 1 and num(0):
        n, offset = int(texts[0]), None
    elif len(rest) == 3 and num(0) and kinds[1] == "word" and texts[1].upper() == "OFFSET" and num(2):
        n, offset = int(texts[0]), int(texts[2])
    elif len(rest) == 3 and num(0) and texts[1] == "," and num(2):
        n, offset = int(texts[2]), int(texts[0])
    else:
        raise ValueError(MSG_LIMIT)
    new_sql = f"{_render(tokens[:limit_idx])} LIMIT {min(n, max_rows)}"
    if offset is not None:
        new_sql += f" OFFSET {offset}"
    return new_sql, new_sql != original


def validate_and_sanitize(sql_text: str) -> GateResult:
    if not sql_text or not sql_text.strip():
        return GateResult(False, MSG_EMPTY)
    tokens = _tokenize(strip_markdown_fences(sql_text))
    tokens, multiple = _split_statements(_collapse(tokens))
    if not tokens:
        return GateResult(False, MSG_EMPTY)
    if multiple:
        return GateResult(False, MSG_MULTI)

    words = [(i, t.upper()) for i, (k, t) in enumerate(tokens) if k == "word"]
    if tokens[0][0] != "word" or words[0][1] not in ("SELECT", "WITH"):
        return GateResult(False, MSG_READ_ONLY)

    for i, w in words:
        if w not in FORBIDDEN_KEYWORDS:
            continue
        if w == "REPLACE":  # allow the replace() string function, not REPLACE INTO
            nxt = [t for t in tokens[i + 1:] if t[0] != "space"][:1]
            if nxt and nxt[0] == ("punct", "("):
                continue
        return GateResult(False, MSG_READ_ONLY)

    if words[0][1] == "WITH":
        depth, has_select = 0, False
        for kind, text in tokens:
            if kind == "punct" and text == "(":
                depth += 1
            elif kind == "punct" and text == ")":
                depth -= 1
            elif kind == "word" and depth == 0 and text.upper() == "SELECT":
                has_select = True
        if not has_select:
            return GateResult(False, MSG_READ_ONLY)

    try:
        sanitized, applied = enforce_limit(_render(tokens), MAX_ROWS)
    except ValueError as e:
        return GateResult(False, str(e))
    return GateResult(True, None, sanitized, applied)
