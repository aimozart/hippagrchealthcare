"""Record platinum-layer AI decisions in the Entropa ledger (signed, data-minimal).
The question and SQL are hashed by the entropa-platinum CLI and never stored. Configure with
ENTROPA_PLATINUM_DIR (ledger directory; unset = logging off). Set ENTROPA_PLATINUM_REQUIRED=1 to refuse a
query whenever it cannot be logged (fail closed). Synthetic data only."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
from .sql_guard import Verdict, check, refuse

_last_error: str | None = None

def last_error() -> str | None:
    return _last_error

def _log(label: str, decision: str, reason: str, text_in: str, text_out: str, run_id: str,
         provider: str, model_id: str, in_tokens: int, out_tokens: int, cost_micro_usd: int) -> bool:
    """Append one event; returns True on success. On failure records a short error and returns False."""
    global _last_error
    _last_error = None
    d = os.environ.get("ENTROPA_PLATINUM_DIR")
    if not d:
        return True
    exe = shutil.which("entropa-platinum")
    if exe is None:
        _last_error = "entropa-platinum is not installed"
        return False
    req = {"label": label, "decision": decision, "reason": reason, "input": text_in, "output": text_out,
           "run_id": run_id, "provider": provider, "model_id": model_id,
           "input_tokens": in_tokens, "output_tokens": out_tokens, "cost_micro_usd": cost_micro_usd}
    try:
        p = subprocess.run([exe, "log", d], input=json.dumps(req), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        _last_error = "could not run entropa-platinum"
        return False
    if p.returncode != 0:
        _last_error = (p.stderr.strip() or "entropa-platinum failed")[:200]
        return False
    return True

def guarded_query(question: str, sql: str, run_id: str, provider: str = "vertex",
                  model_id: str = "gemini-3.8-flash", in_tokens: int = 0, out_tokens: int = 0,
                  cost_micro_usd: int = 0) -> Verdict:
    """Check generated SQL with the guard, then record the decision. The verdict is the guard's own;
    a logging failure never changes it, except in required mode where the query is refused."""
    v = check(sql)
    ok = _log("nl_query", "allow" if v.allowed else "deny", "guard_passed" if v.allowed else "guard_refused",
              question, sql, run_id, provider, model_id, in_tokens, out_tokens, cost_micro_usd)
    if not ok and os.environ.get("ENTROPA_PLATINUM_REQUIRED") == "1":
        return refuse("audit log unavailable")
    return v
