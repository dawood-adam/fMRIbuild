#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${CWL_TEST_WORK_DIR:-$ROOT_DIR/tests/work/cwl}"
EDGE_DIR="${WORK_DIR}/edges"
SPEC_FILE="${EDGE_DIR}/spec.json"
RUN_EDGES=1
RUN_TOOLS=0

for arg in "$@"; do
  case "$arg" in
    --run-tools)
      RUN_TOOLS=1
      ;;
    --skip-run)
      RUN_EDGES=0
      ;;
    --help|-h)
      echo "Usage: $(basename "$0") [--run-tools] [--skip-run]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd cwltool
require_cmd python3

LIB_NAMES=()
CWL_DIRS=()
JOB_DIRS=()

for dir in "${ROOT_DIR}/public/cwl"/*; do
  [[ -d "$dir" ]] || continue
  lib="$(basename "$dir")"
  verify_script="${ROOT_DIR}/utils/verify_${lib}_tools.sh"
  if [[ -x "$verify_script" ]]; then
    if [[ "$RUN_TOOLS" -eq 1 ]]; then
      "$verify_script"
    else
      "$verify_script" --jobs-only
    fi
    LIB_NAMES+=("$lib")
    CWL_DIRS+=("$dir")
    JOB_DIRS+=("${ROOT_DIR}/tests/work/${lib}/jobs")
  else
    echo "WARN: missing verify script for ${lib} (skipping)" >&2
  fi
done

mkdir -p "$EDGE_DIR"

LIB_NAMES_STR="$(printf '%s\n' "${LIB_NAMES[@]}")"
CWL_DIRS_STR="$(printf '%s\n' "${CWL_DIRS[@]}")"
JOB_DIRS_STR="$(printf '%s\n' "${JOB_DIRS[@]}")"

LIB_NAMES_STR="$LIB_NAMES_STR" CWL_DIRS_STR="$CWL_DIRS_STR" JOB_DIRS_STR="$JOB_DIRS_STR" SPEC_FILE="$SPEC_FILE" \
python3 - <<'PY'
import json
import os

names = [n for n in os.environ.get("LIB_NAMES_STR", "").splitlines() if n]
cs = [c for c in os.environ.get("CWL_DIRS_STR", "").splitlines() if c]
js = [j for j in os.environ.get("JOB_DIRS_STR", "").splitlines() if j]
if not names:
    raise SystemExit("No libraries found to build spec.")
if not (len(names) == len(cs) == len(js)):
    raise SystemExit("Spec list lengths do not match.")

spec = {"libraries": []}
for name, cwl_dir, job_dir in zip(names, cs, js):
    spec["libraries"].append({"name": name, "cwl_dir": cwl_dir, "job_dir": job_dir})

spec_path = os.environ.get("SPEC_FILE")
if not spec_path:
    raise SystemExit("SPEC_FILE env var missing.")
with open(spec_path, "w", encoding="utf-8") as handle:
    json.dump(spec, handle, indent=2)
PY

python3 "${ROOT_DIR}/utils/lib/cwl_edges.py" \
  --spec "${SPEC_FILE}" \
  --out-tsv "${EDGE_DIR}/edges.tsv" \
  --out-json "${EDGE_DIR}/edges.json"

printf "Edge matrix written to %s\n" "${EDGE_DIR}/edges.tsv"
EDGE_COUNT="$(python3 - <<'PY'\nimport json\nwith open(\"${EDGE_DIR}/edges.json\", \"r\", encoding=\"utf-8\") as f:\n    data = json.load(f)\nedges = data.get(\"edges\", [])\npass_edges = [e for e in edges if e.get(\"status\") == \"PASS\"]\nprint(f\"{len(pass_edges)}/{len(edges)}\")\nPY\n)"
printf "Runtime edge run count (PASS/total): %s\\n" "${EDGE_COUNT}"

if [[ "$RUN_EDGES" -eq 1 ]]; then
  python3 "${ROOT_DIR}/utils/lib/cwl_edges_run.py" \
    --edges-json "${EDGE_DIR}/edges.json" \
    --out-dir "${EDGE_DIR}/runs"
  printf "Runtime edge results written to %s\n" "${EDGE_DIR}/runs/edges_runtime.tsv"
  printf "Validated edge matrix written to %s\n" "${EDGE_DIR}/runs/edges_validated.tsv"
fi
