#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${FSL_TEST_WORK_DIR:-$ROOT_DIR/tests/work/fsl}"
JOB_DIR="${WORK_DIR}/jobs"
EDGE_DIR="${WORK_DIR}/edges"
CWL_DIR="${ROOT_DIR}/public/cwl/fsl"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd cwltool
require_cmd python3

"${ROOT_DIR}/utils/verify_fsl_tools.sh" --jobs-only

mkdir -p "$EDGE_DIR"

python3 "${ROOT_DIR}/utils/lib/cwl_edges.py" \
  --cwl-dir "$CWL_DIR" \
  --job-dir "$JOB_DIR" \
  --out-tsv "${EDGE_DIR}/edges.tsv" \
  --out-json "${EDGE_DIR}/edges.json"

printf "Edge matrix written to %s\n" "${EDGE_DIR}/edges.tsv"
