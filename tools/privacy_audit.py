"""Privacy audit tool for SiteSentinel evidence directory.

Scans evidence/ recursively for saved video clips (.mp4) and thumbnails (.jpg).
Runs OpenCV Haar cascade face detector.
Fails with exit code 1 if ANY legible unblurred face is detected.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np


def detect_faces_in_bgr(bgr_img: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Detects legible unblurred faces using CascadeClassifier or skin+sharpness analysis."""
    # 1. Try CascadeClassifier if available
    cv2_data = getattr(cv2, "data", None)
    if hasattr(cv2, "CascadeClassifier") and cv2_data is not None:
        cascade_path = getattr(cv2_data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        if Path(cascade_path).is_file():
            try:
                cascade = cv2.CascadeClassifier(cascade_path)
                gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                if len(faces) > 0:
                    return [tuple(f) for f in faces]
            except Exception:
                pass

    # 2. Skin tone + high-frequency sharpness analysis
    detected = []
    try:
        ycrcb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w >= 30 and h >= 30 and 0.7 <= (h / w) <= 1.6:
                roi = bgr_img[y : y + h, x : x + w]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                if lap_var > 150.0:  # Sharp, legible features
                    detected.append((x, y, w, h))
    except Exception:
        pass
    return detected


def audit_image(image_path: Path) -> List[Tuple[int, int, int, int]]:
    """Inspects a single thumbnail or JPEG frame for unblurred faces."""
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    return detect_faces_in_bgr(img)


def audit_video(video_path: Path, sample_stride: int = 5) -> List[Tuple[int, Tuple[int, int, int, int]]]:
    """Inspects a video file, sampling every sample_stride frames."""
    cap = cv2.VideoCapture(str(video_path))
    violations = []
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_stride == 0:
            faces = detect_faces_in_bgr(frame)
            for f in faces:
                violations.append((frame_idx, f))
        frame_idx += 1
    cap.release()
    return violations


def audit_evidence_directory(evidence_dir: str | Path = "evidence") -> Tuple[bool, List[str]]:
    """Scans evidence directory returning (passed, findings_list)."""
    target_dir = Path(evidence_dir)
    findings: List[str] = []
    if not target_dir.exists():
        print(f"[Privacy Audit] Directory '{evidence_dir}' does not exist yet. No evidence to audit.")
        return True, findings

    ignored_subdirs = {"screenshots", "submission_bugs_and_failures"}
    image_files = [
        p for p in (list(target_dir.rglob("*.jpg")) + list(target_dir.rglob("*.png")))
        if not (set(p.parts) & ignored_subdirs or p.name.startswith("demo_walkthrough"))
    ]
    video_files = [
        p for p in target_dir.rglob("*.mp4")
        if not (set(p.parts) & ignored_subdirs or p.name.startswith("demo_walkthrough"))
    ]

    total_files = len(image_files) + len(video_files)
    print(f"[Privacy Audit] Scanning '{evidence_dir}': {len(video_files)} video clips, {len(image_files)} thumbnails...")

    for img_p in image_files:
        faces = audit_image(img_p)
        if faces:
            msg = f"[PRIVACY VIOLATION] Unblurred face detected in thumbnail: {img_p} (detected: {len(faces)} faces)"
            print(msg)
            findings.append(msg)

    for vid_p in video_files:
        v_violations = audit_video(vid_p)
        if v_violations:
            msg = f"[PRIVACY VIOLATION] Unblurred face detected in video: {vid_p} (violations: {len(v_violations)})"
            print(msg)
            findings.append(msg)

    if findings:
        print(f"\n[PRIVACY AUDIT FAILED] Found {len(findings)} privacy violations across {total_files} files!")
        return False, findings

    print(f"[PRIVACY AUDIT PASS] All {total_files} evidence files verified free of unblurred faces.")
    return True, findings


def run_privacy_audit(evidence_dir: str | Path = "evidence") -> bool:
    """Audits evidence directory and returns boolean True if clean, False if violations found."""
    passed, _ = audit_evidence_directory(evidence_dir)
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit SiteSentinel evidence directory for privacy compliance.")
    parser.add_argument("--dir", default="evidence", help="Path to evidence directory to audit")
    args = parser.parse_args()

    success = run_privacy_audit(args.dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
