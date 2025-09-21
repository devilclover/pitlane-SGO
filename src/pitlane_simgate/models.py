from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from .utils import now_s

@dataclass
class Scenario:
    scenario_id: str
    source_log: str
    source_hash: str
    metadata: Dict[str, Any]
    params: Dict[str, Any]

@dataclass
class RunSpec:
    scenario_id: str
    run_id: str
    params: Dict[str, Any]

@dataclass
class Metrics:
    time_to_goal_s: float
    collisions: int
    energy_kj: float
    map_diff_iou: float
    notes: Optional[str] = None

@dataclass
class RunResult:
    run_id: str
    scenario_id: str
    params: Dict[str, Any]
    metrics: Metrics

@dataclass
class GateRule:
    name: str
    metric: str
    op: str
    value: Any = None
    min: Any = None
    max: Any = None

@dataclass
class GateEval:
    name: str
    passed: bool
    reason: str

@dataclass
class GateDecision:
    overall_pass: bool
    risk: str
    action: str
    canary_percent: int
    timestamp: int
    gate_results: List[GateEval]

@dataclass
class Attestation:
    schema: str
    decision: GateDecision
    results_hash: str
    signer_pub: Optional[str] = None
    signature: Optional[str] = None

    @staticmethod
    def now() -> int:
        return now_s()
