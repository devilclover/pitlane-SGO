from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from .models import Scenario


def _load_metadata_yaml(bag_path: str | Path) -> dict[str, Any]:
    """Load rosbag2 metadata.yaml from a bag folder (or a direct path to metadata.yaml)."""
    p = Path(bag_path)
    meta_path = p if p.name == "metadata.yaml" else (p / "metadata.yaml")
    if not meta_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found at {meta_path}")
    with open(meta_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_core(meta: dict[str, Any]) -> tuple[float, list[dict]]:
    """
    Return (duration_sec, topics_info[ {name,type,count} ]) in a robust way
    for typical rosbag2 metadata structures.
    """
    root = meta.get("rosbag2_bagfile_information", meta)
    # duration
    dur = root.get("duration", {})
    if isinstance(dur, dict) and "nanoseconds" in dur:
        duration_sec = float(dur["nanoseconds"]) / 1e9
    elif isinstance(dur, (int, float)):
        duration_sec = float(dur)
    else:
        duration_sec = 0.0

    # topics
    topics_info = []
    tlist = root.get("topics_with_message_count", [])
    for t in tlist:
        tm = t.get("topic_metadata", {})
        topics_info.append(
            {
                "name": tm.get("name", ""),
                "type": tm.get("type", ""),
                "count": int(t.get("message_count", 0)),
            }
        )
    return duration_sec, topics_info


def scenario_from_ros2_bag(
    bag_dir: str,
    scenario_id: str = "scenario_ros2",
    default_params: dict[str, Any] | None = None,
) -> Scenario:
    """
    Build a Scenario from rosbag2 metadata only (no ROS libs needed).
    Uses metadata.yaml and hashes the files listed under relative_file_paths (if present).
    """
    meta = _load_metadata_yaml(bag_dir)
    root = meta.get("rosbag2_bagfile_information", meta)
    # Combine metadata + listed files for a stronger source hash
    hasher = hashlib.sha256()
    hasher.update(yaml.safe_dump(meta).encode("utf-8"))
    for rel in root.get("relative_file_paths", []):
        fpath = Path(bag_dir) / rel
        if fpath.exists():
            with open(fpath, "rb") as f:
                for ch in iter(lambda: f.read(8192), b""):
                    hasher.update(ch)
    source_hash = hasher.hexdigest()

    duration_sec, topics_info = _extract_core(meta)

    # Heuristic: pick a likely pose/odom topic if present
    odom_topic = None
    for cand in topics_info:
        if cand["name"] == "/odom" or cand["type"].endswith("Odometry"):
            odom_topic = cand["name"]
            break

    metadata = {
        "kind": "rosbag2",
        "duration_sec": duration_sec,
        "topics": topics_info,
        "odom_topic": odom_topic,
    }

    params = default_params.copy() if default_params else {}
    # Set plausible defaults if not provided
    params.setdefault("speed", 1.0)
    params.setdefault("friction", 1.0)

    return Scenario(
        scenario_id=scenario_id,
        source_log="metadata.yaml",
        source_hash=source_hash,
        metadata=metadata,
        params=params,
    )


def emit_ignition_world(
    scenario: Scenario,
    out_sdf: str,
    world_name: str = "pitlane_world",
    gravity: tuple[float, float, float] = (0, 0, -9.81),
) -> None:
    """
    Emit a minimal SDF world that encodes a couple of scenario params as world properties.
    This is a placeholder world intended to be extended by users.
    """
    # Map scenario params to simple physics values
    friction = float(scenario.params.get("friction", 1.0))
    friction = max(0.1, min(2.0, friction))

    sdf = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="{world_name}">
    <gravity>{gravity[0]} {gravity[1]} {gravity[2]}</gravity>
    <physics type="ignored">
      <max_step_size>0.004</max_step_size>
      <real_time_update_rate>250</real_time_update_rate>
    </physics>
    <scene>
      <ambient>0.1 0.1 0.1 1</ambient>
      <background>0.01 0.01 0.01 1</background>
    </scene>
    <!-- Simple ground plane -->
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>1000 1000</size></plane></geometry>
          <surface>
            <friction>
              <ode>
                <mu>{friction}</mu>
                <mu2>{friction}</mu2>
              </ode>
            </friction>
          </surface>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>1000 1000</size></plane></geometry>
          <material><ambient>0.08 0.08 0.08 1</ambient></material>
        </visual>
      </link>
    </model>

    <!-- Placeholder for an agent start pose -->
    <model name="agent_start">
      <pose>0 0 0.1 0 0 0</pose>
      <static>true</static>
      <link name="marker">
        <visual name="marker_vis">
          <geometry><box><size>0.4 0.4 0.1</size></box></geometry>
          <material><diffuse>0.88 0.02 0.02 1</diffuse></material>
        </visual>
      </link>
    </model>
  </world>
</sdf>
"""
    Path(out_sdf).parent.mkdir(parents=True, exist_ok=True)
    with open(out_sdf, "w", encoding="utf-8") as f:
        f.write(sdf)
