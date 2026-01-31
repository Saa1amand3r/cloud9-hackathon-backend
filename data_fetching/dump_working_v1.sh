#!/usr/bin/env bash
set -euo pipefail

: "${GRID_API_KEY:?set GRID_API_KEY first}"

PYTHON=${PYTHON:-python3}

TITLE_ID="3"                 # LoL title id
GTE="2023-01-01T00:00:00Z"
LTE="2026-01-28T23:59:59Z"
PAGE_SIZE=50
RETRIES=5

OUT_TOURNAMENTS="tournaments.jsonl"
OUT_SERIES="series.jsonl"
OUT_SERIESSTATE="series_state.jsonl"

CENTRAL_URL="https://api-op.grid.gg/central-data/graphql"
STATE_URL="https://api-op.grid.gg/live-data-feed/series-state/graphql"

export TITLE_ID GTE LTE PAGE_SIZE

: > "$OUT_TOURNAMENTS"
: > "$OUT_SERIES"
: > "$OUT_SERIESSTATE"

post_json() {
  local url="$1"
  local payload="$2"
  local attempt=1
  local resp=""
  local code=0

  while true; do
    resp="$(curl -s "$url" \
      -H "x-api-key: $GRID_API_KEY" \
      -H "content-type: application/json" \
      -d "$payload" || true)"

    # Validate response:
    # - Must be JSON
    # - If it has GraphQL errors and no data -> fail fast (no retries)
    # - Otherwise accept if it has "data" key
    if printf '%s' "$resp" | "$PYTHON" -c '
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(1)

if isinstance(d,dict) and d.get("errors") and not d.get("data"):
    sys.exit(2)

sys.exit(0 if (isinstance(d,dict) and "data" in d) else 1)
'; then
      printf '%s' "$resp"
      return 0
    else
      code=$?
      if [[ $code -eq 2 ]]; then
        echo "GraphQL error (won't retry): $resp" >&2
        return 1
      fi
    fi

    if (( attempt >= RETRIES )); then
      echo "Request failed after $RETRIES attempts" >&2
      echo "$resp" >&2
      return 1
    fi

    sleep "$attempt"
    attempt=$((attempt+1))
  done
}


echo "=== Fetch tournaments ==="
after="null"
while true; do
  payload="$(
    AFTER="$after" "$PYTHON" - <<'PY'
import json,os
after_raw = os.environ.get("AFTER", "null")
try:
    after_val = None if after_raw in ("", "null", "None", None) else json.loads(after_raw)
except Exception:
    after_val = None

payload = {
  "query": (
    "query T($first:Int!,$after:Cursor,$titleIds:[ID!]!){"
    "tournaments(filter:{title:{id:{in:$titleIds}}},first:$first,after:$after){"
    "pageInfo{endCursor hasNextPage} edges{node{id name}}}}"
  ),
  "variables": {
    "first": int(os.environ["PAGE_SIZE"]),
    "after": after_val,
    "titleIds": [os.environ["TITLE_ID"]],
  },
}
print(json.dumps(payload))
PY
  )"

  resp="$(post_json "$CENTRAL_URL" "$payload")"
  printf '%s' "$resp" | "$PYTHON" -c $'import json,sys\ntry:\n    d=json.load(sys.stdin)\nexcept Exception:\n    sys.exit(0)\nedges=((d.get(\"data\") or {}).get(\"tournaments\") or {}).get(\"edges\", [])\nfor e in edges:\n    print(json.dumps((e.get(\"node\") or {})))' >> "$OUT_TOURNAMENTS"

  has_next="$(
    printf '%s' "$resp" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
info=((d.get("data") or {}).get("tournaments") or {}).get("pageInfo") or {}
print(str(info.get("hasNextPage")).lower())
'
  )"
  [[ "$has_next" == "true" ]] || break

  end_cursor="$(
    printf '%s' "$resp" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
info=((d.get("data") or {}).get("tournaments") or {}).get("pageInfo") or {}
print(json.dumps(info.get("endCursor")))
'
  )"
  after="$end_cursor"
done

echo "Collected tournaments -> $OUT_TOURNAMENTS"

tournament_ids="$("$PYTHON" - <<'PY'
import json
from pathlib import Path

ids=[]
p=Path("tournaments.jsonl")
if p.exists():
    for line in p.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line:
            continue
        try:
            ids.append((json.loads(line) or {}).get("id"))
        except Exception:
            pass
