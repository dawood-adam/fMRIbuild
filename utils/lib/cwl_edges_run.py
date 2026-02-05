#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from ruamel.yaml import YAML
import subprocess


yaml = YAML()

yaml.default_flow_style = False


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


def load_edges(edges_json: Path) -> dict:
    return json.loads(edges_json.read_text(encoding="utf-8"))


def get_tool_output(tool_meta: dict, output_port: str) -> str:
    job_dir = Path(tool_meta["job_dir"])
    out_dir = job_dir.parent / "out" / tool_meta["tool"]
    outputs_json = out_dir / "outputs.json"
    if not outputs_json.exists():
        return ""
    outputs = json.loads(outputs_json.read_text(encoding="utf-8"))
    if output_port not in outputs:
        return ""
    return extract_output_path(outputs[output_port])


def run_edge(edge: dict, edges_meta: dict, runs_dir: Path) -> dict:
    source = edge["source"]
    target = edge["target"]
    output_port = edge["output_port"]
    input_port = edge["input_port"]

    source_meta = edges_meta["tools"][source]
    target_meta = edges_meta["tools"][target]

    output_path = get_tool_output(source_meta, output_port)
    if not output_path:
        return {"status": "SKIP", "reason": "missing-source-output"}
    if not os.path.exists(output_path):
        return {"status": "FAIL", "reason": "source-output-missing"}

    job_template = Path(target_meta["job_path"])
    if not job_template.exists():
        return {"status": "SKIP", "reason": "missing-job"}

    with job_template.open("r", encoding="utf-8") as handle:
        job_data = yaml.load(handle) or {}

    output_obj = {"class": "File", "path": output_path}
    input_type = edges_meta["tools"][target]["inputs"].get(input_port, {}).get("type", "")
    if input_type.startswith("array"):
        job_data[input_port] = [output_obj]
    else:
        job_data[input_port] = output_obj

    edge_name = f"{source}__{target}".replace("/", "__")
    edge_dir = runs_dir / edge_name
    edge_dir.mkdir(parents=True, exist_ok=True)
    job_path = edge_dir / "job.yml"
    log_path = edge_dir / "run.log"
    outputs_json = edge_dir / "outputs.json"

    with job_path.open("w", encoding="utf-8") as handle:
        yaml.dump(job_data, handle)

    cwl_file = Path(target_meta["cwl_path"])
    with log_path.open("w", encoding="utf-8") as log_handle, outputs_json.open(
        "w", encoding="utf-8"
    ) as out_handle:
        result = subprocess.run(
            ["cwltool", "--outdir", str(edge_dir), str(cwl_file), str(job_path)],
            stdout=out_handle,
            stderr=log_handle,
        )

    if result.returncode != 0:
        return {"status": "FAIL", "reason": "tool-failed"}
    if not outputs_json.exists():
        return {"status": "FAIL", "reason": "missing-outputs"}
    if not verify_outputs(outputs_json):
        return {"status": "FAIL", "reason": "outputs-invalid"}

    return {"status": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CWL compatibility edges.")
    parser.add_argument("--edges-json", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    edges_meta = load_edges(Path(args.edges_json))
    runs_dir = Path(args.out_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)

    results = []
    summary_tsv = runs_dir / "edges_runtime.tsv"
    with summary_tsv.open("w", encoding="utf-8") as handle:
        handle.write(
            "source\ttarget\tstatus\truntime_status\truntime_reason\toutput_port\tinput_port\n"
        )

    for edge in edges_meta["edges"]:
        if edge.get("status") != "PASS":
            result = {**edge, "runtime_status": "SKIP", "runtime_reason": "precheck-fail"}
            results.append(result)
            with summary_tsv.open("a", encoding="utf-8") as handle:
                handle.write(
                    "{source}\t{target}\t{status}\t{runtime_status}\t{runtime_reason}\t{output_port}\t{input_port}\n".format(
                        source=result.get("source"),
                        target=result.get("target"),
                        status=result.get("status"),
                        runtime_status=result.get("runtime_status"),
                        runtime_reason=result.get("runtime_reason", ""),
                        output_port=result.get("output_port", ""),
                        input_port=result.get("input_port", ""),
                    )
                )
            continue
        outcome = run_edge(edge, edges_meta, runs_dir)
        result = {
            **edge,
            "runtime_status": outcome["status"],
            "runtime_reason": outcome.get("reason", ""),
        }
        results.append(result)
        with summary_tsv.open("a", encoding="utf-8") as handle:
            handle.write(
                "{source}\t{target}\t{status}\t{runtime_status}\t{runtime_reason}\t{output_port}\t{input_port}\n".format(
                    source=result.get("source"),
                    target=result.get("target"),
                    status=result.get("status"),
                    runtime_status=result.get("runtime_status"),
                    runtime_reason=result.get("runtime_reason", ""),
                    output_port=result.get("output_port", ""),
                    input_port=result.get("input_port", ""),
                )
            )

    out_json = runs_dir / "edges_runtime.json"
    out_json.write_text(json.dumps({"edges": results}, indent=2), encoding="utf-8")

    validated = []
    for edge in results:
        validated_status = "FAIL"
        validated_reason = edge.get("runtime_reason", "")
        if edge.get("status") == "PASS" and edge.get("runtime_status") == "PASS":
            validated_status = "PASS"
            validated_reason = ""
        elif edge.get("runtime_status") == "SKIP":
            validated_status = "SKIP"
            validated_reason = edge.get("runtime_reason", "")
        validated.append({**edge, "validated_status": validated_status, "validated_reason": validated_reason})

    validated_tsv = runs_dir / "edges_validated.tsv"
    with validated_tsv.open("w", encoding="utf-8") as handle:
        handle.write(
            "source\ttarget\tvalidated_status\tvalidated_reason\toutput_port\tinput_port\n"
        )
        for edge in validated:
            handle.write(
                "{source}\t{target}\t{validated_status}\t{validated_reason}\t{output_port}\t{input_port}\n".format(
                    source=edge.get("source"),
                    target=edge.get("target"),
                    validated_status=edge.get("validated_status"),
                    validated_reason=edge.get("validated_reason", ""),
                    output_port=edge.get("output_port", ""),
                    input_port=edge.get("input_port", ""),
                )
            )

    validated_json = runs_dir / "edges_validated.json"
    validated_json.write_text(json.dumps({"edges": validated}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
