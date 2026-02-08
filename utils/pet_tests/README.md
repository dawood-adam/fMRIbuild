# PET Tool CWL Tests

CWL verification tests for PET imaging tools. Currently covers `mri_gtmpvc` (FreeSurfer).

## Prerequisites

- **cwltool**: `pip install cwltool`
- **docker**: Running with ability to pull `freesurfer/freesurfer:7.4.1`
- **python3**: For output verification
- **FreeSurfer license**: Set `FS_LICENSE` env var to your `license.txt` path, or place it at `tests/data/freesurfer/license.txt`
- **Test data**: The `bert` FreeSurfer subject — auto-downloaded on first run via `utils/download_freesurfer_test_data.sh`

## Running

```bash
# From the repo root
bash utils/pet_tests/test_mri_gtmpvc.sh

# Re-run previously passed tests
bash utils/pet_tests/test_mri_gtmpvc.sh --rerun-passed
```

## What it tests

`test_mri_gtmpvc.sh` runs 5 parameter sets against a synthetic PET image (created from `bert/mri/brain.mgz` at 2 mm isotropic to keep memory manageable):

| Set | Description | Key flags |
|-----|-------------|-----------|
| A | Minimal, PSF=4 | `--psf 4 --regheader --no-rescale --default-seg-merge --ctab-default` |
| B | Higher PSF | `--psf 6 --regheader --no-rescale --default-seg-merge --ctab-default` |
| C | Even higher PSF | `--psf 8 --regheader --no-rescale --default-seg-merge --ctab-default` |
| D | Lower PSF | `--psf 3 --regheader --no-rescale --default-seg-merge --ctab-default` |
| E | No reduce FOV | `--psf 4 --regheader --no-reduce-fov --no-rescale --default-seg-merge --ctab-default` |

All sets use `--no-rescale` because the synthetic data lacks the Pons (id 174) reference region needed for rescaling, and `--ctab-default --default-seg-merge` for tissue type handling with `aseg.mgz`.

Each set validates:
1. CWL file passes `cwltool --validate`
2. Tool executes successfully via cwltool + Docker
3. Expected output files exist (output directory, gtm.stats.dat, logs)

## Output structure

```
pet_tests/
├── jobs/           # Generated job YAML files (gitignored)
├── out/            # Tool output directories (gitignored)
├── logs/           # Execution logs (gitignored)
├── data/           # Downloaded/copied test data (gitignored)
├── derived/        # Synthetic PET image (gitignored)
└── summary.tsv     # PASS/FAIL results table (gitignored)
```

## Shared infrastructure

Test scripts source `utils/structural_mri_tests/_common.sh` which provides:
- Docker helpers (`docker_fs`, `copy_from_fs_image`)
- FreeSurfer data preparation (`prepare_freesurfer_data`)
- CWL template generation (`make_template`)
- Tool execution and output verification (`run_tool`, `verify_outputs`)
