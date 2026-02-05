#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${FSL_TEST_WORK_DIR:-$ROOT_DIR/tests/work/fsl}"
JOB_DIR="${WORK_DIR}/jobs"
EDGE_DIR="${WORK_DIR}/edges"
CHAIN_DIR="${WORK_DIR}/chains"
CWL_DIR="${ROOT_DIR}/public/cwl/fsl"

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

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd cwltool
require_cmd python3

"${ROOT_DIR}/utils/verify_fsl_tools.sh" --jobs-only

if [[ ! -f "${EDGE_DIR}/edges.json" ]]; then
  "${ROOT_DIR}/utils/verify_fsl_edges.sh"
fi

mkdir -p "$CHAIN_DIR"

CHAIN_ARGS=(
  --edges-json "${EDGE_DIR}/edges.json"
  --cwl-dir "${CWL_DIR}"
  --job-dir "${JOB_DIR}"
  --out-dir "${CHAIN_DIR}"
  --chain-length "${CHAIN_LENGTH}"
)

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
