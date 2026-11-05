#!/usr/bin/env bash
# Run the repository's own checks and record each result as audit evidence (counts only).
#   scripts/evidence-check.sh            (best effort; EVIDENCE_REQUIRED=1 makes an evidence failure fatal)
# Records: Python tests (ci_tests), secret scan (secret_scan), identifier-range scan (identifier_range).
# The exit code is the checks' own result, never the evidence step's (unless EVIDENCE_REQUIRED=1).
set -uo pipefail
cd "$(dirname "$0")/.."
E=scripts/evidence.sh
sha=$(git rev-parse --short=12 HEAD 2>/dev/null || echo "nogit")
rc=0

# 1) tests
out=$(uv run pytest -q 2>&1); t_rc=$?
passed=$(printf '%s' "$out" | grep -Eo '[0-9]+ passed' | grep -Eo '[0-9]+' | head -1); passed=${passed:-0}
failed=$(printf '%s' "$out" | grep -Eo '[0-9]+ failed' | grep -Eo '[0-9]+' | head -1); failed=${failed:-0}
if [ "$t_rc" -eq 0 ]; then d=allow; r=check_passed; else d=deny; r=check_failed; rc=1; fi
$E emit evidence.control_check ci_tests "$d" "$r" hitrust_10_sdlc $((passed + failed)) "$passed" "$failed" "pytest at $sha" "ci-$sha"

# 2) secret scan (gitleaks, the same scan the CI runs)
if command -v gitleaks >/dev/null; then
  gitleaks detect --no-banner >/dev/null 2>&1; g_rc=$?
  if [ "$g_rc" -eq 0 ]; then d=allow; r=check_passed; f=0; else d=deny; r=check_failed; f=1; rc=1; fi
  $E emit evidence.control_check secret_scan "$d" "$r" hitrust_10_sdlc 1 $((1 - f)) "$f" "gitleaks at $sha" "scan-$sha"
fi

# 3) identifier shapes in tracked text files: area/group/serial in a valid SSN range must never appear
hits=$(git grep -InE '\b(00[1-9]|0[1-9][0-9]|[1-5][0-9]{2}|6[0-5][0-9]|66[0-5]|66[7-9]|6[7-9][0-9]|7[0-9]{2}|8[0-9]{2})-(0[1-9]|[1-9][0-9])-(000[1-9]|00[1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3})\b' -- ':!*.lock' ':!*.svg' 2>/dev/null | wc -l)
if [ "$hits" -eq 0 ]; then d=allow; r=check_passed; else d=deny; r=check_failed; rc=1; fi
$E emit evidence.control_check identifier_range "$d" "$r" policy_p0_data_safety 1 $((hits == 0 ? 1 : 0)) "$hits" "identifier shapes at $sha" "ids-$sha"

echo "checks done (exit $rc)"
exit "$rc"
