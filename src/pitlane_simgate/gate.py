from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import asdict
import operator
import yaml
from .models import GateRule, GateEval, GateDecision, RunResult

OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}

def load_gate_rules(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _eval_rule(rule: GateRule, metrics: Dict[str, Any]) -> GateEval:
    val = metrics.get(rule.metric)
    if rule.op == "between":
        lo, hi = rule.min, rule.max
        ok = (val is not None) and (lo is not None) and (hi is not None) and (lo <= val <= hi)
        return GateEval(name=rule.name, passed=bool(ok), reason=f"{rule.metric}={val} between {lo}..{hi}")
    elif rule.op in OPS:
        ok = OPS[rule.op](val, rule.value)
        return GateEval(name=rule.name, passed=bool(ok), reason=f"{rule.metric}={val} {rule.op} {rule.value}")
    else:
        return GateEval(name=rule.name, passed=False, reason=f"unknown op {rule.op}")

def evaluate_runs(results: List[RunResult], gates_cfg: Dict[str, Any]) -> GateDecision:
    gates = [GateRule(**g) for g in gates_cfg.get("gates", [])]
    risk = gates_cfg.get("policy", {}).get("risk", "med")
    promo = gates_cfg.get("policy", {}).get("promotion", {})
    on_pass = promo.get("on_pass", "rollout")
    on_fail = promo.get("on_fail", "block")
    canary = int(promo.get("canary_percent", 0))

    # Aggregate using worst-case across runs (strict)
    gate_pass_all = True
    evals_agg: List[GateEval] = []
    for g in gates:
        # if any run fails, the gate fails
        ok_runs = []
        for r in results:
            m = asdict(r.metrics)
            ev = _eval_rule(g, m)
            ok_runs.append(ev.passed)
        passed = all(ok_runs)
        gate_pass_all = gate_pass_all and passed
        # Reason summarizes pass rate
        reason = f"{g.name}: {sum(ok_runs)}/{len(ok_runs)} runs passed"
        evals_agg.append(GateEval(name=g.name, passed=passed, reason=reason))

    action = on_pass if gate_pass_all else on_fail
    return GateDecision(
        overall_pass=gate_pass_all, risk=risk, action=action, canary_percent=canary, timestamp=__import__("time").time().__int__(), gate_results=evals_agg
    )
