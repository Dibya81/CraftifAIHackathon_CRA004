"""Adapter converting PipeGen's detection payloads to canonical FrameMeta objects.

Provides:
- PipeGenAdapter: parses JSON payloads (from MQTT or files) into FrameMeta using
  configurable class mappings.
- JsonFileMetadataTailer: tails an append-only JSONL file or directory of JSON frame metadata.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from sentinel.models import Box, Detection, FrameDimensions, FrameMeta


class PipeGenAdapter:
    """Parses raw PipeGen detection messages into internal FrameMeta structures."""

    DEFAULT_CLASS_MAP: Dict[str, str] = {
        "person": "person",
        "0": "person",
        "helmet": "helmet",
        "hard_hat": "helmet",
        "1": "helmet",
        "no_helmet": "no_helmet",
        "head": "no_helmet",
        "2": "no_helmet",
        "vest": "vest",
        "safety_vest": "vest",
        "high_vis_vest": "vest",
        "3": "vest",
    }

    def __init__(
        self,
        class_map: Optional[Dict[str, str]] = None,
        default_camera_id: str = "cam-01",
    ) -> None:
        self.class_map: Dict[str, str] = {**self.DEFAULT_CLASS_MAP, **(class_map or {})}
        self.default_camera_id: str = default_camera_id

    def map_class_name(self, raw_class: Union[str, int]) -> str:
        """Map raw detector class string or integer ID to canonical class name."""
        key = str(raw_class).strip().lower()
        return self.class_map.get(key, key)

    def parse_payload(self, payload: Union[str, bytes, Dict[str, Any]]) -> FrameMeta:
        """Convert a raw JSON string, bytes, or parsed dict into a FrameMeta object."""
        if isinstance(payload, (str, bytes)):
            data = json.loads(payload)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise TypeError(f"Expected str, bytes, or dict, got {type(payload).__name__}")

        # Extract frame identification and timing
        camera_id = str(data.get("camera_id") or self.default_camera_id)
        frame_id = int(data.get("frame_id", 0))
        ts_val = data.get("ts")
        if ts_val is None:
            ts_val = data.get("timestamp")
        if ts_val is None:
            ts = time.time()
        elif isinstance(ts_val, (int, float)):
            ts = float(ts_val)
        else:
            try:
                ts = float(ts_val)
            except ValueError:
                import datetime

                ts = datetime.datetime.fromisoformat(str(ts_val)).timestamp()

        # Frame resolution
        frame_dims: Optional[FrameDimensions] = None
        frame_dict = data.get("frame")
        if frame_dict and isinstance(frame_dict, dict):
            w = frame_dict.get("width")
            h = frame_dict.get("height")
            if w and h:
                frame_dims = FrameDimensions(width=int(w), height=int(h))

        # Detections / objects list
        raw_objects = data.get("objects")
        if raw_objects is None:
            raw_objects = data.get("detections", [])

        detections: List[Detection] = []
        for obj in raw_objects:
            if not isinstance(obj, dict):
                continue

            raw_cls = None
            for key in ("class", "label", "class_id"):
                if key in obj and obj[key] is not None:
                    raw_cls = obj[key]
                    break
            if raw_cls is None:
                raw_cls = "unknown"
            canonical_cls = self.map_class_name(raw_cls)

            raw_conf = obj.get("conf")
            if raw_conf is None:
                raw_conf = obj.get("confidence", 0.8)
            conf = float(raw_conf) if raw_conf is not None else 0.8
            raw_track_id = obj.get("track_id")
            track_id = int(raw_track_id) if raw_track_id is not None else None

            # Bounding box parsing: support [x1, y1, x2, y2] or dict {x1, y1, x2, y2}
            bbox = obj.get("bbox") or obj.get("box")
            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                b = Box(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            elif isinstance(bbox, dict):
                b = Box(
                    float(bbox.get("x1", 0.0)),
                    float(bbox.get("y1", 0.0)),
                    float(bbox.get("x2", 0.0)),
                    float(bbox.get("y2", 0.0)),
                )
            else:
                continue

            detections.append(
                Detection(
                    class_name=canonical_cls,
                    conf=conf,
                    box=b,
                    track_id=track_id,
                )
            )

        return FrameMeta(
            ts=ts,
            frame_id=frame_id,
            camera_id=camera_id,
            detections=detections,
            frame=frame_dims,
        )

    def parse_frame(
        self, payload: Union[str, bytes, Dict[str, Any]]
    ) -> Tuple[FrameMeta, List[Detection]]:
        """Parse payload and return tuple of (FrameMeta, List[Detection])."""
        meta = self.parse_payload(payload)
        return meta, meta.detections


class JsonFileMetadataTailer:
    """Tails an append-only JSONL metadata file emitted by PipeGen."""

    def __init__(
        self, file_path: Union[str, Path], adapter: Optional[PipeGenAdapter] = None
    ) -> None:
        self.file_path = Path(file_path)
        self.adapter = adapter or PipeGenAdapter()

    def iter_frames(
        self, poll_interval_s: float = 0.01, stop_at_eof: bool = False
    ) -> Iterator[FrameMeta]:
        """Generator yielding FrameMeta from new lines in the metadata file."""
        if not self.file_path.exists():
            if stop_at_eof:
                return
            while not self.file_path.exists():
                time.sleep(poll_interval_s)

        with open(self.file_path, "r", encoding="utf-8") as f:
            while True:
                line = f.readline()
                if line:
                    line = line.strip()
                    if line:
                        try:
                            yield self.adapter.parse_payload(line)
                        except Exception:
                            continue
                else:
                    if stop_at_eof:
                        break
                    time.sleep(poll_interval_s)
