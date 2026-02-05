#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${CWL_TEST_WORK_DIR:-$ROOT_DIR/tests/work/cwl}"
EDGE_DIR="${WORK_DIR}/edges"
CHAIN_DIR="${WORK_DIR}/chains"

CHAIN_LENGTH=""
MAX_CHAINS=0
RERUN_PASSED=0
ALLOW_REPEATS=0

usage() {
  cat <<EOF
Usage: $(basename "$0") --chain-length N [--max-chains N] [--rerun-passed] [--allow-repeats]
EOF
}

for arg in "$@"; do
  case "$arg" in
    --chain-length=*)
      CHAIN_LENGTH="${arg#*=}"
      ;;
    --max-chains=*)
      MAX_CHAINS="${arg#*=}"
      ;;
    --rerun-passed)
      RERUN_PASSED=1
      ;;
    --allow-repeats)
      ALLOW_REPEATS=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CHAIN_LENGTH" ]]; then
  echo "--chain-length is required" >&2
  usage
  exit 1
fi

if [[ ! -f "${EDGE_DIR}/edges.json" ]]; then
  "${ROOT_DIR}/utils/verify_cwl_edges.sh"
fi

mkdir -p "$CHAIN_DIR"

CHAIN_ARGS=(
  --edges-json "${EDGE_DIR}/edges.json"
  --out-dir "${CHAIN_DIR}"
  --chain-length "${CHAIN_LENGTH}"
)

CHAIN_COUNT="$(python3 - <<'PY'\nimport json\nimport sys\nedges_path = \"${EDGE_DIR}/edges.json\"\nlength = int(\"${CHAIN_LENGTH}\")\nallow_repeats = \"${ALLOW_REPEATS}\" == \"1\"\nwith open(edges_path, \"r\", encoding=\"utf-8\") as f:\n    data = json.load(f)\n\nadj = {}\nfor edge in data.get(\"edges\", []):\n    if edge.get(\"status\") != \"PASS\":\n        continue\n    adj.setdefault(edge[\"source\"], []).append(edge)\n\nchains = []\n\ndef dfs(path, tools):\n    if len(tools) == length:\n        chains.append(path.copy())\n        return\n    last_tool = tools[-1]\n    for edge in adj.get(last_tool, []):\n        next_tool = edge[\"target\"]\n        if not allow_repeats and next_tool in tools:\n            continue\n        path.append(edge)\n        tools.append(next_tool)\n        dfs(path, tools)\n        tools.pop()\n        path.pop()\n\nfor start in sorted(adj.keys()):\n    dfs([], [start])\n\nmax_chains = int(\"${MAX_CHAINS}\")\ncount = len(chains)\nif max_chains:\n    count = min(count, max_chains)\nprint(count)\nPY\n)"
printf "Chain run count: %s\\n" "${CHAIN_COUNT}"

if [[ "$MAX_CHAINS" -gt 0 ]]; then
  CHAIN_ARGS+=(--max-chains "$MAX_CHAINS")
fi
if [[ "$RERUN_PASSED" -eq 1 ]]; then
  CHAIN_ARGS+=(--rerun-passed)
fi
if [[ "$ALLOW_REPEATS" -eq 1 ]]; then
  CHAIN_ARGS+=(--allow-repeats)
fi

python3 "${ROOT_DIR}/utils/lib/cwl_chains.py" "${CHAIN_ARGS[@]}"

printf "Chain summary written to %s\n" "${CHAIN_DIR}/summary.tsv"
