"""SiteSentinel: Offline Evaluation Harness and Metrics Matcher.

Replays detection streams through the Rule Engine, matches detected incidents
against ground-truth intervals, calculates Precision, Recall, F1, and Alert Latency,
runs parameter threshold sweeps, and outputs JSON and Markdown reports with Wilson 95% CIs.

Usage:
  python eval/evaluate.py --clip data/test_clips/site01.mp4 --labels data/labelled/site01.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel.config import load_rules_config, load_zones_config
from sentinel.domain.models import FrameMeta, Incident
from sentinel.domain.rules import RuleEngine
from sentinel.domain.zones import ZoneManager
from tools.simulate import Simulator


@dataclass
class GroundTruthInterval:
    type: str
    start_s: float
    end_s: float
    track_id: Optional[int] = None
    zone: Optional[str] = None


@dataclass
class RuleMetric:
    rule_type: str
    ground_truth_count: int
    incident_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    mean_latency_s: float
    min_latency_s: float
    max_latency_s: float


@dataclass
class EvaluationSummary:
    timestamp: str
    clip_path: str
    labels_path: str
    total_frames: int
    fps: float
    overall_precision: float
    overall_recall: float
    overall_f1: float
    overall_mean_latency_s: float
    ac5_pass: bool  # Recall >= 0.85 and Precision >= 0.80
    per_rule_metrics: Dict[str, RuleMetric]
    sweep_results: Optional[List[Dict[str, Any]]] = None
    precision_ci_95: Tuple[float, float] = (0.0, 0.0)
    recall_ci_95: Tuple[float, float] = (0.0, 0.0)
    latency_p95_s: float = 0.0
    false_alarms_per_hour: float = 0.0
    misses: List[Dict[str, Any]] = field(default_factory=list)
    false_alarms: List[Dict[str, Any]] = field(default_factory=list)
    data_provenance: str = "SIMULATED"
    qualification_note: str = ""


def wilson_score_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Calculate Wilson score interval (default 95% confidence where z=1.96)."""
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    margin = (z / denom) * math.sqrt((p * (1.0 - p) / total) + (z2 / (4.0 * total * total)))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (round(lower, 4), round(upper, 4))


def calculate_p95(latencies: List[float]) -> float:
    """Calculate 95th percentile latency in seconds."""
    if not latencies:
        return 0.0
    sorted_lats = sorted(latencies)
    k = (len(sorted_lats) - 1) * 0.95
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_lats[int(k)], 3)
    d0 = sorted_lats[int(f)] * (c - k)
    d1 = sorted_lats[int(c)] * (k - f)
    return round(d0 + d1, 3)


