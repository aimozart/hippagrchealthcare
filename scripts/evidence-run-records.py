#!/usr/bin/env python3
"""Turn the pipeline's nightly run records into audit evidence (one silver-layer pipeline_run event per night).

Reads site-data/run_record.jsonl (see docs/site-data-contract.md). For each night not yet recorded it emits:
  total = rowsIn, passed = valid, flagged = quarantined,
  decision allow / reason check_passed when valid + quarantined == rowsIn, otherwise deny / check_failed.
Already-recorded nights are remembered in <EVIDENCE_DIR>/emitted-nights.txt, so running it twice is harmless.
The Scala pipeline is not touched: this only reads the file it writes. Counts only; no data leaves the file.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "scripts" / "evidence.sh"
DIR = Path(os.environ.get("EVIDENCE_DIR", Path.home() / ".local/share/hippagrchealthcare-evidence"))


def main(path: Path) -> int:
    if not path.exists():
        print(f"no run records at {path}")
        return 0
    DIR.mkdir(parents=True, exist_ok=True)
    seen_file = DIR / "emitted-nights.txt"
    seen = set(seen_file.read_text().split()) if seen_file.exists() else set()
    emitted = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        night = str(r["night"])
        if night in seen:
            continue
        rows_in, valid, quarantined = int(r["rowsIn"]), int(r["valid"]), int(r["quarantined"])
        ok = valid + quarantined == rows_in
        p = subprocess.run([str(EVIDENCE), "emit", "evidence.pipeline_run", "silver", "allow" if ok else "deny",
                            "check_passed" if ok else "check_failed", "hipaa_164_312_c1",
                            str(rows_in), str(valid), str(quarantined),
                            f"night={night} layer=silver valid+quarantined=input:{ok}", f"run-{night}-silver"])
        if p.returncode == 0:
            seen.add(night)
            emitted += 1
    seen_file.write_text("\n".join(sorted(seen)) + ("\n" if seen else ""))
    print(f"emitted {emitted} new night(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site-data" / "run_record.jsonl"))
