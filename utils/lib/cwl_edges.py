#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

KNOWN_EXTS = [
    ".nii.gz",
    ".nii",
    ".mgz",
    ".mgh",
    ".gii",
    ".vtk",
    ".txt",
    ".tsv",
    ".csv",
    ".json",
    ".mat",
    ".dat",
    ".bval",
    ".bvec",
]


def run_cwl_print_pre(cwl_path: Path) -> dict:
    result = subprocess.run(
        ["cwltool", "--print-pre", str(cwl_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def normalize_port_id(port_id: str) -> str:
    if "#" in port_id:
        return port_id.split("#")[-1]
    if "/" in port_id:
        return port_id.rsplit("/", 1)[-1]
    return port_id


def normalize_type(port_type) -> str:
    if isinstance(port_type, list):
        filtered = [t for t in port_type if not (isinstance(t, str) and t == "null")]
        if not filtered:
            return "null"
        if len(filtered) == 1:
            return normalize_type(filtered[0])
        # keep list if multiple (treat as union)
        return "/".join(sorted(normalize_type(t) for t in filtered))
    if isinstance(port_type, dict):
        if port_type.get("type") == "array":
            items = normalize_type(port_type.get("items"))
            return f"array[{items}]"
        return str(port_type.get("type"))
    return str(port_type)


def normalize_formats(fmt) -> set:
    if not fmt:
        return set()
    if isinstance(fmt, list):
        return {str(f) for f in fmt}
    return {str(fmt)}


def extract_globs(output_binding) -> list:
    if not output_binding:
        return []
    glob = output_binding.get("glob")
    if not glob:
        return []
    if isinstance(glob, list):
        return [str(g) for g in glob]
    return [str(glob)]


def infer_extensions_from_globs(globs: list) -> set:
    exts = set()
    for glob in globs:
        for ext in KNOWN_EXTS:
            if ext in glob:
                exts.add(ext)
        if not exts:
            # fallback to last suffix-like portion
            match = re.search(r"(\.[A-Za-z0-9]+)(?:\*|$)", glob)
            if match:
                exts.add(match.group(1))
    return exts


def infer_extensions_from_job(job_data: dict, port_name: str) -> set:
    exts = set()
    if port_name not in job_data:
        return exts
    value = job_data[port_name]
    paths = []
    if isinstance(value, dict):
        path = value.get("path") or value.get("location")
        if path:
            paths.append(path)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                path = item.get("path") or item.get("location")
                if path:
                    paths.append(path)
    elif isinstance(value, str):
        paths.append(value)

    for path in paths:
        suffixes = Path(path).suffixes
        if len(suffixes) >= 2 and suffixes[-2:] == [".nii", ".gz"]:
            exts.add(".nii.gz")
        elif suffixes:
            exts.add(suffixes[-1])
    return exts


def load_job_template(job_path: Path) -> dict:
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    with job_path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle) or {}
    return data


def load_tool_metadata(libraries: list) -> dict:
    metadata = {}
    for library in libraries:
        lib_name = library["name"]
        cwl_dir = Path(library["cwl_dir"])
        job_dir = Path(library["job_dir"])
        for cwl_path in sorted(cwl_dir.glob("*.cwl")):
            tool = cwl_path.stem
            tool_id = f"{lib_name}/{tool}"
            cwl = run_cwl_print_pre(cwl_path)
            inputs = {}
            outputs = {}

            raw_inputs = cwl.get("inputs", [])
            if isinstance(raw_inputs, dict):
                raw_inputs = [dict(id=k, **v) for k, v in raw_inputs.items()]
            raw_outputs = cwl.get("outputs", [])
            if isinstance(raw_outputs, dict):
                raw_outputs = [dict(id=k, **v) for k, v in raw_outputs.items()]

            job_template = {}
            job_path = job_dir / f"{tool}.yml"
            if job_path.exists():
                job_template = load_job_template(job_path)

            for inp in raw_inputs:
                port_id = normalize_port_id(inp.get("id", ""))
                inputs[port_id] = {
                    "type": normalize_type(inp.get("type")),
                    "formats": sorted(normalize_formats(inp.get("format"))),
                    "extensions": sorted(infer_extensions_from_job(job_template, port_id)),
                }

            for outp in raw_outputs:
                port_id = normalize_port_id(outp.get("id", ""))
                outputs[port_id] = {
                    "type": normalize_type(outp.get("type")),
                    "formats": sorted(normalize_formats(outp.get("format"))),
                    "extensions": sorted(
                        infer_extensions_from_globs(extract_globs(outp.get("outputBinding")))
                    ),
                }

            metadata[tool_id] = {
                "library": lib_name,
                "tool": tool,
                "cwl_path": str(cwl_path),
                "job_dir": str(job_dir),
                "job_path": str(job_path),
                "inputs": inputs,
                "outputs": outputs,
            }

    return metadata


def best_edge(output_meta: dict, input_meta: dict) -> tuple:
    output_type = output_meta["type"]
    input_type = input_meta["type"]
    if output_type != input_type:
        return None

    output_formats = set(output_meta["formats"])
    input_formats = set(input_meta["formats"])
    if output_formats and input_formats:
        if output_formats.intersection(input_formats):
            return 3, "format"
        return None

    output_exts = set(output_meta["extensions"])
    input_exts = set(input_meta["extensions"])
    if output_exts and input_exts:
        if output_exts.intersection(input_exts):
            return 2, "extension"
        return None

    if not input_formats and not input_exts:
        return 1, "type-only"

    return None


def build_edges(metadata: dict) -> list:
    edges = []
    tools = sorted(metadata.keys())
    for source in tools:
        for target in tools:
            if source == target:
                continue
            best = None
            best_out = None
            best_in = None
            for out_port, out_meta in metadata[source]["outputs"].items():
                for in_port, in_meta in metadata[target]["inputs"].items():
                    match = best_edge(out_meta, in_meta)
                    if match is None:
                        continue
                    score, reason = match
                    if best is None or score > best:
                        best = score
                        best_out = (out_port, out_meta)
                        best_in = (in_port, in_meta)
            if best is None:
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "status": "FAIL",
                        "reason": "no-compatible-ports",
                    }
                )
            else:
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "status": "PASS",
                        "reason": best_in[1]["type"],
                        "score": best,
                        "match_reason": reason,
                        "output_port": best_out[0],
                        "input_port": best_in[0],
                    }
                )
    return edges