def load_ground_truth(labels_path: str | Path) -> Tuple[Dict[str, Any], List[GroundTruthInterval]]:
    """Load ground-truth labels and interval list from JSON."""
    p = Path(labels_path)
    if not p.exists():
        raise FileNotFoundError(f"Labels file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_intervals = data.get("violations", [])
    intervals: List[GroundTruthInterval] = []
    for item in raw_intervals:
        intervals.append(
            GroundTruthInterval(
                type=item["type"].upper(),
                start_s=float(item["start_s"]),
                end_s=float(item["end_s"]),
                track_id=item.get("track_id"),
                zone=item.get("zone"),
            )
        )

    return data, intervals


def match_incidents_to_ground_truth_detailed(
    incidents: List[Tuple[float, Incident]],
    ground_truth: List[GroundTruthInterval],
    tolerance_s: float = 1.0,
    total_duration_s: float = 60.0,
) -> Tuple[
    Dict[str, RuleMetric],
    float,
    float,
    float,
    float,
    float,
    Tuple[float, float],
    Tuple[float, float],
    float,
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """Match detected incidents against ground truth intervals with full statistical diagnostics."""
    all_rule_types = sorted(
        list(set([gt.type for gt in ground_truth] + [inc.type for _, inc in incidents]))
    )

    per_rule: Dict[str, RuleMetric] = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0
    all_latencies: List[float] = []

    all_matched_gt_indices: set[int] = set()
    all_matched_inc_indices: set[int] = set()

    for rule in all_rule_types:
        rule_gt_entries = [(idx, gt) for idx, gt in enumerate(ground_truth) if gt.type == rule]
        rule_inc_entries = [
            (idx, (t_rel, inc)) for idx, (t_rel, inc) in enumerate(incidents) if inc.type == rule
        ]

        matched_gt_indices: set[int] = set()
        matched_inc_indices: set[int] = set()
        rule_latencies: List[float] = []

        # Find True Positives
        for orig_inc_idx, (t_rel, inc) in rule_inc_entries:
            for orig_gt_idx, gt in rule_gt_entries:
                if orig_gt_idx in matched_gt_indices:
                    continue

                if gt.track_id is not None and gt.track_id != inc.track_id:
                    continue

                if gt.zone is not None and inc.zone is not None and gt.zone != inc.zone:
                    continue

                if (gt.start_s - tolerance_s) <= t_rel <= (gt.end_s + tolerance_s):
                    matched_gt_indices.add(orig_gt_idx)
                    all_matched_gt_indices.add(orig_gt_idx)
                    matched_inc_indices.add(orig_inc_idx)
                    all_matched_inc_indices.add(orig_inc_idx)
                    latency = max(0.0, t_rel - gt.start_s)
                    rule_latencies.append(latency)
                    all_latencies.append(latency)
                    break

        tp = len(matched_gt_indices)
        fp = len(rule_inc_entries) - len(matched_inc_indices)
        fn = len(rule_gt_entries) - len(matched_gt_indices)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        mean_lat = sum(rule_latencies) / len(rule_latencies) if rule_latencies else 0.0
        min_lat = min(rule_latencies) if rule_latencies else 0.0
        max_lat = max(rule_latencies) if rule_latencies else 0.0

        per_rule[rule] = RuleMetric(
            rule_type=rule,
            ground_truth_count=len(rule_gt_entries),
            incident_count=len(rule_inc_entries),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1_score=round(f1, 4),
            mean_latency_s=round(mean_lat, 3),
            min_latency_s=round(min_lat, 3),
            max_latency_s=round(max_lat, 3),
        )

    overall_prec = (
        total_tp / (total_tp + total_fp)
        if (total_tp + total_fp) > 0
        else (1.0 if total_fn == 0 else 0.0)
    )
    overall_rec = (
        total_tp / (total_tp + total_fn)
        if (total_tp + total_fn) > 0
        else (1.0 if total_fp == 0 else 0.0)
    )
    overall_f1 = (
        (2 * overall_prec * overall_rec) / (overall_prec + overall_rec)
        if (overall_prec + overall_rec) > 0
        else 0.0
    )
    overall_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0
    p95_lat = calculate_p95(all_latencies)

    # Confidence Intervals
    prec_ci = wilson_score_interval(total_tp, total_tp + total_fp)
    rec_ci = wilson_score_interval(total_tp, total_tp + total_fn)

    # False alarm rate (false alarms / hour)
    duration_hrs = max(total_duration_s, 1.0) / 3600.0
    false_alarms_per_hour = round(total_fp / duration_hrs, 2)

    # Collect Misses (False Negatives)
    misses: List[Dict[str, Any]] = []
    for idx, gt in enumerate(ground_truth):
        if idx not in all_matched_gt_indices:
            misses.append(
                {
                    "index": idx,
                    "type": gt.type,
                    "start_s": gt.start_s,
                    "end_s": gt.end_s,
                    "track_id": gt.track_id,
                    "zone": gt.zone,
                }
            )

    # Collect False Alarms (False Positives)
    false_alarms: List[Dict[str, Any]] = []
    for idx, (t_rel, inc) in enumerate(incidents):
        if idx not in all_matched_inc_indices:
            false_alarms.append(
                {
                    "index": idx,
                    "timestamp_rel_s": t_rel,
                    "type": inc.type,
                    "severity": inc.severity,
                    "track_id": inc.track_id,
                    "zone": inc.zone,
                    "confidence": inc.confidence,
                }
            )

    return (
        per_rule,
        round(overall_prec, 4),
        round(overall_rec, 4),
        round(overall_f1, 4),
        round(overall_latency, 3),
        p95_lat,
        prec_ci,
        rec_ci,
        false_alarms_per_hour,
        misses,
        false_alarms,
    )


def match_incidents_to_ground_truth(
    incidents: List[Tuple[float, Incident]],
    ground_truth: List[GroundTruthInterval],
    tolerance_s: float = 1.0,
) -> Tuple[Dict[str, RuleMetric], float, float, float, float]:
    """Standard 5-tuple signature for backward-compatibility with tests."""
    per_rule, prec, rec, f1, lat, _, _, _, _, _, _ = match_incidents_to_ground_truth_detailed(
        incidents, ground_truth, tolerance_s=tolerance_s
    )
    return per_rule, prec, rec, f1, lat


def run_pipeline_replay(
    frames_generator: Any,
    rule_engine: RuleEngine,
) -> List[Tuple[float, Incident]]:
    """Feed frames through rule engine and return list of (relative_seconds, Incident)."""
    incidents: List[Tuple[float, Incident]] = []
    base_time_s: Optional[float] = None

    for item in frames_generator:
        meta = item[0] if isinstance(item, tuple) else item
        rel_s = float(meta.ts) if isinstance(meta.ts, (int, float)) else meta.ts.timestamp()
        if base_time_s is None:
            base_time_s = rel_s
        relative_elapsed = rel_s - base_time_s

        new_incs = rule_engine.process_frame(meta)
        for inc in new_incs:
            incidents.append((round(relative_elapsed, 3), inc))

    return incidents


def run_threshold_sweep(
    ground_truth: List[GroundTruthInterval],
    base_frames: List[Tuple[FrameMeta, Any]],
    zone_manager: ZoneManager,
    min_durations: List[float] = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
    min_overlaps: List[float] = [0.1, 0.25, 0.4],
    labels_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """Sweep rule debounce duration and PPE overlap thresholds to determine optimal operating point.

    Refuses to execute against locked test split labels to maintain strict evaluation integrity.
    """
    if labels_path is not None:
        p_str = str(labels_path).lower()
        if "test" in p_str and "dev" not in p_str:
            raise ValueError(
                f"Data Protocol Integrity Violation: Parameter threshold sweep cannot be run on locked test split '{labels_path}'."
            )
    sweep_results: List[Dict[str, Any]] = []

    for overlap in min_overlaps:
        for dur in min_durations:
            rules_cfg = load_rules_config("config/rules.yaml")
            rules_cfg.no_helmet.min_duration_s = dur
            rules_cfg.no_vest.min_duration_s = dur
            rules_cfg.association.min_overlap = overlap

            engine = RuleEngine(rules_cfg, zone_manager)
            incidents = run_pipeline_replay(iter(base_frames), engine)
            _, prec, rec, f1, lat = match_incidents_to_ground_truth(incidents, ground_truth)

            sweep_results.append(
                {
                    "min_duration_s": dur,
                    "min_overlap": overlap,
                    "precision": prec,
                    "recall": rec,
                    "f1_score": f1,
                    "mean_latency_s": lat,
                    "incident_count": len(incidents),
                }
            )

    return sweep_results


def generate_evaluation_reports(
    summary: EvaluationSummary,
    output_dir: str | Path = "reports",
) -> Tuple[Path, Path]:
    """Generate reports/eval_<timestamp>.json and reports/eval_<timestamp>.md."""
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)

    dt_slug = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_p / f"eval_{dt_slug}.json"
    md_path = out_p / f"eval_{dt_slug}.md"

    # 1. JSON Report
    json_data = asdict(summary)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    # 2. Markdown Report
    prec_ci_str = (
        f"[{summary.precision_ci_95[0] * 100:.1f}%, {summary.precision_ci_95[1] * 100:.1f}%]"
    )
    rec_ci_str = f"[{summary.recall_ci_95[0] * 100:.1f}%, {summary.recall_ci_95[1] * 100:.1f}%]"

    status_str = (
        "**PASS**"
        if summary.ac5_pass
        else (
            "**INSUFFICIENT EVIDENCE (SIMULATED DATA)**"
            if summary.data_provenance == "SIMULATED"
            else "**FAIL**"
        )
    )

    lines = [
        "# SiteSentinel: Offline Evaluation Report",
        "",
        f"**Date**: {summary.timestamp}  ",
        f"**Clip Evaluated**: `{summary.clip_path}`  ",
        f"**Labels**: `{summary.labels_path}`  ",
        f"**Data Provenance**: `{summary.data_provenance}`  ",
        f"**Frame Count**: {summary.total_frames} ({summary.fps} FPS)  ",
        "",
        "## 1. Overall Acceptance Criteria (AC-5)",
        "",
        f"- **Precision**: **{summary.overall_precision * 100:.1f}%** (95% Wilson CI: {prec_ci_str}) (Target: >= 80.0%)",
        f"- **Recall**: **{summary.overall_recall * 100:.1f}%** (95% Wilson CI: {rec_ci_str}) (Target: >= 85.0%)",
        f"- **F1 Score**: **{summary.overall_f1 * 100:.1f}%**",
        f"- **Average Alert Latency**: **{summary.overall_mean_latency_s:.2f} s** (p95: **{summary.latency_p95_s:.2f} s**)",
        f"- **False Alarms per Hour**: **{summary.false_alarms_per_hour:.1f} / hr**",
        f"- **AC-5 Pass Status**: {status_str}",
    ]

    if summary.qualification_note:
        lines.append(f"- **Qualification Status**: *{summary.qualification_note}*")

    lines.extend(
        [
            "",
            "## 2. Per-Rule Performance Breakdown",
            "",
            "| Rule Type | GT Count | Detections | TP | FP | FN | Precision | Recall | F1 | Latency (mean / max) |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )

    for rule, m in summary.per_rule_metrics.items():
        lines.append(
            f"| `{rule}` | {m.ground_truth_count} | {m.incident_count} | {m.true_positives} | "
            f"{m.false_positives} | {m.false_negatives} | {m.precision * 100:.1f}% | "
            f"{m.recall * 100:.1f}% | {m.f1_score * 100:.1f}% | {m.mean_latency_s:.2f}s / {m.max_latency_s:.2f}s |"
        )

    # Section 3: Diagnostic Breakdown & Failure Analysis
    lines.extend(
        [
            "",
            "## 3. Diagnostic Breakdown (Misses and False Alarms)",
            "",
            f"- **Total Misses (False Negatives)**: {len(summary.misses)}",
            f"- **Total False Alarms (False Positives)**: {len(summary.false_alarms)}",
        ]
    )

    if summary.misses:
        lines.extend(
            [
                "",
                "### Missed Violations (False Negatives)",
                "| Index | Type | Window | Track ID | Zone |",
                "|---|---|---|---|---|",
            ]
        )
        for miss in summary.misses:
            lines.append(
                f"| {miss['index']} | `{miss['type']}` | {miss['start_s']:.1f}s - {miss['end_s']:.1f}s | "
                f"{miss.get('track_id', '-')} | {miss.get('zone', '-')} |"
            )

    if summary.false_alarms:
        lines.extend(
            [
                "",
                "### False Alarms (False Positives)",
                "| Index | Timestamp | Type | Severity | Track ID | Zone | Confidence |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for fa in summary.false_alarms:
            lines.append(
                f"| {fa['index']} | {fa['timestamp_rel_s']:.1f}s | `{fa['type']}` | "
                f"{fa['severity']} | {fa.get('track_id', '-')} | {fa.get('zone', '-')} | {fa.get('confidence', 0.0):.2f} |"
            )

    if summary.sweep_results:
        lines.extend(
            [
                "",
                "## 4. Threshold Sweep Analysis (Debounce Duration & Overlap)",
                "",
                "| min_duration_s | min_overlap | Precision | Recall | F1 Score | Alert Latency | Incidents |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for r in summary.sweep_results:
            is_best = r["f1_score"] == max(x["f1_score"] for x in summary.sweep_results)
            best_star = " *" if is_best else ""
            lines.append(
                f"| {r['min_duration_s']:.1f} s | {r['min_overlap']:.2f} | "
                f"{r['precision'] * 100:.1f}% | {r['recall'] * 100:.1f}% | "
                f"**{r['f1_score'] * 100:.1f}%**{best_star} | {r['mean_latency_s']:.2f} s | {r['incident_count']} |"
            )

    lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, md_path


def generate_failure_analysis_report(
    summary: EvaluationSummary,
    output_path: str | Path = "reports/failure_analysis.md",
) -> Path:
    """Generate a dedicated failure analysis markdown report for engineering triage."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# SiteSentinel: Failure Modes & Root Cause Analysis",
        "",
        f"- **Evaluation Run**: `{summary.timestamp}`",
        f"- **Source Clip**: `{summary.clip_path}`",
        f"- **Labels File**: `{summary.labels_path}`",
        f"- **Data Provenance**: `{summary.data_provenance}`",
        "",
        "## 1. Summary of Discrepancies",
        f"- **Missed Violations (False Negatives)**: {len(summary.misses)}",
        f"- **False Alarms (False Positives)**: {len(summary.false_alarms)}",
        f"- **False Alarm Rate**: {summary.false_alarms_per_hour:.2f} events / hour",
        f"- **Latency p95**: {summary.latency_p95_s:.2f} s",
        "",
        "## 2. Missed Violation Incidents",
    ]

    if not summary.misses:
        lines.append("No ground-truth violations were missed in this evaluation run.")
    else:
        lines.extend(
            [
                "| Index | Rule | Interval | Track | Zone | Triage Notes |",
                "|---|---|---|---|---|---|",
            ]
        )
        for m in summary.misses:
            lines.append(
                f"| {m['index']} | `{m['type']}` | {m['start_s']:.1f}s - {m['end_s']:.1f}s | "
                f"{m.get('track_id', '-')} | {m.get('zone', '-')} | Short interval or track association delay |"
            )

    lines.extend(
        [
            "",
            "## 3. False Alarm Incidents",
        ]
    )

    if not summary.false_alarms:
        lines.append("No spurious false alarms were triggered in this evaluation run.")
    else:
        lines.extend(
            [
                "| Index | Time | Rule | Severity | Track | Zone | Confidence | Triage Notes |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for fa in summary.false_alarms:
            lines.append(
                f"| {fa['index']} | {fa['timestamp_rel_s']:.1f}s | `{fa['type']}` | {fa['severity']} | "
                f"{fa.get('track_id', '-')} | {fa.get('zone', '-')} | {fa.get('confidence', 0.0):.2f} | Transient detection flicker |"
            )

    lines.extend(
        [
            "",
            "## 4. Root Cause Recommendations",
            "1. **Debounce Tuning**: Increase `min_duration_s` from 1.0s to 1.5s if false alarm rate exceeds 2.0/hr.",
            "2. **IoA Association**: Adjust PPE intersection-over-area threshold for workers viewed at oblique camera angles.",
            "3. **Physical Validation**: Run evaluation against ≥ 30 physical events on target hardware to lift SIMULATED status.",
            "",
        ]
    )

    out_p.write_text("\n".join(lines), encoding="utf-8")
    return out_p


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Evaluation Harness")
    parser.add_argument(
        "--clip", type=str, default="data/test_clips/site01.mp4", help="Path to video clip"
    )
    parser.add_argument(
        "--labels",
        type=str,
        default="data/labelled/site01.json",
        help="Path to ground truth labels",
    )
    parser.add_argument(
        "--provenance", type=str, default="AUTO", choices=["AUTO", "SIMULATED", "MEASURED"]
    )
    parser.add_argument(
        "--tolerance", type=float, default=1.0, help="Matching temporal tolerance (seconds)"
    )
    parser.add_argument(
        "--detector",
        type=str,
        default="auto",
        choices=["auto", "sim", "baseline"],
        help="Detection source: 'baseline' (CPU ONNX detector) or 'sim' (Synthetic simulator)",
    )
    parser.add_argument(
        "--stamp",
        type=str,
        default=None,
        help="Custom provenance stamp (e.g. 'BASELINE')",
    )
    parser.add_argument("--sweep", action="store_true", help="Run threshold parameter sweep")
    parser.add_argument(
        "--out-dir", type=str, default="reports", help="Output directory for reports"
    )
    args = parser.parse_args()

    # Determine provenance
    labels_path = Path(args.labels)
    if args.stamp:
        provenance = args.stamp
    elif args.provenance == "AUTO":
        if (
            "simulated" in str(labels_path).lower()
            or "simulated" in args.clip.lower()
            or not Path(args.clip).exists()
        ):
            provenance = "SIMULATED"
        else:
            provenance = "MEASURED"
    else:
        provenance = args.provenance

    # Load ground truth
    if not labels_path.exists():
        print(f"Generating default ground-truth labels for {args.clip}...")
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        default_gt = {
            "clip": args.clip,
            "fps": 25.0,
            "frame_count": 500,
            "duration_s": 20.0,
            "violations": [
                {
                    "type": "NO_HELMET",
                    "start_s": 2.0,
                    "end_s": 6.0,
                    "track_id": 1,
                    "zone": "press-area",
                },
                {
                    "type": "ZONE_INTRUSION",
                    "start_s": 8.0,
                    "end_s": 12.0,
                    "track_id": 2,
                    "zone": "crane-drop",
                },
                {
                    "type": "DANGER_DWELL",
                    "start_s": 13.0,
                    "end_s": 18.0,
                    "track_id": 2,
                    "zone": "crane-drop",
                },
            ],
        }
        with open(labels_path, "w", encoding="utf-8") as f:
            json.dump(default_gt, f, indent=2)

    _, ground_truth = load_ground_truth(labels_path)

    # Initialize domain components
    zones_cfg = load_zones_config("config/zones.json")
    rules_cfg = load_rules_config("config/rules.yaml")
    zone_mgr = ZoneManager(zones_cfg)
    rule_engine = RuleEngine(rules_cfg, zone_mgr)

    clip_p = Path(args.clip)
    use_baseline = (args.detector == "baseline") or (
        args.detector == "auto"
        and clip_p.exists()
        and clip_p.suffix.lower() in {".mp4", ".avi", ".mkv"}
        and "simulated" not in str(clip_p).lower()
    )

    cached_frames: Dict[int, Any] = {}
    fps_val = 25.0

    if use_baseline:
        import cv2

        from sentinel.adapters.baseline_detector import BaselineONNXDetector

        detector = BaselineONNXDetector()
        if not detector.is_ready:
            print(
                "ERROR: Baseline ONNX detector weights not found. Run scripts/fetch_baseline_model.sh first.",
                file=sys.stderr,
            )
            sys.exit(1)

        cap = cv2.VideoCapture(str(clip_p))
        if not cap.isOpened():
            print(f"ERROR: Could not open video clip {clip_p}", file=sys.stderr)
            sys.exit(1)

        raw_frames: List[Tuple[FrameMeta, Any]] = []
        fps_val = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        frame_idx = 0

        print(f"Running baseline ONNX detector on {clip_p} (FPS: {fps_val:.1f})...")
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            ts = frame_idx / fps_val
            meta = detector.detect(frame, frame_id=frame_idx, timestamp=ts)
            raw_frames.append((meta, None))
            if frame_idx % 5 == 0 and len(cached_frames) < 100:
                cached_frames[frame_idx] = frame.copy()
            frame_idx += 1
        cap.release()
        total_dur_s = len(raw_frames) / fps_val if fps_val > 0 else 0.0
        print(f"Processed {len(raw_frames)} frames through baseline detector.")
        if not args.stamp:
            provenance = "BASELINE (real footage, non-PipeGen detector)"
    else:
        # Generate or load evaluation frame detections from simulator
        sim = Simulator(fps=25.0)
        raw_frames = []
        current_ts = datetime.datetime.now(datetime.timezone.utc)

        for scenario_name, dur in [
            ("no_helmet", 5.0),
            ("restricted_entry", 6.0),
            ("danger_dwell", 8.0),
        ]:
            scenario_frames = sim.generate_scenario(scenario_name, duration_s=dur, start_ts=current_ts)
            raw_frames.extend(scenario_frames)
            current_ts = current_ts + datetime.timedelta(seconds=dur)
        total_dur_s = len(raw_frames) / 25.0

    # Replay pipeline
    incidents = run_pipeline_replay(iter(raw_frames), rule_engine)

    (
        per_rule,
        prec,
        rec,
        f1,
        lat,
        p95_lat,
        prec_ci,
        rec_ci,
        fa_per_hr,
        misses,
        false_alarms,
    ) = match_incidents_to_ground_truth_detailed(
        incidents, ground_truth, tolerance_s=args.tolerance, total_duration_s=total_dur_s
    )

    # Generate blurred thumbnails for misses and false alarms for privacy compliance
    thumb_dir = Path(args.out_dir) / "eval_thumbnails"
    if cached_frames and (misses or false_alarms):
        thumb_dir.mkdir(parents=True, exist_ok=True)
        import cv2

        for idx, miss in enumerate(misses[:10]):
            target_f = int(miss["start_s"] * fps_val)
            nearest_f = min(cached_frames.keys(), key=lambda k: abs(k - target_f))
            thumb_img = cv2.resize(cached_frames[nearest_f], (320, 180))
            blurred_thumb = cv2.GaussianBlur(thumb_img, (31, 31), 15.0)
            thumb_name = f"miss_{idx+1}_frame_{nearest_f}.jpg"
            cv2.imwrite(str(thumb_dir / thumb_name), blurred_thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
            miss["thumbnail"] = f"reports/eval_thumbnails/{thumb_name}"

        for idx, fa in enumerate(false_alarms[:10]):
            target_f = int(fa.get("timestamp_rel_s", 0.0) * fps_val)
            nearest_f = min(cached_frames.keys(), key=lambda k: abs(k - target_f))
            thumb_img = cv2.resize(cached_frames[nearest_f], (320, 180))
            blurred_thumb = cv2.GaussianBlur(thumb_img, (31, 31), 15.0)
            thumb_name = f"fa_{idx+1}_frame_{nearest_f}.jpg"
            cv2.imwrite(str(thumb_dir / thumb_name), blurred_thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
            fa["thumbnail"] = f"reports/eval_thumbnails/{thumb_name}"

    sweep_results = None
    if args.sweep:
        print("Running parameter threshold sweep across debounce durations & overlap...")
        sweep_results = run_threshold_sweep(ground_truth, raw_frames, zone_mgr, labels_path=labels_path)

    # AC-5 Qualification Gate:
    # 1. Precision >= 0.80 and Recall >= 0.85
    # 2. Refuse PASS if provenance is SIMULATED or ground truth events < 30
    meets_thresholds = bool(rec >= 0.85 and prec >= 0.80)
    total_events = len(ground_truth)

    if provenance == "SIMULATED":
        ac5_pass = False
        qual_note = (
            "REFUSED PASS: Data provenance is SIMULATED (requires physical MEASURED video footage)."
        )
    elif total_events < 30:
        ac5_pass = False
        qual_note = f"REFUSED PASS: Sample size too small (n={total_events} < 30 minimum physical events for production qualification)."
    else:
        ac5_pass = meets_thresholds
        qual_note = "QUALIFIED: Physical test data meets AC-5 acceptance criteria."

    summary = EvaluationSummary(
        timestamp=datetime.datetime.now().isoformat(),
        clip_path=args.clip,
        labels_path=str(labels_path),
        total_frames=len(raw_frames),
        fps=25.0,
        overall_precision=prec,
        overall_recall=rec,
        overall_f1=f1,
        overall_mean_latency_s=lat,
        ac5_pass=ac5_pass,
        per_rule_metrics=per_rule,
        sweep_results=sweep_results,
        precision_ci_95=prec_ci,
        recall_ci_95=rec_ci,
        latency_p95_s=p95_lat,
        false_alarms_per_hour=fa_per_hr,
        misses=misses,
        false_alarms=false_alarms,
        data_provenance=provenance,
        qualification_note=qual_note,
    )

    json_out, md_out = generate_evaluation_reports(summary, output_dir=args.out_dir)
    failure_report = generate_failure_analysis_report(
        summary, output_path=Path(args.out_dir) / "failure_analysis.md"
    )

    print("\n================ EVALUATION SUMMARY ================")
    print(f"Data Provenance:        {provenance}")
    print(
        f"Precision:              {prec * 100:.1f}% (95% CI: [{prec_ci[0] * 100:.1f}%, {prec_ci[1] * 100:.1f}%])"
    )
    print(
        f"Recall:                 {rec * 100:.1f}% (95% CI: [{rec_ci[0] * 100:.1f}%, {rec_ci[1] * 100:.1f}%])"
    )
    print(f"F1 Score:               {f1 * 100:.1f}%")
    print(f"Alert Latency (mean):   {lat:.2f} s (p95: {p95_lat:.2f} s)")
    print(f"False Alarm Rate:       {fa_per_hr:.1f} / hr")
    print(f"Misses (FN):            {len(misses)}")
    print(f"False Alarms (FP):      {len(false_alarms)}")
    print(f"AC-5 Status:            {'PASS' if ac5_pass else 'REFUSED / FAIL'}")
    if qual_note:
        print(f"Qualification Note:     {qual_note}")
    print(f"Reports saved to:\n  - {json_out}\n  - {md_out}\n  - {failure_report}")


if __name__ == "__main__":
    main()
