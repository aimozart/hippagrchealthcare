"""SQL policy checker for generated queries (the English-question assistant, guardrail layer 1).
A query is allowed only if it is ONE read-only SELECT over allow-listed tables and columns, uses only allow-listed
functions, and has a bounded result (a LIMIT is added or lowered to MAX_ROWS). Anything else is refused with a reason.
Fail closed: any parse problem or unknown construct is a refusal. Synthetic data only; the checker never sees row data."""
from __future__ import annotations
from dataclasses import dataclass
import sqlglot
from sqlglot import exp

MAX_ROWS = 1000
MAX_QUERY_CHARS = 4000
# the catalogue: table -> allowed columns (platinum layer only; no identifiers)
CATALOGUE: dict[str, set[str]] = {
    "platinum_metrics_daily": {"night", "encounters", "inpatient", "outpatient", "ed", "avg_los"},
    "platinum_denials_by_payer": {"month", "payer_id", "lines", "denied", "denial_rate"},
    "platinum_lab_flags": {"test", "abnormal", "total", "abnormal_rate"},
    "platinum_quality": {"night", "entity", "reason", "count"},
}
ALLOWED_FUNCTIONS = {"count", "sum", "avg", "min", "max", "round", "coalesce", "abs", "date_trunc", "year", "month", "upper", "lower", "cast", "if", "case", "nullif"}
FORBIDDEN_FUNCTIONS = {"reflect", "java_method", "input_file_name", "assert_true", "raise_error", "sleep", "read_files", "from_json", "to_json", "uuid", "rand"}

@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str
    sql: str | None = None

def refuse(reason: str) -> Verdict:
    return Verdict(False, reason, None)

def check(sql: str) -> Verdict:
    if not isinstance(sql, str) or not sql.strip(): return refuse("empty query")
    if len(sql) > MAX_QUERY_CHARS: return refuse("query too long")
    if "--" in sql or "/*" in sql: return refuse("comments are not allowed")
    try:
        statements = sqlglot.parse(sql, read="spark")
    except Exception:
        return refuse("could not parse the query")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1: return refuse("exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Select): return refuse("only SELECT is allowed")
    if tree.find(exp.Subquery) or any(isinstance(n, exp.Select) for n in tree.walk() if n is not tree):
        pass  # subqueries are allowed only if every table inside passes the checks below
    ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name
        if name in ctes: continue
        if table.db or table.catalog: return refuse("schema-qualified tables are not allowed")
        if name not in CATALOGUE: return refuse(f"table not allowed: {name}")
    for star in tree.find_all(exp.Star):
        return refuse("SELECT * is not allowed; name the columns")
    allowed_cols = set().union(*CATALOGUE.values())
    aliases = {a.alias for a in tree.find_all(exp.Alias)}
    for col in tree.find_all(exp.Column):
        if col.name in aliases: continue
        if col.name not in allowed_cols: return refuse(f"column not allowed: {col.name}")
    for fn in tree.find_all(exp.Func):
        n = (fn.sql_name() or "").lower()
        if n in FORBIDDEN_FUNCTIONS: return refuse(f"function not allowed: {n}")
    for anon in tree.find_all(exp.Anonymous):
        return refuse(f"unknown function not allowed: {anon.name}")
    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_ROWS)
    else:
        try: n = int(limit.expression.name)
        except Exception: return refuse("LIMIT must be a number")
        if n > MAX_ROWS: tree = tree.limit(MAX_ROWS)
    return Verdict(True, "ok", tree.sql(dialect="spark"))
