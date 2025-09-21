from __future__ import annotations

import json
import os
from typing import Any

import typer
from rich import print as rprint

from .crypto import ensure_keys, sign_payload
from .gate import evaluate_runs, load_gate_rules
from .models import Metrics, RunResult
from .report import write_report
from .ros2_adapter import emit_ignition_world, scenario_from_ros2_bag
from .runner import run_sweep
from .scenario import load_scenario, save_scenario, scenario_from_log
from .utils import json_dump, mkdirp, parse_grid, product_grid

app = typer.Typer(add_completion=False, help="Pitlane Sim-Gate Orchestrator")

# Default values for typer options
DEFAULT_SCENARIO_OUT = "work/scenario.json"
DEFAULT_SCENARIO_ID = "scenario-1"
DEFAULT_ROS2_SCENARIO_OUT = "work/scenario_ros2.json"
DEFAULT_ROS2_SCENARIO_ID = "scenario-ros2"
DEFAULT_PARAMS: list[str] = []

# Module-level typer options to avoid B008 errors
DEFAULT_PARAMS_OPTION = typer.Option([], help="Default params like key=val (floats or strings)")


@app.command()
def from_log(
    log_path: str = typer.Argument(..., help="Path to JSON log or any file to hash"),
    scenario_out: str = typer.Option(DEFAULT_SCENARIO_OUT, "--scenario-out"),
    scenario_id: str = typer.Option(DEFAULT_SCENARIO_ID, help="Scenario identifier"),
    default_params: list[str] = DEFAULT_PARAMS_OPTION,
):
    params: dict[str, Any] = {}
    for kv in default_params:
        if "=" in kv:
            k, v = kv.split("=", 1)
            try:
                v = float(v)
            except ValueError:
                pass
            params[k] = v
    sc = scenario_from_log(log_path, scenario_id=scenario_id, default_params=params)
    mkdirp(os.path.dirname(scenario_out) or ".")
    save_scenario(sc, scenario_out)
    rprint({"scenario_out": scenario_out, "source_hash": sc.source_hash, "params": sc.params})


@app.command("ros2-scenario")
def ros2_scenario(
    bag_dir: str = typer.Argument(..., help="Path to rosbag2 folder containing metadata.yaml"),
    scenario_out: str = typer.Option(DEFAULT_ROS2_SCENARIO_OUT, "--scenario-out"),
    scenario_id: str = typer.Option(DEFAULT_ROS2_SCENARIO_ID, help="Scenario identifier"),
    default_params: list[str] = DEFAULT_PARAMS_OPTION,
):
    params: dict[str, Any] = {}
    for kv in default_params:
        if "=" in kv:
            k, v = kv.split("=", 1)
            try:
                v = float(v)
            except ValueError:
                pass
            params[k] = v
    sc = scenario_from_ros2_bag(bag_dir, scenario_id=scenario_id, default_params=params)
    mkdirp(os.path.dirname(scenario_out) or ".")
    save_scenario(sc, scenario_out)
    topics = sc.metadata.get("topics", [])[:3]
    rprint({"scenario_out": scenario_out, "source_hash": sc.source_hash, "topics": topics})


@app.command("emit-sdf")
def emit_sdf(
    scenario: str = typer.Option(..., help="Scenario JSON created by from-log or ros2-scenario"),
    out_sdf: str = typer.Option("work/world.sdf", help="Output SDF world path"),
    world_name: str = typer.Option("pitlane_world", help="World name"),
):
    sc = load_scenario(scenario)
    emit_ignition_world(sc, out_sdf=out_sdf, world_name=world_name)
    rprint({"sdf": out_sdf, "world": world_name})


@app.command()
def sweep(
    scenario: str = typer.Option(..., help="Scenario JSON created by from-log or ros2-scenario"),
    param_grid: str = typer.Option(
        ..., help="Parameter grid like 'speed:1.0,1.5,2.0;friction:0.8,1.0'"
    ),
    out_results: str = typer.Option("work/results.json", help="Output results JSON"),
    simulator: str = typer.Option("dummy", help="Simulator: 'dummy' or 'shell:command'"),
):
    sc = load_scenario(scenario)
    grid = parse_grid(param_grid)
    runs = product_grid(grid)
    results = run_sweep(sc, runs, simulator=simulator)
    mkdirp(os.path.dirname(out_results) or ".")
    json_dump(results, out_results)
    rprint({"runs": len(results), "out_results": out_results})


@app.command()
def evaluate(
    results: str = typer.Option(..., help="JSON produced by sweep"),
    gates: str = typer.Option(..., help="Gate YAML"),
    out_decision: str = typer.Option("work/decision.json"),
    out_attestation: str = typer.Option("work/decision.attestation.json"),
    out_html: str = typer.Option("work/report.html"),
    out_json: str = typer.Option("work/report.json"),
):
    raw = json.load(open(results, encoding="utf-8"))
    runs = []
    for it in raw:
        metrics_data = it["metrics"]
        metrics = Metrics(
            time_to_goal_s=metrics_data["time_to_goal_s"],
            collisions=metrics_data["collisions"],
            energy_kj=metrics_data["energy_kj"],
            map_diff_iou=metrics_data["map_diff_iou"],
            notes=metrics_data.get("notes"),
        )
        rr = RunResult(
            run_id=it["run_id"],
            scenario_id=it["scenario_id"],
            params=it["params"],
            metrics=metrics,
        )
        runs.append(rr)
    rules = load_gate_rules(gates)
    decision = evaluate_runs(runs, rules)
    mkdirp(os.path.dirname(out_decision) or ".")
    json_dump(decision, out_decision)
    # Attestation
    ensure_keys()
    att = sign_payload(decision)
    json_dump(att, out_attestation)
    # Report
    write_report(runs, decision, out_json, out_html)
    rprint({"decision": out_decision, "attestation": out_attestation, "html": out_html})


@app.command()
def verify(
    decision: str = typer.Option(..., help="Decision JSON"),
    attestation: str = typer.Option(..., help="Attestation JSON"),
):
    with open(decision, encoding="utf-8") as f:
        decision_data = json.load(f)
    with open(attestation, encoding="utf-8") as f:
        att_data = json.load(f)
    # Verify signature
    from .crypto import verify_payload

    valid = verify_payload(decision_data, att_data)
    rprint({"valid": valid, "decision": decision, "attestation": attestation})


if __name__ == "__main__":
    app()
