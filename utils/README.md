# CWL Tool Testing Utilities

This directory contains shell scripts for testing the CWL tool definitions in `public/cwl/`. The test harness downloads real neuroimaging data, runs each tool through `cwltool`, and validates outputs.

## Goals

- **Verify CWL correctness**: Ensure all tool definitions execute without errors
- **Validate outputs**: Confirm expected output files are produced
- **Test tool chains**: Verify tools work together (e.g., bet → fast → flirt → fnirt)
- **Reproducibility**: Use public datasets for consistent, reproducible testing

## Prerequisites

### Required Tools

```bash
# Check if you have the required tools
cwltool --version    # CWL runner
docker --version     # Container runtime
python3 --version    # For output validation
aws --version        # For downloading test data (optional)
```

### Installation

#### Linux / macOS

```bash
pip install cwltool
# Docker: https://docs.docker.com/engine/install/
# AWS CLI: https://aws.amazon.com/cli/
```

#### Windows (via WSL)

These scripts require a Unix-like environment. Use WSL:

```bash
# Install dependencies in WSL
sudo apt update
sudo apt install python3 python3-pip docker.io awscli
pip install cwltool

# Ensure Docker is running
sudo service docker start
```

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `download_fsl_test_data.sh` | Download FSL test data from OpenNeuro |
| `download_afni_test_data.sh` | Download AFNI test data from OpenNeuro |
| `download_ants_test_data.sh` | Download ANTs test data from OpenNeuro |
| `download_freesurfer_test_data.sh` | Download FreeSurfer test subject (bert) |
| `build_afni_test_image.sh` | Build custom AFNI Docker image with R |
| `verify_fsl_tools.sh` | Run all FSL CWL tools and report results |
| `verify_fsl_edges.sh` | Build a compatibility edge matrix for FSL tool pairs |
| `verify_fsl_chains.sh` | Run chain tests for FSL tools (length N) |
| `verify_cwl_edges.sh` | Build a compatibility edge matrix for all CWL tools in the repo |
| `verify_cwl_chains.sh` | Run chain tests across all CWL tools (length N) |
| `verify_afni_tools.sh` | Run all AFNI CWL tools and report results |
| `verify_ants_tools.sh` | Run all ANTs CWL tools and report results |
| `verify_freesurfer_tools.sh` | Run all FreeSurfer CWL tools and report results |

## Running Tests

### Quick Start

The verification scripts automatically download data if needed:

```bash
# Run from project root
bash utils/verify_fsl_tools.sh
```

### Manual Data Download

If you want to download data separately:

```bash
bash utils/download_fsl_test_data.sh
bash utils/download_afni_test_data.sh
bash utils/download_ants_test_data.sh
bash utils/download_freesurfer_test_data.sh
```

### Running Each Library's Tests

```bash
# FSL (30 tools)
bash utils/verify_fsl_tools.sh

# FSL compatibility matrix (pairwise edges)
bash utils/verify_fsl_edges.sh

# FSL chain testing (chains of length 3)
bash utils/verify_fsl_chains.sh --chain-length=3

# AFNI (44 tools)
bash utils/verify_afni_tools.sh

# ANTs (17 tools)
bash utils/verify_ants_tools.sh

# FreeSurfer (20 tools) - requires license file
export FS_LICENSE="/path/to/license.txt"
bash utils/verify_freesurfer_tools.sh
```

### Running Compatibility and Chains Across All Tools

These scripts build a compatibility matrix across every CWL tool in `public/cwl/*` and then use it to enumerate tool chains.

```bash
# Build a global compatibility matrix (job templates only)
bash utils/verify_cwl_edges.sh

# Build a global compatibility matrix and run tools to generate outputs for edge validation
bash utils/verify_cwl_edges.sh --run-tools

# Run global chains of length 3
bash utils/verify_cwl_chains.sh --chain-length=3
```

When `--run-tools` is used, each `verify_<lib>_tools.sh` script is executed without `--jobs-only` so tool outputs exist for runtime edge validation.

Outputs:

```
tests/work/cwl/edges/edges.tsv
tests/work/cwl/edges/edges.json
tests/work/cwl/edges/runs/edges_runtime.tsv
tests/work/cwl/edges/runs/edges_runtime.json
tests/work/cwl/edges/runs/edges_validated.tsv
tests/work/cwl/edges/runs/edges_validated.json
tests/work/cwl/chains/summary.tsv
```

### Building a Compatibility Matrix (FSL)

This step tests all ordered tool pairs using CWL input/output metadata and job templates to determine compatible edges.

```bash
bash utils/verify_fsl_edges.sh
```

Outputs:

```
tests/work/fsl/edges/edges.tsv
tests/work/fsl/edges/edges.json
```

### Running Tool Chains (FSL)

Tool chain execution uses the edge matrix to enumerate valid chains.

```bash
# Run chains of length 3 (tool1 → tool2 → tool3)
bash utils/verify_fsl_chains.sh --chain-length 3

# Limit to the first 10 chains (useful for smoke testing)
bash utils/verify_fsl_chains.sh --chain-length 3 --max-chains 10
```

Outputs:

```
tests/work/fsl/chains/summary.tsv
tests/work/fsl/chains/<chain_name>/
```

### Compatibility Rules

Edges are considered valid when:

1. CWL types match (File vs Directory, including array types)
2. CWL `format` matches (when present), otherwise
3. Output file extension matches the expected input extension (derived from job templates and CWL output globs)

If a tool has multiple outputs or ambiguous input ports, the edge matrix will pick the best scoring match based on the rules above.

### Re-running Previously Passed Tests

By default, passing tests are cached. To re-run everything:

