"""Unit tests for SyntheticScenarioGenerator in tools/simulate.py."""

import pytest

from tools.simulate import SyntheticScenarioGenerator


@pytest.mark.sim
def test_scenario_generation():
    scenarios = ["compliant", "no_helmet", "restricted_entry", "danger_dwell", "crowd", "flicker"]
    for sc in scenarios:
        gen = SyntheticScenarioGenerator(scenario=sc, fps=25.0)
        frame_dict = gen.generate_frame(0, 0.0)
        assert frame_dict["frame_id"] == 0
        assert frame_dict["ts"] == 0.0
        assert "objects" in frame_dict
        assert len(frame_dict["objects"]) > 0

        # Test image rendering with OpenCV
        img = gen.render_frame_image(frame_dict)
        assert img.shape == (1080, 1920, 3)
