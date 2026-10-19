"""Adapter converting PipeGen's detection payloads to canonical FrameMeta objects.

Provides:
- PipeGenAdapter: multi-format parser (canonical, DeepStream pipe-delimited,
  DeepStream object-array, NDJSON) with configurable coordinate conventions,
  normalizations, timestamps, and zero-crash fault-tolerant parsing.
- JsonFileMetadataTailer: tails an append-only JSONL file or directory of JSON frame metadata.
"""

from __future__ import annotations

import datetime
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from sentinel.domain.models import Box, Detection, FrameDimensions, FrameMeta
from sentinel.logging import get_logger

logger = get_logger(__name__)


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
        format_mode: str = "auto",
        bbox_format: str = "xyxy",
        bbox_normalized: bool = False,
        timestamp_format: str = "epoch",
        fps: float = 25.0,
        track_id_fields: Optional[List[str]] = None,
        class_fields: Optional[List[str]] = None,
        conf_fields: Optional[List[str]] = None,
        bbox_fields: Optional[List[str]] = None,
    ) -> None:
        self.class_map: Dict[str, str] = {**self.DEFAULT_CLASS_MAP, **(class_map or {})}
        self.default_camera_id: str = default_camera_id
        self.format_mode: str = format_mode
        self.bbox_format: str = bbox_format.lower()
        self.bbox_normalized: bool = bbox_normalized
        self.timestamp_format: str = timestamp_format.lower()
        self.fps: float = fps if fps > 0 else 25.0

        self.track_id_fields: List[str] = track_id_fields or [
            "track_id",
            "id",
            "object_id",
            "objectId",
        ]
        self.class_fields: List[str] = class_fields or [
            "class",
            "type",
            "label",
            "class_id",
            "classId",
        ]
        self.conf_fields: List[str] = conf_fields or ["conf", "confidence", "score"]
        self.bbox_fields: List[str] = bbox_fields or ["bbox", "box", "rect"]

        # Integrity & resilience metrics
        self.adapter_rejects_total: int = 0
        self.adapter_parsed_total: int = 0

    def get_metrics(self) -> Dict[str, int]:
        return {
            "adapter_rejects_total": self.adapter_rejects_total,
            "adapter_parsed_total": self.adapter_parsed_total,
        }

    def map_class_name(self, raw_class: Union[str, int, None]) -> str:
        """Map raw detector class string or integer ID to canonical class name."""
        if raw_class is None:
            return "unknown"
        key = str(raw_class).strip().lower()
        return self.class_map.get(key, key)

    def _safe_float(self, val: Any) -> Optional[float]:
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    def _parse_timestamp(self, data: Dict[str, Any], frame_id: int) -> float:
        """Extract and normalize timestamp from data dict."""
        for field in ("ts", "timestamp", "@timestamp", "time"):
            if field in data and data[field] is not None:
                val = data[field]
                f_val = self._safe_float(val)
                if f_val is not None:
                    return f_val
                # Try ISO-8601 string
                try:
                    iso_str = str(val).replace("Z", "+00:00")
                    return datetime.datetime.fromisoformat(iso_str).timestamp()
                except Exception:
                    pass

        # PTS / Frame number fallback
        if self.timestamp_format == "pts_fps" and frame_id >= 0:
            return float(frame_id) / self.fps

        return time.time()

    def _parse_box(
        self,
        raw_box: Any,
        frame_w: float,
        frame_h: float,
        bbox_format: Optional[str] = None,
    ) -> Optional[Box]:
        """Convert arbitrary bbox structure to a validated Box or None if corrupt."""
        fmt = (bbox_format or self.bbox_format).lower()
        x1: Optional[float] = None
        y1: Optional[float] = None
        x2: Optional[float] = None
        y2: Optional[float] = None

        if isinstance(raw_box, (list, tuple)) and len(raw_box) >= 4:
            vals = [self._safe_float(v) for v in raw_box[:4]]
            if any(v is None for v in vals):
                return None
            v0 = float(vals[0])  # type: ignore[arg-type]
            v1 = float(vals[1])  # type: ignore[arg-type]
            v2 = float(vals[2])  # type: ignore[arg-type]
            v3 = float(vals[3])  # type: ignore[arg-type]
            if fmt == "xywh":
                x1, y1 = v0, v1
                x2, y2 = v0 + v2, v1 + v3
            else:  # xyxy
                x1, y1, x2, y2 = v0, v1, v2, v3

        elif isinstance(raw_box, dict):
            # Check left/top/width/height (DeepStream nvmsgconv)
            if "left" in raw_box and "top" in raw_box:
                box_l = self._safe_float(raw_box.get("left"))
                t = self._safe_float(raw_box.get("top"))
                w = self._safe_float(raw_box.get("width", 0.0))
                h = self._safe_float(raw_box.get("height", 0.0))
                if box_l is not None and t is not None and w is not None and h is not None:
                    x1, y1, x2, y2 = box_l, t, box_l + w, t + h
            # Check topleftx / bottomrightx
            elif "topleftx" in raw_box or "top_left_x" in raw_box:
                lx = self._safe_float(raw_box.get("topleftx", raw_box.get("top_left_x")))
                ly = self._safe_float(raw_box.get("toplefty", raw_box.get("top_left_y")))
                rx = self._safe_float(raw_box.get("bottomrightx", raw_box.get("bottom_right_x")))
                ry = self._safe_float(raw_box.get("bottomrighty", raw_box.get("bottom_right_y")))
                if lx is not None and ly is not None and rx is not None and ry is not None:
                    x1, y1, x2, y2 = lx, ly, rx, ry
            # Standard x1, y1, x2, y2 or x, y, w, h
            elif "x1" in raw_box and "y1" in raw_box:
                x1 = self._safe_float(raw_box.get("x1"))
                y1 = self._safe_float(raw_box.get("y1"))
                x2 = self._safe_float(raw_box.get("x2"))
                y2 = self._safe_float(raw_box.get("y2"))
            elif "x" in raw_box and "y" in raw_box and "w" in raw_box:
                x = self._safe_float(raw_box.get("x"))
                y = self._safe_float(raw_box.get("y"))
                w = self._safe_float(raw_box.get("w"))
                h = self._safe_float(raw_box.get("h"))
                if x is not None and y is not None and w is not None and h is not None:
                    x1, y1, x2, y2 = x, y, x + w, y + h

        if x1 is None or y1 is None or x2 is None or y2 is None:
            return None

        # De-normalize if coordinates are normalized [0.0, 1.0]
        if self.bbox_normalized or (
            0.0 <= x1 <= 1.0
            and 0.0 <= x2 <= 1.0
            and 0.0 <= y1 <= 1.0
            and 0.0 <= y2 <= 1.0
            and max(x2, y2) <= 1.0
        ):
            x1 *= frame_w
            x2 *= frame_w
            y1 *= frame_h
            y2 *= frame_h

        # Clamp coordinates to non-negative
        x1 = max(0.0, x1)
        y1 = max(0.0, y1)
        x2 = max(0.0, x2)
        y2 = max(0.0, y2)

        # Discard degenerate zero-size boxes
        if x2 <= x1 or y2 <= y1:
            return None

        try:
            return Box(x1, y1, x2, y2)
        except Exception:
            return None

    def _parse_pipe_delimited_string(
        self, line: str, frame_w: float, frame_h: float
    ) -> Optional[Detection]:
        """Parse 'track_id|class_id|x|y|w|h|conf' or 'track_id|class_id|x1|y1|x2|y2|conf'."""
        tokens = [t.strip() for t in line.split("|")]
        if len(tokens) < 6:
            return None

        try:
            raw_track = int(tokens[0]) if tokens[0] not in {"-1", "", "null", "None"} else None
        except ValueError:
            raw_track = None

        raw_class = tokens[1]
        canonical_cls = self.map_class_name(raw_class)

        # Parse box coordinates
        if len(tokens) == 6:
            # track_id|class|x|y|w|h
            box = self._parse_box(
                [tokens[2], tokens[3], tokens[4], tokens[5]], frame_w, frame_h, bbox_format="xywh"
            )
            conf = 0.8
        elif len(tokens) >= 7:
            # track_id|class|x|y|w|h|conf or track_id|class|x1|y1|x2|y2|conf
            conf_val = self._safe_float(tokens[6]) or 0.8
            conf = conf_val
            box = self._parse_box(
                [tokens[2], tokens[3], tokens[4], tokens[5]],
                frame_w,
                frame_h,
                bbox_format=self.bbox_format,
            )
        else:
            return None

        if not box:
            return None

        return Detection(
            class_name=canonical_cls,
            conf=conf,
            box=box,
            track_id=raw_track,
        )

    def _parse_deepstream_array_payload(self, data: Dict[str, Any]) -> Optional[FrameMeta]:
        """Parse NVIDIA DeepStream standard schema (nvmsgconv full array)."""
        camera_id = str(
            data.get("sensorId")
            or (data.get("sensor", {}).get("id") if isinstance(data.get("sensor"), dict) else None)
            or self.default_camera_id
        )
        raw_fid = data.get("id") or data.get("frameId") or data.get("frame_id", 0)
        try:
            frame_id = int(raw_fid)
        except (ValueError, TypeError):
            frame_id = 0

        ts = self._parse_timestamp(data, frame_id)

        # Resolution
        frame_w = 1920.0
        frame_h = 1080.0
        frame_dims: Optional[FrameDimensions] = None
        if "frame" in data and isinstance(data["frame"], dict):
            w = self._safe_float(data["frame"].get("width"))
            h = self._safe_float(data["frame"].get("height"))
            if w and h:
                frame_w, frame_h = w, h
                frame_dims = FrameDimensions(width=int(w), height=int(h))

        raw_objects = data.get("objects", [])
        if not isinstance(raw_objects, list):
            return None

        detections: List[Detection] = []
        for item in raw_objects:
            if not isinstance(item, dict):
                self.adapter_rejects_total += 1
                continue

            obj = item.get("object", item)
            if not isinstance(obj, dict):
                self.adapter_rejects_total += 1
                continue

            # Class
            raw_cls = None
            for f in self.class_fields:
                if f in obj and obj[f] is not None:
                    raw_cls = obj[f]
                    break
            canonical_cls = self.map_class_name(raw_cls)

            # Confidence
            conf = 0.8
            for f in self.conf_fields:
                if f in obj and obj[f] is not None:
                    c = self._safe_float(obj[f])
                    if c is not None:
                        conf = c
                        break

            # Track ID
            track_id = None
            for f in self.track_id_fields:
                if f in obj and obj[f] is not None:
                    try:
                        tid_str = str(obj[f]).strip()
                        if tid_str not in {"-1", "", "null", "None"}:
                            track_id = int(tid_str)
                            break
                    except ValueError:
                        pass

            # Bounding box
            raw_box = None
            for f in self.bbox_fields:
                if f in obj and obj[f] is not None:
                    raw_box = obj[f]
                    break

            if raw_box is None:
                self.adapter_rejects_total += 1
                continue

            box = self._parse_box(raw_box, frame_w, frame_h)
            if not box:
                self.adapter_rejects_total += 1
                continue

            detections.append(
                Detection(
                    class_name=canonical_cls,
                    conf=conf,
                    box=box,
                    track_id=track_id,
                )
            )

        return FrameMeta(
            ts=ts,
            frame_id=frame_id,
            camera_id=camera_id,
            detections=detections,
            frame=frame_dims or FrameDimensions(width=int(frame_w), height=int(frame_h)),
        )

    def _parse_deepstream_pipe_payload(
        self, data_or_str: Union[str, Dict[str, Any]]
    ) -> Optional[FrameMeta]:
        """Parse pipe-delimited payload (in string or wrapped in JSON)."""
        frame_w = 1920.0
        frame_h = 1080.0
        frame_dims = FrameDimensions(width=1920, height=1080)

        if isinstance(data_or_str, dict):
            camera_id = str(
                data_or_str.get("sensorId")
                or data_or_str.get("camera_id")
                or self.default_camera_id
            )
            raw_fid = data_or_str.get("frameId") or data_or_str.get("frame_id", 0)
            try:
                frame_id = int(raw_fid)
            except (ValueError, TypeError):
                frame_id = 0

            ts = self._parse_timestamp(data_or_str, frame_id)
            raw_objects = data_or_str.get("objects", [])

            detections: List[Detection] = []
            for item in raw_objects:
                if isinstance(item, str):
                    det = self._parse_pipe_delimited_string(item, frame_w, frame_h)
                    if det:
                        detections.append(det)
                    else:
                        self.adapter_rejects_total += 1

            return FrameMeta(
                ts=ts,
                frame_id=frame_id,
                camera_id=camera_id,
                detections=detections,
                frame=frame_dims,
            )

        elif isinstance(data_or_str, str):
            # Raw string of pipe tokens: frame_num|camera_id|ts|track|class|x|y|w|h|conf
            lines = [line.strip() for line in data_or_str.splitlines() if line.strip()]
            if not lines:
                return None

            camera_id = self.default_camera_id
            frame_id = 0
            ts = time.time()

            detections = []
            for line in lines:
                # Could be multiple object specs separated by #
                sub_items = line.split("#")
                for sub in sub_items:
                    parts = sub.split("|")
                    if len(parts) >= 10:
                        # frame|cam|ts|track|class|x|y|w|h|conf
                        try:
                            frame_id = int(parts[0])
                        except ValueError:
                            pass
                        camera_id = parts[1] or camera_id
                        ts_f = self._safe_float(parts[2])
                        if ts_f:
                            ts = ts_f
                        obj_line = "|".join(parts[3:])
                        det = self._parse_pipe_delimited_string(obj_line, frame_w, frame_h)
                        if det:
                            detections.append(det)
                        else:
                            self.adapter_rejects_total += 1
                    else:
                        det = self._parse_pipe_delimited_string(sub, frame_w, frame_h)
                        if det:
                            detections.append(det)
                        else:
                            self.adapter_rejects_total += 1

            return FrameMeta(
                ts=ts,
                frame_id=frame_id,
                camera_id=camera_id,
                detections=detections,
                frame=frame_dims,
            )

        return None

    def _parse_canonical_payload(self, data: Dict[str, Any]) -> FrameMeta:
        """Parse standard SiteSentinel internal JSON schema."""
        camera_id = str(data.get("camera_id") or data.get("sensorId") or self.default_camera_id)
        raw_fid = data.get("frame_id") or data.get("frameId")
        if raw_fid is not None:
            try:
                frame_id = int(raw_fid)
            except (ValueError, TypeError):
                frame_id = 0
        else:
            frame_id = 0

        ts = self._parse_timestamp(data, frame_id)

        frame_w = 1920.0
        frame_h = 1080.0
        frame_dims: Optional[FrameDimensions] = None
        frame_dict = data.get("frame")
        if frame_dict and isinstance(frame_dict, dict):
            w = self._safe_float(frame_dict.get("width"))
            h = self._safe_float(frame_dict.get("height"))
            if w and h:
                frame_w, frame_h = w, h
                frame_dims = FrameDimensions(width=int(w), height=int(h))

        raw_objects = data.get("objects")
        if raw_objects is None:
            raw_objects = data.get("detections", [])

        if not isinstance(raw_objects, list):
            raw_objects = []

        detections: List[Detection] = []
        for obj in raw_objects:
            if isinstance(obj, str) and "|" in obj:
                # Mixed pipe-delimited object inside canonical payload
                det = self._parse_pipe_delimited_string(obj, frame_w, frame_h)
                if det:
                    detections.append(det)
                else:
                    self.adapter_rejects_total += 1
                continue

            if not isinstance(obj, dict):
                self.adapter_rejects_total += 1
                continue

            # Class
            raw_cls = None
            for key in self.class_fields:
                if key in obj and obj[key] is not None:
                    raw_cls = obj[key]
                    break
            canonical_cls = self.map_class_name(raw_cls)

            # Confidence
            conf = 0.8
            for key in self.conf_fields:
                if key in obj and obj[key] is not None:
                    c = self._safe_float(obj[key])
                    if c is not None:
                        conf = c
                        break

            # Track ID
            track_id = None
            for key in self.track_id_fields:
                if key in obj and obj[key] is not None:
                    try:
                        raw_tid = str(obj[key]).strip()
                        if raw_tid not in {"-1", "", "null", "None"}:
                            track_id = int(raw_tid)
                            break
                    except ValueError:
                        pass

            # Bounding box
            raw_box = None
            for key in self.bbox_fields:
                if key in obj and obj[key] is not None:
                    raw_box = obj[key]
                    break

            if raw_box is None:
                self.adapter_rejects_total += 1
                continue

            box = self._parse_box(raw_box, frame_w, frame_h)
            if not box:
                self.adapter_rejects_total += 1
                continue

            detections.append(
                Detection(
                    class_name=canonical_cls,
                    conf=conf,
                    box=box,
                    track_id=track_id,
                )
            )

        return FrameMeta(
            ts=ts,
            frame_id=frame_id,
            camera_id=camera_id,
            detections=detections,
            frame=frame_dims or FrameDimensions(width=int(frame_w), height=int(frame_h)),
        )

    def parse_payload(self, payload: Union[str, bytes, Dict[str, Any]]) -> FrameMeta:
        """Convert a raw JSON string, bytes, NDJSON, or parsed dict into a FrameMeta object.

        Guaranteed to never raise an unhandled exception or crash on malformed inputs.
        """
        # Convert bytes to string
        if isinstance(payload, bytes):
            try:
                payload = payload.decode("utf-8", errors="replace")
            except Exception:
                self.adapter_rejects_total += 1
                return self._fallback_frame()

        # Handle NDJSON or string payload
        data: Optional[Dict[str, Any]] = None
        if isinstance(payload, str):
            payload_str = payload.strip()
            if not payload_str:
                self.adapter_rejects_total += 1
                return self._fallback_frame()

            # First: attempt to parse payload_str as a complete JSON structure
            try:
                parsed = json.loads(payload_str)
                if isinstance(parsed, dict):
                    data = parsed
            except Exception:
                pass

            # If not a single JSON dict, handle NDJSON lines or header
            if data is None:
                lines = [line.strip() for line in payload_str.splitlines() if line.strip()]
                for line in lines:
                    if "_sentinel_capture_header" in line:
                        continue
                    try:
                        candidate = json.loads(line)
                        if isinstance(candidate, dict):
                            data = candidate
                            break
                    except Exception:
                        pass

            # If still not JSON, test if it is a raw pipe-delimited payload
            if data is None:
                if "|" in payload_str:
                    meta = self._parse_deepstream_pipe_payload(payload_str)
                    if meta:
                        self.adapter_parsed_total += 1
                        return meta
                self.adapter_rejects_total += 1
                logger.warning("Failed to decode payload as JSON or pipe tokens")
                return self._fallback_frame()
        elif isinstance(payload, dict):
            data = payload
        else:
            self.adapter_rejects_total += 1
            return self._fallback_frame()

        if not isinstance(data, dict):
            self.adapter_rejects_total += 1
            return self._fallback_frame()

        # Auto-detect or route by format_mode
        mode = self.format_mode
        if mode == "auto":
            # Heuristic detection: check deepstream_pipe before deepstream_array
            objs = data.get("objects")
            if isinstance(objs, list) and objs and isinstance(objs[0], str) and "|" in objs[0]:
                mode = "deepstream_pipe"
            elif (
                "sensorId" in data
                or "@timestamp" in data
                or (
                    isinstance(objs, list)
                    and objs
                    and isinstance(objs[0], dict)
                    and "object" in objs[0]
                )
            ):
                mode = "deepstream_array"
            else:
                mode = "canonical"

        try:
            if mode == "deepstream_array":
                res = self._parse_deepstream_array_payload(data)
                if res is not None:
                    self.adapter_parsed_total += 1
                    return res
                # Fallback to canonical if array parser returned None
                res = self._parse_canonical_payload(data)
                self.adapter_parsed_total += 1
                return res

            elif mode == "deepstream_pipe":
                res = self._parse_deepstream_pipe_payload(data)
                if res is not None:
                    self.adapter_parsed_total += 1
                    return res
                res = self._parse_canonical_payload(data)
                self.adapter_parsed_total += 1
                return res

            else:  # canonical
                res = self._parse_canonical_payload(data)
                self.adapter_parsed_total += 1
                return res

        except Exception as ex:
            self.adapter_rejects_total += 1
            logger.error("Unexpected error parsing payload: %s", ex)
            return self._fallback_frame()

    def parse_frame(
        self, payload: Union[str, bytes, Dict[str, Any]]
    ) -> Tuple[FrameMeta, List[Detection]]:
        """Parse payload and return tuple of (FrameMeta, List[Detection])."""
        meta = self.parse_payload(payload)
        return meta, meta.detections

    def _fallback_frame(self) -> FrameMeta:
        return FrameMeta(
            ts=time.time(),
            frame_id=0,
            camera_id=self.default_camera_id,
            detections=[],
            frame=FrameDimensions(width=1920, height=1080),
        )

    def diagnose_payload(self, payload: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
        """Perform self-diagnosis on a sample payload and report parser evaluations and field mappings."""
        report: Dict[str, Any] = {
            "parsed_successfully": False,
            "detected_format": "unknown",
            "format_evaluations": {},
            "fields_found": {},
            "detections_count": 0,
            "classes_detected": [],
            "warnings": [],
            "recommendations": [],
        }

        # Raw data inspection
        data: Optional[Dict[str, Any]] = None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")

        if isinstance(payload, str):
            lines = [line.strip() for line in payload.splitlines() if line.strip()]
            first_line = lines[0] if lines else ""
            if "_sentinel_capture_header" in first_line and len(lines) > 1:
                first_line = lines[1]
            try:
                data = json.loads(first_line)
            except Exception:
                pass

        elif isinstance(payload, dict):
            data = payload

        # Evaluate individual formats
        formats_to_test = ["canonical", "deepstream_array", "deepstream_pipe"]
        best_format = None
        max_detections = -1

        for fmt in formats_to_test:
            old_fmt = self.format_mode
            self.format_mode = fmt
            try:
                meta = self.parse_payload(payload)
                count = len(meta.detections)
                report["format_evaluations"][fmt] = {
                    "success": True,
                    "detections_count": count,
                    "frame_id": meta.frame_id,
                    "camera_id": meta.camera_id,
                }
                if count > max_detections:
                    max_detections = count
                    best_format = fmt
            except Exception as e:
                report["format_evaluations"][fmt] = {
                    "success": False,
                    "error": str(e),
                }
            finally:
                self.format_mode = old_fmt

        if best_format is not None and max_detections >= 0:
            report["parsed_successfully"] = True
            report["detected_format"] = best_format
            report["detections_count"] = max_detections

        # Inspect data fields if dict was parsed
        if data is not None:
            report["fields_found"] = {
                "camera_id": data.get("camera_id") or data.get("sensorId"),
                "frame_id": data.get("frame_id") or data.get("frameId") or data.get("id"),
                "timestamp": data.get("ts") or data.get("timestamp") or data.get("@timestamp"),
                "has_objects": "objects" in data or "detections" in data,
                "objects_type": type(data.get("objects") or data.get("detections")).__name__,
            }

            raw_objs = data.get("objects") or data.get("detections") or []
            if isinstance(raw_objs, list):
                for obj in raw_objs:
                    if isinstance(obj, dict):
                        inner = obj.get("object", obj)
                        for f in self.class_fields:
                            if f in inner:
                                cls_name = str(inner[f])
                                if cls_name not in report["classes_detected"]:
                                    report["classes_detected"].append(cls_name)
                    elif isinstance(obj, str) and "|" in obj:
                        parts = obj.split("|")
                        if len(parts) >= 2:
                            cls_name = parts[1]
                            if cls_name not in report["classes_detected"]:
                                report["classes_detected"].append(cls_name)

            # Recommendations for unmapped classes
            for raw_cls in report["classes_detected"]:
                if raw_cls not in self.class_map and str(raw_cls).lower() not in self.class_map:
                    report["warnings"].append(f"Unmapped detector class: '{raw_cls}'")
                    report["recommendations"].append(
                        f"Add to config/sentinel.yaml: class_map: {{'{raw_cls}': 'person|helmet|vest'}}"
                    )

        if not report["parsed_successfully"]:
            report["recommendations"].append(
                "Payload does not match known schemas. Check docs/DETECTION_SCHEMA.md for supported formats."
            )

        return report


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
                            # Skip capture headers if present
                            if "_sentinel_capture_header" in line:
                                continue
                            yield self.adapter.parse_payload(line)
                        except Exception:
                            continue
                else:
                    if stop_at_eof:
                        break
                    time.sleep(poll_interval_s)