```bash
bash utils/verify_fsl_tools.sh --rerun-passed
```

## Output Structure

After running tests, outputs are organized as:

```
tests/
├── data/                    # Downloaded test datasets (gitignored)
│   ├── openneuro/
│   │   ├── ds002979/        # T1w, BOLD, fieldmaps
│   │   ├── ds003676/        # Longitudinal T1w
│   │   └── ds002185/        # DWI data
│   └── freesurfer/
│       └── subjects/bert/   # Pre-reconstructed subject
└── work/                    # Test outputs (gitignored)
    └── fsl/
        ├── jobs/            # Generated YAML input files
        ├── out/             # Tool outputs (per-tool subdirs)
        ├── logs/            # Stdout/stderr logs
        ├── derived/         # Intermediate files (masks, matrices)
        └── summary.tsv      # Final results table
```

## Understanding Results

### Summary File

Each verification script produces a `summary.tsv`:

```
tool        status
bet         PASS
fast        PASS
fnirt       FAIL
probtrackx2 SKIP
```

| Status | Meaning |
|--------|---------|
| `PASS` | Tool ran successfully and outputs exist |
| `FAIL` | Tool failed or outputs missing |
| `SKIP` | Prerequisites not met (missing data/dependencies) |

### Viewing Logs

For failed tools, check the log file:

```bash
cat tests/work/fsl/logs/fnirt.log
```

## Test Data Sources

| Dataset | Source | Contents | Tools Tested |
|---------|--------|----------|--------------|
| ds002979 | [OpenNeuro](https://openneuro.org/datasets/ds002979) | T1w + BOLD + fieldmaps | Most preprocessing tools |
| ds003676 | [OpenNeuro](https://openneuro.org/datasets/ds003676) | Longitudinal T1w (3T/7T) | siena |
| ds002185 | [OpenNeuro](https://openneuro.org/datasets/ds002185) | DWI + bvec/bval | probtrackx2 |
| bert | [FreeSurfer](https://surfer.nmr.mgh.harvard.edu/) | Pre-reconstructed subject | Surface analysis tools |

## Environment Variables

### FSL

| Variable | Default | Description |
|----------|---------|-------------|
| `FSL_TEST_DATA_DIR` | `tests/data/openneuro` | Data download location |
| `FSL_TEST_WORK_DIR` | `tests/work/fsl` | Output directory |
| `FSL_DOCKER_IMAGE` | `brainlife/fsl:latest` | Docker image to use |
| `FSL_DOCKER_PLATFORM` | (auto) | Docker platform (e.g., `linux/amd64`) |
| `FSL_FNIRT_USE_CONFIG` | `0` | Use FNIRT config file |
| `FSL_SIENA_SUBSAMP` | `7` | SIENA downsampling level |

### AFNI

| Variable | Default | Description |
|----------|---------|-------------|
| `AFNI_TEST_DATA_DIR` | `tests/data/openneuro` | Data download location |
| `AFNI_TEST_RES_MM` | `6` | Resampling resolution (mm) |
| `AFNI_BOLD_CLIP_LEN` | `20` | BOLD clip length (volumes) |
| `AFNI_DISABLE_PULL` | `1` | Skip Docker image pull |

### ANTs

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTS_TEST_DATA_DIR` | `tests/data/openneuro` | Data download location |
| `ANTS_TEST_RES_MM` | `6` | Resampling resolution (mm) |
| `ANTS_NUM_THREADS` | `1` | Number of threads |

### FreeSurfer

| Variable | Default | Description |
|----------|---------|-------------|
| `FREESURFER_TEST_DATA_DIR` | `tests/data/freesurfer` | Data download location |
| `FS_LICENSE` | `tests/data/freesurfer/license.txt` | License file path |

## Troubleshooting

### "Missing required command: aws"

Install AWS CLI or manually download data:
```bash
# macOS
brew install awscli

# Linux
sudo apt install awscli

# Or download directly from OpenNeuro website
```

### "Docker permission denied"

Add your user to the docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### FreeSurfer License Error

FreeSurfer requires a license file. Get one free at:
https://surfer.nmr.mgh.harvard.edu/registration.html

Then set the path:
```bash
export FS_LICENSE="/path/to/license.txt"
```

### WSL: Slow Performance

Keep test data in the Linux filesystem for better performance:
```bash
# Good: ~/projects/neuro-analysis-frontend
# Slow: /mnt/c/Users/.../neuro-analysis-frontend
```

### Tool Fails But Works Manually

Check the generated job file and log:
```bash
cat tests/work/fsl/jobs/toolname.yml
cat tests/work/fsl/logs/toolname.log
```

## Adding New Tool Tests

To add a test for a new CWL tool:

1. Add the tool's CWL definition to `public/cwl/<library>/`
2. Edit the corresponding `verify_<library>_tools.sh`
3. Add a job file generation block:
   ```bash
   cat > "${JOB_DIR}/newtool.yml" <<EOF
   input:
     class: File
     path: "${INPUT_FILE}"
   output: "newtool_out"
   EOF
   run_tool "newtool" "${JOB_DIR}/newtool.yml"
   ```

## Resources

- [CWL User Guide](https://www.commonwl.org/user_guide/)
- [cwltool Documentation](https://github.com/common-workflow-language/cwltool)
- [OpenNeuro](https://openneuro.org/) - Public neuroimaging datasets
- [FSL Documentation](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki)
- [AFNI Documentation](https://afni.nimh.nih.gov/pub/dist/doc/htmldoc/)
- [ANTs Documentation](http://stnava.github.io/ANTs/)
- [FreeSurfer Documentation](https://surfer.nmr.mgh.harvard.edu/fswiki)
