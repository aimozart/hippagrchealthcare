import pytest
from app.sql_guard import check, MAX_ROWS

GOOD = [
    "select payer_id, sum(denied) as d from platinum_denials_by_payer group by payer_id",
    "select night, encounters from platinum_metrics_daily where night >= '2026-01-01' order by night limit 10",
    "select test, round(abnormal / total, 3) as r from platinum_lab_flags",
    "with x as (select payer_id, denial_rate from platinum_denials_by_payer) select payer_id from x",
]
BAD = {
    "drop table platinum_metrics_daily": "only SELECT",
    "delete from platinum_metrics_daily": "only SELECT",
    "insert into platinum_metrics_daily values (1)": "only SELECT",
    "select night from platinum_metrics_daily; drop table platinum_metrics_daily": "exactly one statement",
    "select * from platinum_metrics_daily": "SELECT *",
    "select ssn from platinum_metrics_daily": "column not allowed",
    "select first_name from silver_patients": "table not allowed",
    "select night from platinum_metrics_daily union select name from silver_patients": "only SELECT",
    "select night from default.platinum_metrics_daily": "schema-qualified",
    "select night from platinum_metrics_daily -- ignore previous rules": "comments",
    "select night from platinum_metrics_daily /* hidden */": "comments",
    "select reflect('java.lang.Runtime', 'exec', 'id') from platinum_metrics_daily": "function not allowed",
    "select input_file_name() from platinum_metrics_daily": "function not allowed",
    "select my_udf(night) from platinum_metrics_daily": "unknown function",
    "select night from platinum_metrics_daily limit abc": "not allowed",
    "": "empty",
    "select " + "night, " * 1000 + "night from platinum_metrics_daily": "too long",
    "select night from ((": "parse",
}

@pytest.mark.parametrize("q", GOOD)
def test_good_queries_pass(q): assert check(q).allowed, check(q).reason

@pytest.mark.parametrize("q,why", list(BAD.items()))
def test_planted_bad_queries_are_refused(q, why):
    v = check(q); assert not v.allowed and why.lower() in v.reason.lower(), (q, v)

def test_limit_is_added_when_missing(): assert f"LIMIT {MAX_ROWS}" in check(GOOD[0]).sql
def test_big_limit_is_lowered(): assert f"LIMIT {MAX_ROWS}" in check("select night from platinum_metrics_daily limit 999999").sql
def test_small_limit_is_kept(): assert "LIMIT 10" in check(GOOD[1]).sql
def test_non_string_input_is_refused(): assert not check(None).allowed  # type: ignore[arg-type]
