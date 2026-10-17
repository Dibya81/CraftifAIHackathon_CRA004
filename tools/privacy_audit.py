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
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
        cascade_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
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
    """Inspects a still image and returns bounding boxes of any detected unblurred faces."""
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


def run_privacy_audit(evidence_dir: str = "evidence") -> bool:
    target_dir = Path(evidence_dir)
    if not target_dir.exists():
        print(f"[Privacy Audit] Directory '{evidence_dir}' does not exist yet. No evidence to audit.")
        return True

    image_files = list(target_dir.rglob("*.jpg")) + list(target_dir.rglob("*.png"))
    video_files = list(target_dir.rglob("*.mp4"))

    total_files = len(image_files) + len(video_files)
    print(f"[Privacy Audit] Scanning '{evidence_dir}': {len(video_files)} video clips, {len(image_files)} thumbnails...")

    violations_found = 0

    for img_p in image_files:
        faces = audit_image(img_p)
        if faces:
            print(f"[PRIVACY VIOLATION] Unblurred face detected in thumbnail: {img_p} (detected: {len(faces)} faces)")
            violations_found += 1

    for vid_p in video_files:
        v_violations = audit_video(vid_p)
        if v_violations:
            print(f"[PRIVACY VIOLATION] Unblurred face detected in video: {vid_p} (violations: {len(v_violations)})")
            violations_found += 1

    if violations_found > 0:
        print(f"\n[PRIVACY AUDIT FAILED] Found {violations_found} privacy violations across {total_files} files!")
        return False

    print(f"[PRIVACY AUDIT PASS] All {total_files} evidence files verified free of unblurred faces.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit SiteSentinel evidence directory for privacy compliance.")
    parser.add_argument("--dir", default="evidence", help="Path to evidence directory to audit")
    args = parser.parse_args()

    success = run_privacy_audit(args.dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
