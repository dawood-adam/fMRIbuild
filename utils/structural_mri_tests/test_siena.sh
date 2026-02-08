#!/usr/bin/env bash
# Test: FSL siena (Longitudinal Brain Atrophy Estimation)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

TOOL="siena"
LIB="fsl"
CWL="${CWL_DIR}/${LIB}/${TOOL}.cwl"

prepare_fsl_data

# Siena needs two timepoint T1 images. Use the 2mm MNI152 as both
# timepoints (will yield ~0% change). The 1mm images cause OOM.
SIENA_T1A="$T1W_2MM"
SIENA_T1B="$T1W_2MM"

# Generate template for reference
make_template "$CWL" "$TOOL"

# Create job YAML
cat > "${JOB_DIR}/${TOOL}.yml" <<EOF
input1:
  class: File
  path: "${SIENA_T1A}"
input2:
  class: File
  path: "${SIENA_T1B}"
output_dir: "siena_out"
EOF

run_tool "$TOOL" "${JOB_DIR}/${TOOL}.yml" "$CWL"