def write_edges(edges: list, out_tsv: Path) -> None:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", encoding="utf-8") as handle:
        handle.write("source\ttarget\tstatus\tscore\tmatch_reason\toutput_port\tinput_port\n")
        for edge in edges:
            handle.write(
                "{source}\t{target}\t{status}\t{score}\t{match_reason}\t{output_port}\t{input_port}\n".format(
                    source=edge.get("source"),
                    target=edge.get("target"),
                    status=edge.get("status"),
                    score=edge.get("score", ""),
                    match_reason=edge.get("match_reason", edge.get("reason", "")),
                    output_port=edge.get("output_port", ""),
                    input_port=edge.get("input_port", ""),
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CWL compatibility edge matrix.")
    parser.add_argument("--spec")
    parser.add_argument("--cwl-dir")
    parser.add_argument("--job-dir")
    parser.add_argument("--out-tsv", required=True)
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    libraries = []
    if args.spec:
        spec_path = Path(args.spec)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        libraries = spec.get("libraries", [])
    else:
        if not args.cwl_dir or not args.job_dir:
            raise SystemExit("Provide either --spec or both --cwl-dir and --job-dir.")
        cwl_dir = Path(args.cwl_dir)
        job_dir = Path(args.job_dir)
        libraries = [{"name": cwl_dir.name, "cwl_dir": str(cwl_dir), "job_dir": str(job_dir)}]

    metadata = load_tool_metadata(libraries)
    edges = build_edges(metadata)

    write_edges(edges, Path(args.out_tsv))
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out_json).open("w", encoding="utf-8") as handle:
        json.dump({"tools": metadata, "edges": edges}, handle, indent=2)


if __name__ == "__main__":
    main()
