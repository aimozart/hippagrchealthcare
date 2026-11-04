"""FastAPI app: serves the dashboard and a small data API. The same data files feed Streamlit and the RAG tools.
Data comes from site/data.js (written by tools/export_site_data.py); no database, no row-level data, synthetic only."""
import json, re, pathlib
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
app = FastAPI(title="hippagrchealthcare", description="Synthetic-data pipeline dashboard and build log API", version="0.1.0")

def load_data() -> dict:
    f = SITE / "data.js"
    if not f.exists():
        return {"commits": {}, "notes": [], "docs": [], "metrics": [], "runs": [], "recent": [], "synthetic_only": True}
    text = f.read_text()
    return json.loads(re.sub(r"^window\.SITE_DATA\s*=\s*|;\s*$", "", text.strip()))

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "synthetic_only": True}

@app.get("/api/summary")
def summary() -> dict:
    d = load_data()
    return {"updated": d.get("updated"), "working_days": len(d["commits"]), "commits": sum(d["commits"].values()),
            "notes": len(d["notes"]), "runs": len(d["runs"]), "synthetic_only": True}

@app.get("/api/runs")
def runs() -> list:
    return load_data()["runs"]

@app.get("/api/notes")
def notes() -> list:
    return load_data()["notes"]

@app.get("/api/search")
def search(q: str = Query(min_length=2, max_length=200), limit: int = Query(6, ge=1, le=20)) -> list:
    """Lexical search over the build log (documents and notes). The RAG layer will call the same function."""
    words = [w for w in re.split(r"\s+", q.lower()) if w]
    hits = []
    for doc in load_data()["docs"]:
        text = (doc["title"] + " " + doc["text"]).lower()
        score = sum(text.count(w) + (5 if w in doc["title"].lower() else 0) for w in words)
        if score:
            hits.append({"score": score, "path": doc["path"], "title": doc["title"], "snippet": doc["text"][:240]})
    return sorted(hits, key=lambda h: -h["score"])[:limit]

app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
