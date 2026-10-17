import pytest

from tools.soak_test import run_soak_test


@pytest.mark.tc("TC-28")
def test_soak_pipeline_stability_and_memory():
    """Verify that processing 500 multi-scenario frames maintains bounded memory and track state."""
    results = run_soak_test(total_frames=500, fps=150.0)

    assert results["total_frames"] == 500
    assert results["overall_soak_pass"] is True
    assert results["memory_leak_check_pass"] is True
    assert results["track_purging_check_pass"] is True
    assert results["effective_fps"] > 25.0
