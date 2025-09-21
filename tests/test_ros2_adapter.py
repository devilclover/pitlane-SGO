from pathlib import Path
from pitlane_simgate.ros2_adapter import scenario_from_ros2_bag, emit_ignition_world

def test_ros2_scenario_and_sdf(tmp_path: Path):
    # Use example metadata
    bag_dir = Path(__file__).parent.parent / "examples" / "ros2_bag"
    sc = scenario_from_ros2_bag(str(bag_dir), scenario_id="s_ros2", default_params={"speed":1.1})
    assert sc.scenario_id == "s_ros2"
    assert sc.metadata.get("kind") == "rosbag2"
    assert isinstance(sc.metadata.get("duration_sec"), float)
    assert "topics" in sc.metadata
    # Emit an SDF
    out_sdf = tmp_path / "world.sdf"
    emit_ignition_world(sc, out_sdf=str(out_sdf), world_name="test_world")
    assert out_sdf.exists()
    txt = out_sdf.read_text(encoding="utf-8")
    assert "<world name=\"test_world\">" in txt
