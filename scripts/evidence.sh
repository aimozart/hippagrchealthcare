#!/usr/bin/env bash
# Emit one piece of audit evidence (a signed, hash-only event) to the Scryon Health Data evidence ledger.
#   scripts/evidence.sh init
#   scripts/evidence.sh emit KIND LABEL DECISION REASON CONTROL TOTAL PASSED FLAGGED "DETAIL" RUN_ID
# Where it goes:  EVIDENCE_URL set  -> POST to that node (EVIDENCE_TOKEN adds a bearer token)
#                 otherwise         -> the local node in EVIDENCE_DIR (default ~/.local/share/hippagrchealthcare-evidence)
# Best effort by default (a missing node never breaks your build). EVIDENCE_REQUIRED=1 makes a failure fatal.
# The detail text is hashed by the node and dropped: put counts and ids there, never data.
set -uo pipefail
DIR=${EVIDENCE_DIR:-$HOME/.local/share/hippagrchealthcare-evidence}
required=${EVIDENCE_REQUIRED:-0}

fail() { echo "evidence: $1" >&2; [ "$required" = 1 ] && exit 1; exit 0; }

cmd=${1:-}
case "$cmd" in
  init)
    command -v entropa-platinum >/dev/null || fail "entropa-platinum is not installed"
    [ -f "$DIR/platinum.key" ] && { echo "evidence node already initialised in $DIR"; exit 0; }
    entropa-platinum init "$DIR" && echo "evidence node initialised in $DIR"
    ;;
  emit)
    [ $# -eq 11 ] || fail "usage: emit KIND LABEL DECISION REASON CONTROL TOTAL PASSED FLAGGED DETAIL RUN_ID"
    body=$(jq -n --arg kind "$2" --arg label "$3" --arg decision "$4" --arg reason "$5" --arg control "$6" \
      --argjson total "$7" --argjson passed "$8" --argjson flagged "$9" --arg detail "${10}" --arg run_id "${11}" \
      '{kind:$kind,label:$label,decision:$decision,reason:$reason,control:$control,total:$total,passed:$passed,flagged:$flagged,detail:$detail,run_id:$run_id}') \
      || fail "could not build the request"
    if [ -n "${EVIDENCE_URL:-}" ]; then
      curl -sf -X POST "${EVIDENCE_URL%/}/v1/evidence" ${EVIDENCE_TOKEN:+-H "Authorization: Bearer $EVIDENCE_TOKEN"} \
        -H "Content-Type: application/json" -d "$body" >/dev/null || fail "the evidence node did not accept the event"
    else
      command -v entropa-platinum >/dev/null || fail "entropa-platinum is not installed"
      [ -f "$DIR/platinum.key" ] || fail "no local evidence node (run: scripts/evidence.sh init)"
      printf '%s' "$body" | entropa-platinum log-evidence "$DIR" >/dev/null || fail "the node refused the event"
    fi
    ;;
  verify)
    entropa-platinum verify-evidence "$DIR"
    ;;
  *) echo "usage: evidence.sh init | emit ... | verify" >&2; exit 2 ;;
esac
