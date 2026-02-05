#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from ruamel.yaml import YAML


yaml = YAML()

yaml.default_flow_style = False


def load_edges(edges_json: Path) -> dict:
    with edges_json.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_adjacency(edges: list) -> dict:
    adjacency = {}
    for edge in edges:
        if edge.get("status") != "PASS":
            continue
        adjacency.setdefault(edge["source"], []).append(edge)
    return adjacency


def enumerate_chains(adjacency: dict, length: int, allow_repeats: bool) -> List[List[dict]]:
    chains = []

    def dfs(path: List[dict], tools: List[str]):
        if len(tools) == length:
            chains.append(path.copy())
            return
        last_tool = tools[-1]
        for edge in adjacency.get(last_tool, []):
            next_tool = edge["target"]
            if not allow_repeats and next_tool in tools:
                continue
            path.append(edge)
            tools.append(next_tool)
            dfs(path, tools)
            tools.pop()
            path.pop()

    for start in sorted(adjacency.keys()):
        dfs([], [start])
    return chains


def extract_output_path(output_obj) -> str:
    if not output_obj:
        return ""
    if isinstance(output_obj, dict):
        path = output_obj.get("path") or output_obj.get("location")
        if path and path.startswith("file://"):
            path = urlparse(path).path
        return path
    if isinstance(output_obj, list):
        for item in output_obj:
            path = extract_output_path(item)
            if path:
                return path
    if isinstance(output_obj, str):
        return output_obj
    return ""


def verify_outputs(outputs_json: Path) -> bool:
    data = json.loads(outputs_json.read_text(encoding="utf-8"))
    paths = []

    def walk(obj):
        if obj is None:
            return
        if isinstance(obj, dict):
            if obj.get("class") in ("File", "Directory"):
                path = obj.get("path") or obj.get("location")
                if path and path.startswith("file://"):
                    path = urlparse(path).path
                if path:
                    paths.append(path)
            else:
                for value in obj.values():
                    walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(data)
    if not paths:
        return False
    return all(os.path.exists(p) for p in paths)


def run_chain(
    chain_edges: List[dict],
    tool_order: List[str],
    edges_meta: dict,
    out_dir: Path,
    rerun_passed: bool,
) -> str:
    chain_name = "__".join(tool_order).replace("/", "__")
    chain_root = out_dir / chain_name
    jobs_dir = chain_root / "jobs"
    logs_dir = chain_root / "logs"
    tools_out_dir = chain_root / "out"
    chain_root.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    tools_out_dir.mkdir(parents=True, exist_ok=True)

    status_file = chain_root / "status.json"
    if rerun_passed and status_file.exists():
        prev = json.loads(status_file.read_text(encoding="utf-8"))
        if prev.get("status") == "PASS":
            return "PASS"

    previous_output = None
    previous_edge = None

    for idx, tool_id in enumerate(tool_order):
        tool_meta = edges_meta["tools"][tool_id]
        job_template = Path(tool_meta["job_path"])
        if not job_template.exists():
            status_file.write_text(json.dumps({"status": "SKIP", "reason": "missing-job"}))
            return "SKIP"

        with job_template.open("r", encoding="utf-8") as handle:
            job_data = yaml.load(handle) or {}

        if idx > 0:
            input_port = previous_edge["input_port"]
            if not previous_output:
                status_file.write_text(json.dumps({"status": "FAIL", "reason": "missing-output"}))
                return "FAIL"
            output_obj = {"class": "File", "path": previous_output}
            if input_port in edges_meta["tools"][tool_id]["inputs"]:
                input_type = edges_meta["tools"][tool_id]["inputs"][input_port]["type"]
                if input_type.startswith("array"):
                    job_data[input_port] = [output_obj]
                else:
                    job_data[input_port] = output_obj
            else:
                job_data[input_port] = output_obj

        tool_key = tool_id.replace("/", "__")
        job_path = jobs_dir / f"{tool_key}.yml"
        with job_path.open("w", encoding="utf-8") as handle:
            yaml.dump(job_data, handle)

        tool_out = tools_out_dir / tool_key
        tool_out.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"{tool_key}.log"
        outputs_json = tool_out / "outputs.json"

        cwl_file = Path(tool_meta["cwl_path"])
        with log_path.open("w", encoding="utf-8") as log_handle, outputs_json.open(
            "w", encoding="utf-8"
        ) as out_handle:
            result = subprocess.run(
                ["cwltool", "--outdir", str(tool_out), str(cwl_file), str(job_path)],
                stdout=out_handle,
                stderr=log_handle,
            )

        if result.returncode != 0:
            status_file.write_text(json.dumps({"status": "FAIL", "reason": f"tool-failed:{tool_id}"}))
            return "FAIL"

        if not outputs_json.exists():
            status_file.write_text(json.dumps({"status": "FAIL", "reason": f"missing-outputs:{tool_id}"}))
            return "FAIL"

        if not verify_outputs(outputs_json):
            status_file.write_text(json.dumps({"status": "FAIL", "reason": f"outputs-invalid:{tool_id}"}))
            return "FAIL"

        outputs = json.loads(outputs_json.read_text(encoding="utf-8"))
        if idx < len(tool_order) - 1:
            output_port = chain_edges[idx]["output_port"]
            if output_port not in outputs:
                status_file.write_text(
                    json.dumps({"status": "FAIL", "reason": f"missing-port:{tool_id}.{output_port}"})
                )
                return "FAIL"
            previous_output = extract_output_path(outputs[output_port])
            if not previous_output:
                status_file.write_text(
                    json.dumps({"status": "FAIL", "reason": f"empty-output:{tool_id}.{output_port}"})
                )
                return "FAIL"

        previous_edge = chain_edges[idx] if idx < len(chain_edges) else None

    status_file.write_text(json.dumps({"status": "PASS"}))
    return "PASS"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CWL tool chains.")
    parser.add_argument("--edges-json", required=True)
    parser.add_argument("--cwl-dir")
    parser.add_argument("--job-dir")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--chain-length", type=int, required=True)
    parser.add_argument("--max-chains", type=int, default=0)
    parser.add_argument("--allow-repeats", action="store_true")
    parser.add_argument("--rerun-passed", action="store_true")
    args = parser.parse_args()

    edges_meta = load_edges(Path(args.edges_json))
    adjacency = build_adjacency(edges_meta["edges"])
    chains = enumerate_chains(adjacency, args.chain_length, args.allow_repeats)
    if args.max_chains:
        chains = chains[: args.max_chains]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "summary.tsv"
    with summary.open("w", encoding="utf-8") as handle:
        handle.write("chain\tstatus\n")
    for chain_edges in chains:
        tool_order = [chain_edges[0]["source"]] + [edge["target"] for edge in chain_edges]
        status = run_chain(
            chain_edges,
            tool_order,
            edges_meta,
            out_dir,
            args.rerun_passed,
        )
        chain_name = "__".join(tool_order).replace("/", "__")
        with summary.open("a", encoding="utf-8") as handle:
            handle.write(f"{chain_name}\t{status}\n")


if __name__ == "__main__":
    main()
