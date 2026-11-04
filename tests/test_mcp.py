import asyncio
from mcp_server import pipeline_ops as p

def test_status_synthetic(): assert p.project_status()["synthetic_only"] is True
def test_search_validates_limits():
    try: p.search_build_log("x"); assert False
    except ValueError: pass
def test_chain_ok_without_records(): assert p.verify_run_chain()["ok"] is True
def test_safety_scan_runs(): assert "files_scanned" in p.safety_scan()
def test_tools_registered():
    tools = asyncio.run(p.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"project_status", "search_build_log", "recent_runs", "verify_run_chain", "safety_scan", "publication_gate"} <= names