ids=[i for i in ids if i]
print(json.dumps(ids))
PY
)"

echo "=== Fetch allSeries ==="
export TIDS="$tournament_ids"
after="null"
while true; do
  payload="$(
    AFTER="$after" "$PYTHON" - <<'PY'
import json,os
after_raw = os.environ.get("AFTER", "null")
try:
    after_val = None if after_raw in ("", "null", "None", None) else json.loads(after_raw)
except Exception:
    after_val = None

payload = {
  "query": (
    "query S($tids:[ID!]!,$gte:String!,$lte:String!,$first:Int!,$after:Cursor){"
    "allSeries(filter:{tournament:{id:{in:$tids},includeChildren:{equals:true}},"
    "startTimeScheduled:{gte:$gte,lte:$lte}},orderBy:StartTimeScheduled,"
    "first:$first,after:$after){pageInfo{endCursor hasNextPage} edges{node{"
    "id startTimeScheduled tournament{id name} teams{baseInfo{id name}}}}}}"
  ),
  "variables": {
    "tids": json.loads(os.environ["TIDS"]),
    "gte": os.environ["GTE"],
    "lte": os.environ["LTE"],
    "first": int(os.environ["PAGE_SIZE"]),
    "after": after_val,
  },
}
print(json.dumps(payload))
PY
  )"

  resp="$(post_json "$CENTRAL_URL" "$payload")"

  printf '%s' "$resp" | "$PYTHON" -c $'import json,sys\ntry:\n    d=json.load(sys.stdin)\nexcept Exception:\n    sys.exit(0)\nedges=((d.get(\"data\") or {}).get(\"allSeries\") or {}).get(\"edges\", [])\nfor e in edges:\n    print(json.dumps((e.get(\"node\") or {})))' >> "$OUT_SERIES"

  has_next="$(
    printf '%s' "$resp" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
info=((d.get("data") or {}).get("allSeries") or {}).get("pageInfo") or {}
print(str(info.get("hasNextPage")).lower())
'
  )"
  [[ "$has_next" == "true" ]] || break

  end_cursor="$(
    printf '%s' "$resp" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
info=((d.get("data") or {}).get("allSeries") or {}).get("pageInfo") or {}
print(json.dumps(info.get("endCursor")))
'
  )"
  after="$end_cursor"
done

echo "Collected series -> $OUT_SERIES"

echo "=== Fetch seriesState for each series ==="
GRID_API_KEY="$GRID_API_KEY" STATE_URL="$STATE_URL" "$PYTHON" - <<'PY'
import json
import os
import pathlib
import subprocess
import time

state_url = os.environ["STATE_URL"]
api_key = os.environ["GRID_API_KEY"]
out_path = "series_state.jsonl"

p = pathlib.Path("series.jsonl")
series = []
if p.exists():
    for l in p.read_text(encoding="utf-8").splitlines():
        l=l.strip()
        if not l:
            continue
        try:
            series.append((json.loads(l) or {}).get("id"))
        except Exception:
            pass
series = [s for s in series if s]

for sid in series:
    payload = {
        "query": (
            "query SS($id:ID!){"
            "seriesState(id:$id){"
            "valid finished startedAt "
            "teams{id name won score kills deaths} "
            "games{sequenceNumber teams{id won score kills deaths "
            "players{id name kills deaths character{ id name }}}}"
            "}}}"
        ),
        "variables": {"id": sid},
    }
    cmd = [
        "curl","-s",
        state_url,
        "-H", f"x-api-key: {api_key}",
        "-H", "content-type: application/json",
        "-d", json.dumps(payload),
    ]
    resp = subprocess.check_output(cmd).decode("utf-8", errors="replace")
    try:
        data = json.loads(resp)
    except Exception:
        continue

    rec = {
        "series_id": sid,
        "seriesState": (data.get("data") or {}).get("seriesState"),
        "errors": data.get("errors"),
    }
    with open(out_path, "a", encoding="utf-8") as out:
        out.write(json.dumps(rec) + "\n")
    time.sleep(0.1)
PY

echo "Done."
echo "Outputs:"
echo "  $OUT_TOURNAMENTS"
echo "  $OUT_SERIES"
echo "  $OUT_SERIESSTATE"
