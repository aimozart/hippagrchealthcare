"""pipeline-ops MCP server (stdio). READ-ONLY tools for controlling and inspecting the project workflow.
Allowlisted, no shell, no network, no writes. Every tool returns small, data-minimal results (no row data).
Run: uv run python -m mcp_server.pipeline_ops"""
import json, re, subprocess, pathlib
from mcp.server.mcpserver import MCPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
mcp = MCPServer("pipeline-ops")
CANARY = "CANARY-7F3A-SYN"
SSN_VALID = re.compile(r"\b[0-8]\d{2}-\d{2}-\d{4}\b|\b9\d{2}-(?!00-)\d{2}-\d{4}\b")

def _load_site() -> dict:
    f = ROOT / "site" / "data.js"
    if not f.exists():
        return {"commits": {}, "notes": [], "docs": [], "metrics": [], "runs": []}
    return json.loads(re.sub(r"^window\.SITE_DATA\s*=\s*|;\s*$", "", f.read_text().strip()))

@mcp.tool()
def project_status() -> dict:
    """Summary of the build: working days, commits, notes, last test result, pipeline runs (synthetic data only)."""
    d = _load_site()
    last = d["metrics"][-1] if d["metrics"] else None
    return {"working_days": len(d["commits"]), "commits": sum(d["commits"].values()), "notes": len(d["notes"]),
            "runs": len(d["runs"]), "last_tests": last, "synthetic_only": True}

@mcp.tool()
def search_build_log(query: str, limit: int = 5) -> list:
    """Lexical search over documents and notes in the build log. Returns title, path and a short snippet."""
    if not 2 <= len(query) <= 200 or not 1 <= limit <= 10:
        raise ValueError("query must be 2-200 chars and limit 1-10")
    words = [w for w in query.lower().split() if w]
    out = []
    for doc in _load_site()["docs"]:
        t = (doc["title"] + " " + doc["text"]).lower()
        s = sum(t.count(w) + (5 if w in doc["title"].lower() else 0) for w in words)
        if s: out.append({"score": s, "path": doc["path"], "title": doc["title"], "snippet": doc["text"][:200]})
    return sorted(out, key=lambda h: -h["score"])[:limit]

@mcp.tool()
def recent_runs(count: int = 5) -> list:
    """The latest pipeline run records (counts and hashes only)."""
    if not 1 <= count <= 30: raise ValueError("count must be 1-30")
    return _load_site()["runs"][-count:]

@mcp.tool()
def verify_run_chain() -> dict:
    """Recompute the hash chain of site/run-record.jsonl (each record's prev_hash must equal the previous record's hash)."""
    import hashlib
    f = ROOT / "site" / "run-record.jsonl"
    if not f.exists(): return {"ok": True, "records": 0, "note": "no run records yet"}
    prev = "0" * 64; n = 0
    for line in f.read_text().splitlines():
        rec = json.loads(line); n += 1
        body = {k: v for k, v in rec.items() if k != "hash"}
        if rec.get("prev_hash") != prev: return {"ok": False, "records": n, "broken_at": n}
        h = hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest()
        if h != rec.get("hash"): return {"ok": False, "records": n, "broken_at": n}
        prev = h
    return {"ok": True, "records": n}

@mcp.tool()
def safety_scan() -> dict:
    """Scan tracked text files for the canary token, valid-range SSN shapes and secret-like strings. Reports file names only."""
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout.split()
    hits = []
    for rel in files:
        p = ROOT / rel
        if not p.is_file() or p.stat().st_size > 2_000_000: continue
        try: t = p.read_text()
        except Exception: continue
        if rel.startswith("mcp_server/") or rel.startswith("tools/") or rel.startswith("tests/") or rel.startswith("scripts/git-hooks/"): continue
        if CANARY in t: hits.append({"file": rel, "kind": "canary"})
        if SSN_VALID.search(t): hits.append({"file": rel, "kind": "ssn-shape-valid-range"})
        if re.search(r"(?i)(secret|password|api[_-]?key)\s*[:=]\s*\S{12,}", t): hits.append({"file": rel, "kind": "secret-like"})
    return {"ok": not hits, "files_scanned": len(files), "findings": hits}

@mcp.tool()
def publication_gate() -> dict:
    """Checklist for publishing: clean working tree, safety scan, tests exist, README present. Does not publish anything."""
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    scan = safety_scan()
    return {"clean_tree": not dirty, "safety_scan_ok": scan["ok"], "has_readme": (ROOT / "README.md").exists(),
            "has_license": (ROOT / "LICENSE").exists(), "ready": (not dirty) and scan["ok"]}

if __name__ == "__main__":
    mcp.run()
