import json
from pathlib import Path

from eval.evaluate import (
    EvaluationSummary,
    GroundTruthInterval,
    generate_evaluation_reports,
    match_incidents_to_ground_truth,
    run_threshold_sweep,
)
from sentinel.config import load_zones_config
from sentinel.models import Incident
from sentinel.zones import ZoneManager
from tools.label_clip import inspect_clip, parse_interval_spec, save_labels
from tools.simulate import Simulator


def test_label_clip_parse_spec_valid():
    spec = "NO_HELMET:2.5:6.0:1:press-area"
    parsed = parse_interval_spec(spec)
    assert parsed["type"] == "NO_HELMET"
    assert parsed["start_s"] == 2.5
    assert parsed["end_s"] == 6.0
    assert parsed["track_id"] == 1
    assert parsed["zone"] == "press-area"


def test_label_clip_save_and_inspect(tmp_path: Path):
    labels_path = tmp_path / "test_labels.json"
    clip_info = inspect_clip("nonexistent_test.mp4")
    assert clip_info["fps"] == 25.0

    violations = [
        {"type": "NO_HELMET", "start_s": 2.0, "end_s": 5.0, "track_id": 1},
        {"type": "ZONE_INTRUSION", "start_s": 8.0, "end_s": 12.0, "zone": "crane-drop"},
    ]
    saved = save_labels(labels_path, clip_info, violations)
    assert saved.exists()

    with open(saved, "r") as f:
        data = json.load(f)
    assert len(data["violations"]) == 2
    assert data["violations"][0]["type"] == "NO_HELMET"


def test_match_incidents_to_ground_truth_metrics():
    # Ground truth: 2 incidents
    ground_truth = [
        GroundTruthInterval(type="NO_HELMET", start_s=2.0, end_s=6.0, track_id=1),
        GroundTruthInterval(type="ZONE_INTRUSION", start_s=8.0, end_s=12.0, track_id=2),
    ]

    # Detected incidents:
    # 1. Matching NO_HELMET at t=3.0 (latency = 1.0s) -> TP
    # 2. Matching ZONE_INTRUSION at t=8.5 (latency = 0.5s) -> TP
    # 3. False Positive at t=15.0 -> FP
    inc1 = Incident(
        incident_id="inc-1",
        timestamp="2026-10-17T12:00:03Z",
        camera_id="cam-01",
        type="NO_HELMET",
        severity="HIGH",
        track_id=1,
        zone="press-area",
        confidence=0.9,
        duration_s=1.0,
    )
    inc2 = Incident(
        incident_id="inc-2",
        timestamp="2026-10-17T12:00:08.5Z",
        camera_id="cam-01",
        type="ZONE_INTRUSION",
        severity="HIGH",
        track_id=2,
        zone="crane-drop",
        confidence=0.95,
        duration_s=0.5,
    )
    inc_fp = Incident(
        incident_id="inc-fp",
        timestamp="2026-10-17T12:00:15Z",
        camera_id="cam-01",
        type="NO_HELMET",
        severity="HIGH",
        track_id=99,
        zone="press-area",
        confidence=0.8,
        duration_s=2.0,
    )

    detected = [
        (3.0, inc1),
        (8.5, inc2),
        (15.0, inc_fp),
    ]

    per_rule, prec, rec, f1, lat = match_incidents_to_ground_truth(detected, ground_truth)

    # Total: TP = 2, FP = 1, FN = 0
    # Precision = 2 / 3 = 0.6667
    # Recall = 2 / 2 = 1.0
    assert prec == 0.6667
    assert rec == 1.0
    assert f1 > 0.79
    assert lat == round((1.0 + 0.5) / 2.0, 3)

    assert "NO_HELMET" in per_rule
    assert per_rule["NO_HELMET"].true_positives == 1
    assert per_rule["NO_HELMET"].false_positives == 1
    assert per_rule["ZONE_INTRUSION"].true_positives == 1
    assert per_rule["ZONE_INTRUSION"].false_positives == 0


def test_evaluation_report_generation(tmp_path: Path):
    summary = EvaluationSummary(
        timestamp="2026-10-17T12:00:00Z",
        clip_path="data/test_clips/site01.mp4",
        labels_path="data/labelled/site01.json",
        total_frames=500,
        fps=25.0,
        overall_precision=0.92,
        overall_recall=0.88,
        overall_f1=0.90,
        overall_mean_latency_s=1.2,
        ac5_pass=True,
        per_rule_metrics={},
        sweep_results=[
            {
                "min_duration_s": 2.0,
                "min_overlap": 0.25,
                "precision": 0.92,
                "recall": 0.88,
                "f1_score": 0.90,
                "mean_latency_s": 1.2,
                "incident_count": 2,
            }
        ],
    )

    json_p, md_p = generate_evaluation_reports(summary, output_dir=tmp_path)
    assert json_p.exists()
    assert md_p.exists()

    with open(json_p, "r") as f:
        data = json.load(f)
    assert data["ac5_pass"] is True
    assert data["overall_precision"] == 0.92

    with open(md_p, "r") as f:
        md_text = f.read()
    assert "- **AC-5 Pass Status**: ✅ **PASS**" in md_text
    assert "Threshold Sweep Analysis" in md_text


def test_run_threshold_sweep_and_replay():
    sim = Simulator(fps=25.0)
    frames = sim.generate_scenario("no_helmet", duration_s=4.0)
    zones_cfg = load_zones_config("config/zones.json")
    zone_mgr = ZoneManager(zones_cfg)

    gt = [GroundTruthInterval(type="NO_HELMET", start_s=1.0, end_s=3.5, track_id=1)]

    results = run_threshold_sweep(
        gt,
        frames,
        zone_mgr,
        min_durations=[1.0, 2.0],
        min_overlaps=[0.25],
    )

    assert len(results) == 2
    for r in results:
        assert "precision" in r
        assert "recall" in r
        assert "f1_score" in r
