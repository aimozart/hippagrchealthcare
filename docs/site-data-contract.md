# Site data contract

The pipeline (Scala/Spark, run on the author's machine) writes small, aggregate, de-identified JSON files into `site-data/`. `tools/export_site_data.py` validates them, scans them, and bundles them into `site/data.js`; the site draws charts from that. Nothing row-level ever goes here.

| File | Shape | Notes |
|---|---|---|
| `run_record.jsonl` | one JSON object per night: `night` (YYYY-MM-DD), `rowsIn`, `valid`, `quarantined` (integers), `byReason` (object of integers), `prev_hash`, `hash` | hash chain: `hash = sha256(prev_hash + canonical_json(record without hash))`, first `prev_hash` is 64 zeros |
| `quarantine_by_reason.json` | array of `{entity, reason, count}` | entity in patients, encounters, labs, claims |
| `denial_by_payer.json` | array of `{payer, month, lines, denied}` | the site computes the rate |
| `encounters_per_day.json` | array of `{day, type, count}` | type in inpatient, outpatient, ED |
| `lab_flags.json` | array of `{test, abnormal, total}` | |

Rules: values are integers or short strings (60 characters at most); counts from 1 to 10 are replaced by `null` (small-cell suppression, as in real reporting); each file is at most 1 MB; synthetic data only; the export refuses files that contain the canary token, identifier shapes, emails or key-like strings.
