from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
from typing import Any

from .models import Metrics, RunResult, RunSpec, Scenario


def _deterministic_rng(seed_str: str) -> random.Random:
    # Seed from sha256 hex to int
    seed = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest(), 16) % (2**32 - 1)
    return random.Random(seed)


def _dummy_simulate(s: Scenario, params: dict[str, Any]) -> Metrics:
    """
    Deterministic pseudo-sim. Produces plausible metrics from scenario+params hash.
    """
    key = json.dumps(
        {"scenario": s.scenario_id, "hash": s.source_hash, "params": params}, sort_keys=True
    )
    rng = _deterministic_rng(key)

    # Base values
    time_to_goal = rng.uniform(20.0, 240.0)
    energy = rng.uniform(5.0, 80.0)
    iou = rng.uniform(0.75, 0.98)
    collisions = 0 if rng.random() > 0.15 else rng.randint(1, 3)

    # Param effects (ad hoc but deterministic)
    speed = float(params.get("speed", s.params.get("speed", 1.0)))
    friction = float(params.get("friction", s.params.get("friction", 1.0)))

    time_to_goal /= max(0.3, min(2.0, speed))
    energy *= (1.0 + (speed - 1.0) * 0.3) * (2.0 - min(1.5, friction))
    iou -= max(0.0, (speed - 1.0)) * 0.02
    if friction < 0.9 and rng.random() < 0.3:
        collisions = max(collisions, 1)

    return Metrics(
        time_to_goal_s=round(time_to_goal, 2),
        collisions=int(collisions),
        energy_kj=round(energy, 2),
        map_diff_iou=round(max(0.0, min(1.0, iou)), 3),
        notes="dummy-deterministic",
    )


def _shell_simulate(shell_cmd: str, env: dict[str, str]) -> Metrics:
    """
    Run user-provided command; it must write JSON metrics to SIM_OUT path.
    """
    sim_out = env["SIM_OUT"]
    # Ensure prior file removed
    if os.path.exists(sim_out):
        os.remove(sim_out)
    subprocess.check_call(shell_cmd, shell=True, env={**os.environ, **env})
    if not os.path.exists(sim_out):
        raise RuntimeError("Shell driver did not produce metrics JSON at $SIM_OUT")
    data = json.load(open(sim_out, encoding="utf-8"))
    return Metrics(
        time_to_goal_s=float(data["time_to_goal_s"]),
        collisions=int(data["collisions"]),
        energy_kj=float(data["energy_kj"]),
        map_diff_iou=float(data["map_diff_iou"]),
        notes=data.get("notes"),
    )


def run_sweep(
    scenario: Scenario,
    runs: list[RunSpec],
    driver: str = "dummy",
    shell_cmd: str | None = None,
    work_dir: str = "work",
) -> list[RunResult]:
    os.makedirs(work_dir, exist_ok=True)
    results: list[RunResult] = []
    for rs in runs:
        if driver == "dummy":
            metrics = _dummy_simulate(scenario, rs.params)
        elif driver == "shell":
            if not shell_cmd:
                raise ValueError("shell driver requires --shell-cmd")
            sim_out = os.path.join(work_dir, f"{rs.run_id}.metrics.json")
            env = {
                "SIM_SCENARIO_ID": scenario.scenario_id,
                "SIM_PARAMS": json.dumps(rs.params),
                "SIM_OUT": sim_out,
            }
            metrics = _shell_simulate(shell_cmd, env)
        else:
            raise ValueError(f"unknown driver: {driver}")

        results.append(
            RunResult(
                run_id=rs.run_id, scenario_id=rs.scenario_id, params=rs.params, metrics=metrics
            )
        )
    return results
