from __future__ import annotations

import json
import os
from typing import Any

from .models import Scenario
from .utils import sha256_file


def scenario_from_log(log_path: str, scenario_id: str, default_params: dict[str, Any]) -> Scenario:
    """
    Accepts a JSON log (any structure) or any file; we hash it and store minimal metadata.
    """
    if not os.path.exists(log_path):
        raise FileNotFoundError(log_path)
    h = sha256_file(log_path)
    meta = {
        "kind": "json_log" if log_path.lower().endswith(".json") else "blob",
        "size": os.path.getsize(log_path),
    }
    return Scenario(
        scenario_id=scenario_id,
        source_log=os.path.basename(log_path),
        source_hash=h,
        metadata=meta,
        params=default_params or {},
    )


def save_scenario(s: Scenario, path: str) -> None:
    d = {
        "scenario_id": s.scenario_id,
        "source_log": s.source_log,
        "source_hash": s.source_hash,
        "metadata": s.metadata,
        "params": s.params,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def load_scenario(path: str) -> Scenario:
    d = json.load(open(path, encoding="utf-8"))
    return Scenario(
        scenario_id=d["scenario_id"],
        source_log=d["source_log"],
        source_hash=d["source_hash"],
        metadata=d.get("metadata", {}),
        params=d.get("params", {}),
    )
