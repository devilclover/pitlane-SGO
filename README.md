# Pitlane Sim-Gate Orchestrator (SGO)

**What it is**  
A CLI + library that turns logs into reproducible **simulation scenarios**, executes **parameter sweeps** (with a built-in deterministic dummy simulator or your own shell command), evaluates **policy gates** via a simple DSL, and emits **signed gate results** and a **brand-styled HTML report**.

**Why**  
Risky changes should rehearse before touching hardware. SGO automates "practice before impact" and binds every promotion decision to measurable evidence.

---

## Quick start (no external sim required)

```bash
pip install -e .

# 1) Create a scenario from a JSON log (any small JSON works)
simgate from-log examples/logs/drive_loop.json --scenario-out work/warehouse_s1.yaml

# 2) Run a parameter sweep with the built-in deterministic dummy simulator
simgate sweep --scenario work/warehouse_s1.yaml --grid "speed=0.6..1.2:4; friction=0.8,1.0" \
  --out-json work/results.json --out-html work/report.html

# 3) Evaluate policy gates and write a signed decision + attestation
simgate evaluate --results work/results.json --gates examples/gates/warehouse.yml \
  --out-decision work/decision.json --attestation work/decision.attestation.json

# 4) Verify the decision attestation
simgate verify --attestation work/decision.attestation.json
```

Open `work/report.html` in a browser for a clean report with Pitlane colors.

## Use your own simulator

Provide a shell command that writes metrics JSON to a file path given by `$SIM_OUT`:

```bash
simgate sweep --scenario work/warehouse_s1.yaml \
  --driver shell \
  --shell-cmd "python examples/shell_driver_example.py" \
  --out-json work/results.json --out-html work/report.html
```

The shell script must create `$SIM_OUT` with metrics like:

```json
{"time_to_goal_s": 42.2, "collisions": 0, "energy_kj": 12.7, "map_diff_iou": 0.91}
```

## Gate DSL (YAML)

```yaml
gates:
  - name: no_collisions
    metric: collisions
    op: "=="
    value: 0
  - name: time_to_goal
    metric: time_to_goal_s
    op: "<="
    value: 300
  - name: map_quality
    metric: map_diff_iou
    op: ">="
    value: 0.85

policy:
  risk: "med"
  promotion:
    on_pass: "rollout"
    on_fail: "block"
    canary_percent: 10
```

## What's inside

- **Scenario builder**: from logs to a scenario YAML with metadata and params
- **Sweeps**: define grids like `speed=0.6..1.2:4; friction=0.8,1.0`
- **Runners**:
  - `dummy` (default): deterministic metrics from scenario+params hash (reproducible)
  - `shell`: run your command, read metrics from `$SIM_OUT`
- **Gate engine**: evaluate gates with `==`, `!=`, `<`, `<=`, `>`, `>=`, `between`
- **Reports**: JSON summary + self-contained HTML with Pitlane palette
- **Attestations**: Ed25519 signatures for decisions; local key at `~/.pitlane/simgate_keys.json`

## License

Apache-2.0
