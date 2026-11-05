"""Platinum AI decisions are recorded as signed, data-minimal ledger events (entropa-platinum CLI).
Synthetic data only. Skipped when the entropa-platinum binary is not installed."""
import shutil
import subprocess
import pytest
from app import decision_log
from app.sql_guard import check

pytestmark = pytest.mark.skipif(shutil.which("entropa-platinum") is None, reason="entropa-platinum not installed")

SQL = "SELECT payer_id, denial_rate FROM platinum_denials_by_payer LIMIT 10"
QUESTION = "Which payers deny the most claims?"


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    d = tmp_path / "ledger"
    subprocess.run(["entropa-platinum", "init", str(d)], check=True)
    monkeypatch.setenv("ENTROPA_PLATINUM_DIR", str(d))
    return d


def verify(d):
    return subprocess.run(["entropa-platinum", "verify", str(d)], capture_output=True, text=True)


def test_an_allowed_query_is_recorded_and_verifies(ledger):
    v = decision_log.guarded_query(QUESTION, SQL, run_id="run-test-1")
    assert v.allowed
    assert "OK records=1" in verify(ledger).stdout


def test_a_refused_query_is_recorded_too(ledger):
    v = decision_log.guarded_query(QUESTION, "DROP TABLE platinum_quality", run_id="run-test-1")
    assert not v.allowed
    assert "OK records=1" in verify(ledger).stdout


def test_the_verdict_is_the_same_with_or_without_logging(ledger, monkeypatch):
    with_log = decision_log.guarded_query(QUESTION, SQL, run_id="run-test-1")
    monkeypatch.delenv("ENTROPA_PLATINUM_DIR")
    without = decision_log.guarded_query(QUESTION, SQL, run_id="run-test-1")
    assert with_log == without == check(SQL)


def test_no_ledger_configured_means_no_logging_and_no_error(monkeypatch):
    monkeypatch.delenv("ENTROPA_PLATINUM_DIR", raising=False)
    assert decision_log.guarded_query(QUESTION, SQL, run_id="run-test-1").allowed


def test_a_broken_ledger_never_changes_or_blocks_the_verdict_but_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTROPA_PLATINUM_DIR", str(tmp_path / "missing"))
    v = decision_log.guarded_query(QUESTION, SQL, run_id="run-test-1")
    assert v.allowed
    assert decision_log.last_error() is not None


def test_required_mode_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTROPA_PLATINUM_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("ENTROPA_PLATINUM_REQUIRED", "1")
    v = decision_log.guarded_query(QUESTION, SQL, run_id="run-test-1")
    assert not v.allowed and "audit" in v.reason


def test_identifier_shaped_text_is_never_logged(ledger):
    q = f"patient {'123'}-{'45'}-{'6789'} denials?"
    decision_log.guarded_query(q, SQL, run_id="run-test-1")
    assert "OK records=0" in verify(ledger).stdout
    assert decision_log.last_error() is not None


def test_an_ml_score_is_recorded_without_the_features(ledger):
    ok = decision_log.log_score("readmission-risk", features_text="age_band=65-74;los=4", score_text="0.31", run_id="run-test-2")
    assert ok
    assert "OK records=1" in verify(ledger).stdout
    # the raw feature text never reaches the ledger files
    for f in ledger.rglob("*"):
        if f.is_file() and f.name != "platinum.key":
            assert "age_band" not in f.read_text(errors="ignore")


def test_a_rag_answer_is_recorded_with_its_precedent_count(ledger):
    ok = decision_log.log_rag("What drives denials?", "Denials concentrate in two payers.", run_id="run-test-3", cited=2)
    assert ok
    assert "OK records=1" in verify(ledger).stdout


def test_an_answer_with_no_citations_is_held_not_allowed(ledger):
    # a RAG answer without any cited source is not 'allow': it is held for review
    assert decision_log.log_rag("Q?", "A.", run_id="run-test-4", cited=0)
    assert "OK records=1" in verify(ledger).stdout
    assert decision_log.last_decision() == ("hold", "needs_review")


def test_logging_off_returns_true_for_scores_and_answers(monkeypatch):
    monkeypatch.delenv("ENTROPA_PLATINUM_DIR", raising=False)
    assert decision_log.log_score("m", features_text="x", score_text="1", run_id="run-test-5")
    assert decision_log.log_rag("q", "a", run_id="run-test-5", cited=1)


import socket
import time
import urllib.request


@pytest.fixture()
def server(tmp_path, monkeypatch):
    """A real entropa-platinum serve process on a free port (the same service that runs in the cloud)."""
    d = tmp_path / "node"
    subprocess.run(["entropa-platinum", "init", str(d)], check=True)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen(["entropa-platinum", "serve", str(d)], env={**__import__("os").environ, "PORT": str(port), "BIND": "127.0.0.1"})
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1).read(); break
        except Exception:
            time.sleep(0.05)
    monkeypatch.delenv("ENTROPA_PLATINUM_DIR", raising=False)
    monkeypatch.setenv("ENTROPA_PLATINUM_URL", f"http://127.0.0.1:{port}")
    yield port
    proc.kill(); proc.wait()


def server_verify(port):
    return urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/verify", timeout=5).read().decode()


def test_http_mode_records_to_the_service(server):
    assert decision_log.guarded_query(QUESTION, SQL, run_id="run-http-1").allowed
    assert "OK records=1" in server_verify(server)


def test_http_mode_failure_is_reported_and_required_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("ENTROPA_PLATINUM_URL", "http://127.0.0.1:9")
    assert decision_log.guarded_query(QUESTION, SQL, run_id="run-http-2").allowed
    assert decision_log.last_error() is not None
    monkeypatch.setenv("ENTROPA_PLATINUM_REQUIRED", "1")
    assert not decision_log.guarded_query(QUESTION, SQL, run_id="run-http-2").allowed
