from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

def test_health(): assert c.get("/api/health").json() == {"status": "ok", "synthetic_only": True}
def test_summary_is_synthetic(): assert c.get("/api/summary").json()["synthetic_only"] is True
def test_search_finds_readme():
    hits = c.get("/api/search", params={"q": "synthetic"}).json()
    assert hits and all("path" in h for h in hits)
def test_search_rejects_short_query(): assert c.get("/api/search", params={"q": "a"}).status_code == 422
def test_index_served(): assert "hippagrchealthcare" in c.get("/").text
