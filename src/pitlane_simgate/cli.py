from __future__ import annotations

import json
import os
from typing import Any

import typer
from rich import print as rprint

from .crypto import ensure_keys, sign_payload
from .gate import evaluate_runs, load_gate_rules
from .models import GateDecision, Metrics, RunResult, RunSpec
from .report import write_report
from .ros2_adapter import emit_ignition_world, scenario_from_ros2_bag
from .runner import run_sweep
from .scenario import load_scenario, save_scenario, scenario_from_log
from .utils import json_dump, mkdirp, parse_grid, product_grid, sha256_file

app = typer.Typer(add_completion=False, help="Pitlane Sim-Gate Orchestrator")


@app.command()
def from_log(
    log_path: str = typer.Argument(..., help="Path to JSON log or any file to hash"),
    scenario_out: str = typer.Option("work/scenario.json", "--scenario-out"),
    scenario_id: str = typer.Option("scenario-1", help="Scenario identifier"),
    default_params: list[str] = typer.Option(
        [], help="Default params like key=val (floats or strings)"
    ),
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
    sc = scenario_from_log(log_path, scenario_id, params)
    mkdirp(os.path.dirname(scenario_out) or ".")
    save_scenario(sc, scenario_out)
    rprint({"scenario_out": scenario_out, "source_hash": sc.source_hash, "params": sc.params})


@app.command("ros2-scenario")
def ros2_scenario(
    bag_dir: str = typer.Argument(..., help="Path to rosbag2 folder containing metadata.yaml"),
    scenario_out: str = typer.Option("work/scenario_ros2.json", "--scenario-out"),
    scenario_id: str = typer.Option("scenario-ros2", help="Scenario identifier"),
    default_params: list[str] = typer.Option(
        [], help="Default params like key=val (floats or strings)"
    ),
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
    rprint(
        {
            "scenario_out": scenario_out,
            "source_hash": sc.source_hash,
            "topics": sc.metadata.get("topics", [])[:3],
        }
    )


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
    scenario: str = typer.Option(..., help="Scenario JSON created by from-log / ros2-scenario"),
    grid: str = typer.Option(
        "", "--grid", help="Param grid like 'speed=0.6..1.2:4; friction=0.8,1.0'"
    ),
    driver: str = typer.Option("dummy", help="dummy | shell"),
    shell_cmd: str | None = typer.Option(
        None, help="Command for shell driver; must write $SIM_OUT JSON"
    ),
    out_json: str = typer.Option("work/results.json"),
    out_html: str = typer.Option("work/report.html"),
    work_dir: str = typer.Option("work"),
):
    from .scenario import load_scenario

    sc = load_scenario(scenario)
    g = parse_grid(grid)
    runs: list[RunSpec] = []
    idx = 0
    for params in product_grid(g):
        run_id = f"run{idx}"
        runs.append(RunSpec(scenario_id=sc.scenario_id, run_id=run_id, params=params))
        idx += 1
    if not runs:
        runs = [RunSpec(scenario_id=sc.scenario_id, run_id="run0", params={})]
    results: list[RunResult] = run_sweep(
        sc, runs, driver=driver, shell_cmd=shell_cmd, work_dir=work_dir
    )
    json_dump(
        [
            {
                "run_id": r.run_id,
                "scenario_id": r.scenario_id,
                "params": r.params,
                "metrics": r.metrics.__dict__,
            }
            for r in results
        ],
        out_json,
    )
    rprint(
        {
            "runs": len(results),
            "out_json": out_json,
            "hint": "next: simgate evaluate --results ... --gates ... --out-html report.html",
        }
    )


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

    gates_cfg = load_gate_rules(gates)
    decision: GateDecision = evaluate_runs(runs, gates_cfg)

    write_report(runs, decision, out_json=out_json, out_html=out_html)

    keys = ensure_keys()
    payload = {
        "schema": "pitlane.simgate.decision/0.1",
        "decision": decision.__dict__
        | {"gate_results": [gr.__dict__ for gr in decision.gate_results]},
        "results_sha256": sha256_file(results),
    }
    sig = sign_payload(payload, keys["ed25519_secret_hex"])
    att = {
        "schema": "pitlane.simgate.decision/0.1",
        "decision": payload["decision"],
        "results_hash": payload["results_sha256"],
        "signer_pub": keys["ed25519_public_hex"],
        "signature": sig,
    }
    json_dump(
        decision.__dict__ | {"gate_results": [gr.__dict__ for gr in decision.gate_results]},
        out_decision,
    )
    json_dump(att, out_attestation)
    rprint(
        {
            "overall_pass": decision.overall_pass,
            "action": decision.action,
            "report": out_html,
            "attestation": out_attestation,
        }
    )


@app.command()
def verify(attestation: str = typer.Option(..., help="decision.attestation.json")):
    data = json.load(open(attestation, encoding="utf-8"))
    ok = all(k in data for k in ("schema", "decision", "results_hash", "signer_pub", "signature"))
    rprint({"attestation_valid_format": ok, "schema": data.get("schema")})
