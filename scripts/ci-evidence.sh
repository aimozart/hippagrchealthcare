#!/usr/bin/env bash
# Post one audit-evidence receipt from CI to the Entropa evidence node (a signed, hash-only event). Counts and ids only.
#   ID_TOKEN=... EVIDENCE_URL=https://... scripts/ci-evidence.sh KIND LABEL DECISION REASON CONTROL TOTAL PASSED FLAGGED "DETAIL" RUN_ID
# Best effort: a failure here is reported but never fails the build.
set -uo pipefail
[ $# -eq 10 ] || { echo "usage: ci-evidence.sh KIND LABEL DECISION REASON CONTROL TOTAL PASSED FLAGGED DETAIL RUN_ID"; exit 0; }
[ -n "${EVIDENCE_URL:-}" ] && [ -n "${ID_TOKEN:-}" ] || { echo "evidence: not configured, skipped"; exit 0; }
body=$(jq -n --arg kind "$1" --arg label "$2" --arg decision "$3" --arg reason "$4" --arg control "$5" \
  --argjson total "$6" --argjson passed "$7" --argjson flagged "$8" --arg detail "$9" --arg run_id "${10}" \
  '{kind:$kind,label:$label,decision:$decision,reason:$reason,control:$control,total:$total,passed:$passed,flagged:$flagged,detail:$detail,run_id:$run_id}')
if curl -sf -X POST "${EVIDENCE_URL%/}/v1/evidence" -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" -d "$body" >/dev/null; then
  echo "evidence: recorded $2 ($3)"
else
  echo "evidence: the node did not accept the receipt (continuing)"
fi
exit 0
