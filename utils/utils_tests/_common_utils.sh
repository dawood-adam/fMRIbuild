#!/usr/bin/env bash
# Shared helpers for utils_tests (sourced after structural_mri_tests/_common.sh)

# Generate a QWarp warp field for testing, reusing cached results if available.
# Sets QWARP_WARP to the path of the generated warp HEAD file.
generate_qwarp_warp() {
  local prefix="${DERIVED_DIR}/qwarp_test"
  QWARP_WARP=""

  # Check for existing warp in either +orig or +tlrc space
  for suffix in +orig +tlrc; do
    if [[ -f "${prefix}_WARP${suffix}.HEAD" ]]; then
      QWARP_WARP="${prefix}_WARP${suffix}.HEAD"
      break
    fi
  done
  [[ -n "$QWARP_WARP" ]] && return 0

  echo "Generating identity warp field for testing..."

  # Create a smoothed copy so 3dQwarp has different source/base
  local smooth="${DERIVED_DIR}/qwarp_src_smooth"
  if [[ ! -f "${smooth}+orig.HEAD" && ! -f "${smooth}+tlrc.HEAD" ]]; then
    docker_afni 3dmerge -doall -1blur_fwhm 4 -prefix "$smooth" "$T1W_2MM" 2>/dev/null || true
  fi
  local smooth_file=""
  for suffix in +orig +tlrc; do
    [[ -f "${smooth}${suffix}.HEAD" ]] && smooth_file="${smooth}${suffix}.HEAD" && break
  done
  if [[ -n "$smooth_file" ]]; then
    docker_afni 3dQwarp \
      -base "$T1W_2MM" -source "$smooth_file" \
      -prefix "$prefix" \
      -minpatch 25 -maxlev 1 -iwarp \
      -workhard:0:0 2>/dev/null || true
  fi

  # Check if QWarp succeeded
  for suffix in +orig +tlrc; do
    if [[ -f "${prefix}_WARP${suffix}.HEAD" ]]; then
      QWARP_WARP="${prefix}_WARP${suffix}.HEAD"
      return 0
    fi
  done

  # Fallback: build 3-sub-brick zero displacement field via 3dTcat
  local zero_vol="${DERIVED_DIR}/qwarp_zero_vol"
  if [[ ! -f "${zero_vol}+orig.HEAD" && ! -f "${zero_vol}+tlrc.HEAD" ]]; then
    docker_afni 3dcalc -a "$T1W_2MM" -expr '0' -prefix "$zero_vol" 2>/dev/null || true
  fi
  local zero_file=""
  for suffix in +orig +tlrc; do
    [[ -f "${zero_vol}${suffix}.HEAD" ]] && zero_file="${zero_vol}${suffix}.HEAD" && break
  done
  if [[ -n "$zero_file" ]]; then
    docker_afni 3dTcat -prefix "${prefix}_WARP" \
      "$zero_file" "$zero_file" "$zero_file" 2>/dev/null || true
  fi

  # Find the generated warp
  for suffix in +orig +tlrc; do
    if [[ -f "${prefix}_WARP${suffix}.HEAD" ]]; then
      QWARP_WARP="${prefix}_WARP${suffix}.HEAD"
      break
    fi
  done
}
