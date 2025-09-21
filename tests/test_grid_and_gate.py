from pitlane_simgate.utils import parse_grid, product_grid
from pitlane_simgate.gate import evaluate_runs
from pitlane_simgate.models import RunResult, Metrics

def test_parse_grid_and_product():
    g = parse_grid("speed=0.6..1.2:4; friction=0.8,1.0")
    assert list(g.keys()) == ["speed","friction"]
    pts = list(product_grid(g))
    assert len(pts) == 4 * 2

def test_gate_eval_simple():
    # Create fake results: two runs, both good
    ok = Metrics(time_to_goal_s=100, collisions=0, energy_kj=10, map_diff_iou=0.9)
    rr1 = RunResult(run_id="r1", scenario_id="s1", params={"speed":1.0}, metrics=ok)
    rr2 = RunResult(run_id="r2", scenario_id="s1", params={"speed":1.2}, metrics=ok)
    gates_cfg = {
      "gates":[
        {"name":"no_collisions","metric":"collisions","op":"==","value":0},
        {"name":"time_to_goal","metric":"time_to_goal_s","op":"<=","value":300}
      ],
      "policy":{"risk":"med","promotion":{"on_pass":"rollout","on_fail":"block","canary_percent":10}}
    }
    dec = evaluate_runs([rr1, rr2], gates_cfg)
    assert dec.overall_pass is True
    assert dec.action == "rollout"
