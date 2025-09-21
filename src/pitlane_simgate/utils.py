from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

BLACK = "#111111"
PIT_RED = "#E10600"
WHITE = "#FFFFFF"


def now_s() -> int:
    return int(time.time())


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(8192), b""):
            h.update(ch)
    return h.hexdigest()


def mkdirp(p: str | Path) -> None:
    Path(p).mkdir(parents=True, exist_ok=True)


def json_dump(obj: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def json_load(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_grid(spec: str) -> dict[str, list]:
    """
    Parse grids like:
      "speed=0.6..1.2:4; friction=0.8,1.0"
    """
    out: dict[str, list] = {}
    if not spec:
        return out
    for part in [p.strip() for p in spec.split(";") if p.strip()]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        v = v.strip()
        if ".." in v and ":" in v:
            lo, rest = v.split("..", 1)
            hi, n = rest.split(":", 1)
            lo, hi, n = float(lo), float(hi), int(n)
            if n <= 1:
                out[k] = [lo]
            else:
                step = (hi - lo) / (n - 1)
                out[k] = [round(lo + i * step, 6) for i in range(n)]
        else:
            vals = [x.strip() for x in v.split(",") if x.strip()]
            # try cast to float if possible
            casted = []
            for x in vals:
                try:
                    casted.append(float(x))
                except ValueError:
                    casted.append(x)
            out[k] = casted
    return out


def product_grid(grid: dict[str, list]) -> Iterable[dict[str, Any]]:
    if not grid:
        yield {}
        return
    keys = list(grid.keys())

    def rec(i: int, acc: dict[str, Any]):
        if i == len(keys):
            yield acc.copy()
            return
        k = keys[i]
        for v in grid[k]:
            acc[k] = v
            yield from rec(i + 1, acc)

    yield from rec(0, {})
