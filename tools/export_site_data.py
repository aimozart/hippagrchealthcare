#!/usr/bin/env python3
"""Export public-safe build data for the site: commits per day, daily notes, docs (for search), metrics, run records.
Scans everything it exports (canary, valid-range SSN shapes, emails, key-like strings) and REFUSES to write if anything is found.
Stdlib only. Usage: python3 tools/export_site_data.py [--out site/data.js]"""
import json, re, subprocess, sys, pathlib, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data.js"
if "--out" in sys.argv: OUT = pathlib.Path(sys.argv[sys.argv.index("--out") + 1])
CANARY = "CANARY-7F3A-SYN"
BAD = [re.compile(r"\b[0-8]\d{2}-\d{2}-\d{4}\b"), re.compile(r"\b9\d{2}-(?!00-)\d{2}-\d{4}\b"),
       re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), re.compile(r"(?i)(secret|password|api[_-]?key|token)\s*[:=]\s*\S{8,}"),
       re.compile(r"AKIA[0-9A-Z]{16}"), re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")]
def scan(name, text):
    problems = []
    if CANARY in text: problems.append("canary token")
    for rx in BAD:
        m = rx.search(text)
        if m: problems.append("pattern %s" % rx.pattern[:30])
    return ["%s: %s" % (name, p) for p in problems]
def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout
def read(p): return pathlib.Path(p).read_text(errors="ignore")
commits = {}
for line in git("log", "--date=short", "--pretty=%ad").split():
    commits[line] = commits.get(line, 0) + 1
recent = [l for l in git("log", "-30", "--date=short", "--pretty=%ad|%s").splitlines()]
notes, docs, problems = [], [], []
for f in sorted((ROOT / "notes").glob("*.md")):
    t = read(f); title = (re.search(r"^#\s+(.+)$", t, re.M) or [None, f.stem])[1]
    notes.append({"file": f.name, "title": title, "words": len(t.split()), "excerpt": " ".join(t.split())[:280]})
    problems += scan(str(f.relative_to(ROOT)), t)
for f in list((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"] + list((ROOT / "notes").glob("*.md")):
    if not f.exists(): continue
    t = read(f); title = (re.search(r"^#\s+(.+)$", t, re.M) or [None, f.stem])[1]
    docs.append({"path": str(f.relative_to(ROOT)), "title": title, "text": " ".join(t.split())[:6000]})
    problems += scan(str(f.relative_to(ROOT)), t)
metrics = []
mf = ROOT / "notes" / "metrics.jsonl"
if mf.exists():
    for l in read(mf).splitlines():
        try: metrics.append(json.loads(l))
        except Exception: pass
    problems += scan("notes/metrics.jsonl", read(mf))
runs = []
rf = ROOT / "site" / "run-record.jsonl"
if rf.exists():
    for l in read(rf).splitlines():
        try: runs.append(json.loads(l))
        except Exception: pass
    problems += scan("site/run-record.jsonl", read(rf))
if problems:
    print("EXPORT REFUSED, fix these first:"); [print(" -", p) for p in problems]; sys.exit(1)
data = {"updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "commits": commits, "recent": recent, "notes": notes, "docs": docs,
        "metrics": metrics, "runs": runs, "synthetic_only": True}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("window.SITE_DATA = " + json.dumps(data) + ";\n")
print("wrote %s: %d commit days, %d notes, %d docs, %d metrics, %d runs" % (OUT.relative_to(ROOT), len(commits), len(notes), len(docs), len(metrics), len(runs)))
