"""
Minimal shell driver example: reads params from $SIM_PARAMS and writes metrics JSON to $SIM_OUT.
Used by the --driver shell mode. This is a stub you can replace with Ignition/Isaac calls.
"""

import hashlib
import json
import os
import random

params = json.loads(os.environ.get("SIM_PARAMS", "{}"))
out = os.environ.get("SIM_OUT")
if not out:
    raise SystemExit("SIM_OUT not set")

seed_str = json.dumps(params, sort_keys=True)
seed = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest(), 16) % (2**32 - 1)
rng = random.Random(seed)

metrics = {
    "time_to_goal_s": round(rng.uniform(30, 200) / max(0.3, float(params.get("speed", 1.0))), 2),
    "collisions": 0 if rng.random() > 0.2 else 1,
    "energy_kj": round(rng.uniform(8, 70), 2),
    "map_diff_iou": round(rng.uniform(0.8, 0.97), 3),
    "notes": "shell-driver-stub",
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(metrics, f)
