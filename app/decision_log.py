"""Record platinum-layer AI decisions in the Entropa ledger (signed, data-minimal).
The question and SQL are hashed by the entropa-platinum CLI and never stored. Configure with
ENTROPA_PLATINUM_DIR (ledger directory; unset = logging off). Set ENTROPA_PLATINUM_REQUIRED=1 to refuse a
query whenever it cannot be logged (fail closed). Synthetic data only."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from .sql_guard import Verdict, check, refuse

_last_error: str | None = None
_last_decision: tuple[str, str] | None = None

def last_error() -> str | None:
    return _last_error

def last_decision() -> tuple[str, str] | None:
    """The (decision, reason) codes of the most recent event this process tried to log."""
    return _last_decision

def _log(label: str, decision: str, reason: str, text_in: str, text_out: str, run_id: str,
         provider: str, model_id: str, in_tokens: int, out_tokens: int, cost_micro_usd: int) -> bool:
    """Append one event; returns True on success. On failure records a short error and returns False."""
    global _last_error, _last_decision
    _last_error = None
    _last_decision = (decision, reason)
    url = os.environ.get("ENTROPA_PLATINUM_URL")
    d = os.environ.get("ENTROPA_PLATINUM_DIR")
    if not url and not d:
        return True
    if url:
        return _log_http(url, label, decision, reason, text_in, text_out, run_id, provider, model_id,
                         in_tokens, out_tokens, cost_micro_usd)
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

def _log_http(url: str, label: str, decision: str, reason: str, text_in: str, text_out: str, run_id: str,
              provider: str, model_id: str, in_tokens: int, out_tokens: int, cost_micro_usd: int) -> bool:
    """POST the request to a running ingest (the cloud service or a local one). The caller's identity token,
    if the service is private, comes from ENTROPA_PLATINUM_TOKEN (never logged)."""
    global _last_error
    req = {"label": label, "decision": decision, "reason": reason, "input": text_in, "output": text_out,
           "run_id": run_id, "provider": provider, "model_id": model_id,
           "input_tokens": in_tokens, "output_tokens": out_tokens, "cost_micro_usd": cost_micro_usd}
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("ENTROPA_PLATINUM_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request(url.rstrip("/") + "/v1/decision", data=json.dumps(req).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        _last_error = f"ingest refused the request (HTTP {e.code})"
    except (urllib.error.URLError, OSError, TimeoutError):
        _last_error = "ingest unreachable"
    return False

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


def log_score(model_name: str, features_text: str, score_text: str, run_id: str, provider: str = "sparkml",
              in_tokens: int = 0, out_tokens: int = 0) -> bool:
    """Record an ML score. The feature text and the score are hashed by the node and dropped."""
    return _log("ml_score", "info", "within_limits", f"{model_name}|{features_text}", score_text, run_id,
                provider, model_name[:60] or "model", in_tokens, out_tokens, 0)

def log_rag(question: str, answer: str, run_id: str, cited: int, provider: str = "vertex",
            model_id: str = "gemini-3.8-flash", in_tokens: int = 0, out_tokens: int = 0,
            cost_micro_usd: int = 0) -> bool:
    """Record a retrieval-augmented answer. An answer that cites no source is held for review, not allowed."""
    decision, reason = ("allow", "cited_receipts") if cited > 0 else ("hold", "needs_review")
    return _log("rag_answer", decision, reason, question, answer, run_id, provider, model_id,
                in_tokens, out_tokens, cost_micro_usd)
