"""SiteSentinel Baseline CPU Detector (ONNX Runtime).

Provides a software CPU detection fallback for offline testing, local evaluation,
and development when a PipeGen DeepStream + TensorRT hardware export is not available.

Features:
- Aspect-ratio preserving letterboxing with stride-aligned padding.
- Non-Maximum Suppression (NMS) with configurable IoU and confidence thresholds.
- Class mapping from configuration (mapping model outputs to canonical PPE classes).
- Batch-free low-latency CPU mode.
- Adaptive frame skipping to hold real-time playback on CPU.

IMPORTANT: This is a BASELINE development detector. It does not replace the hardware-accelerated
PipeGen TensorRT engine. All metrics produced using this detector must be marked as BASELINE/MEASURED (baseline).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from sentinel.domain.models import Box, Detection, FrameDimensions, FrameMeta

logger = logging.getLogger("sentinel.adapters.baseline_detector")


class BaselineONNXDetector:
    """CPU-only baseline detector running ONNX Runtime models."""

    DEFAULT_CLASSES = ["person", "helmet", "no_helmet", "vest"]

    def __init__(
        self,
        model_path: Union[str, Path] = "models/baseline/detector.onnx",
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        camera_id: str = "cam-01",
        class_map: Optional[Dict[str, str]] = None,
        low_latency: bool = True,
        frame_skip: int = 1,
        adaptive_skip: bool = False,
        target_fps: float = 25.0,
    ) -> None:
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.camera_id = camera_id
        self.class_map: Dict[str, str] = class_map or {}
        self.low_latency = low_latency
        self.frame_skip = max(1, frame_skip)
        self.adaptive_skip = adaptive_skip
        self.target_fps = target_fps

        self._session: Any = None
        self._input_name: Optional[str] = None
        self._input_shape: Tuple[int, int] = (640, 640)
        self.last_latency_ms: float = 0.0
        self._last_meta: Optional[FrameMeta] = None
        self._consecutive_slow_frames: int = 0

        if not self.model_path.exists():
            logger.info("Baseline weights not found at %s", self.model_path)
        else:
            self._load_session()

    @property
    def is_ready(self) -> bool:
        return self._session is not None

    def _load_session(self) -> None:
        try:
            import onnxruntime as ort  # type: ignore

            opts = ort.SessionOptions()
            if self.low_latency:
                opts.intra_op_num_threads = 2
                opts.inter_op_num_threads = 1
                opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            else:
                opts.intra_op_num_threads = 4
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(
                str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"]
            )
            inputs = self._session.get_inputs()
            self._input_name = inputs[0].name
            shape = inputs[0].shape
            if len(shape) >= 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                self._input_shape = (shape[2], shape[3])
            logger.info(
                "Loaded baseline ONNX detector from %s (input size: %s)",
                self.model_path,
                self._input_shape,
            )
        except ImportError:
            logger.warning("onnxruntime is not installed. BaselineONNXDetector is unavailable.")
        except Exception as exc:
            logger.error("Failed to initialize ONNX runtime session: %s", exc)

    def letterbox(
        self,
        img: np.ndarray,
        new_shape: Tuple[int, int] = (640, 640),
        color: Tuple[int, int, int] = (114, 114, 114),
        stride: int = 32,
    ) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Resize and pad image while meeting stride-multiple constraints and preserving aspect ratio."""
        h, w = img.shape[:2]
        target_h, target_w = new_shape

        scale = min(target_w / w, target_h / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))

        dw = target_w - nw
        dh = target_h - nh

        # Divide padding into 2 sides
        pad_x = dw // 2
        pad_y = dh // 2

        import cv2

        if (w, h) != (nw, nh):
            resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        else:
            resized = img

        top, bottom = pad_y, target_h - (nh + pad_y)
        left, right = pad_x, target_w - (nw + pad_x)

        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
        )
        return padded, scale, (pad_x, pad_y)

    def preprocess(self, img: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Prepares raw BGR image array into normalized NCHW float32 tensor."""
        import cv2

        padded, scale, (pad_x, pad_y) = self.letterbox(img, self._input_shape)

        # BGR to RGB, transpose HWC to CHW, scale 0..255 to 0.0..1.0
        blob = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)
        return np.ascontiguousarray(blob), scale, (pad_x, pad_y)

    def _nms(
        self,
        boxes: List[List[float]],
        scores: List[float],
        iou_threshold: float,
    ) -> List[int]:
        """Pure-NumPy Non-Maximum Suppression with OpenCV fallback."""
        if not boxes:
            return []
        try:
            import cv2

            indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, iou_threshold)
            if hasattr(indices, "flatten"):
                return [int(x) for x in indices.flatten()]
            return [int(x) for x in indices]
        except Exception:
            pass

        # NumPy fallback NMS
        b = np.array(boxes, dtype=np.float32)
        s = np.array(scores, dtype=np.float32)
        x1 = b[:, 0]
        y1 = b[:, 1]
        x2 = b[:, 2]
        y2 = b[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        order = s.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(int(i))
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)

            inds = np.where(ovr <= iou_threshold)[0]
            order = order[inds + 1]

        return keep

    def map_class(self, cls_id: int) -> str:
        """Map class ID or raw name to canonical PPE class name."""
        if cls_id < len(self.DEFAULT_CLASSES):
            raw_name = self.DEFAULT_CLASSES[cls_id]
        else:
            raw_name = f"class_{cls_id}"

        # Check config class_map
        if str(cls_id) in self.class_map:
            return self.class_map[str(cls_id)]
        if raw_name in self.class_map:
            return self.class_map[raw_name]
        return raw_name

    def detect(
        self,
        frame: np.ndarray,
        frame_id: int = 0,
        timestamp: float = 0.0,
    ) -> FrameMeta:
        """Run object detection inference on a single BGR video frame."""
        orig_h, orig_w = frame.shape[:2]
        frame_dims = FrameDimensions(width=orig_w, height=orig_h)

        # Check frame skipping for CPU real-time retention
        eff_skip = self.frame_skip
        if self.adaptive_skip and self._consecutive_slow_frames > 2:
            eff_skip = max(self.frame_skip, 2)

        if frame_id % eff_skip != 0 and self._last_meta is not None:
            # Return previous frame detections forward with updated ts/frame_id
            return FrameMeta(
                ts=timestamp,
                frame_id=frame_id,
                camera_id=self.camera_id,
                detections=self._last_meta.detections,
                frame=frame_dims,
            )

        if self._session is None:
            raise RuntimeError(
                f"Baseline weights missing at {self.model_path}. "
                "Run scripts/fetch_baseline_model.sh to download permissive CPU weights."
            )

        t_start = time.perf_counter()
        blob, scale, (pad_x, pad_y) = self.preprocess(frame)

        outputs = self._session.run(None, {self._input_name: blob})
        raw_output = outputs[0]
        self.last_latency_ms = (time.perf_counter() - t_start) * 1000.0

        # Adaptive skip latency tracking
        target_budget_ms = (1000.0 / self.target_fps) if self.target_fps > 0 else 40.0
        if self.last_latency_ms > target_budget_ms * 1.2:
            self._consecutive_slow_frames += 1
        else:
            self._consecutive_slow_frames = max(0, self._consecutive_slow_frames - 1)

        detections: List[Detection] = []
        if raw_output.ndim == 3 and raw_output.shape[1] < raw_output.shape[2]:
            preds = np.transpose(raw_output[0], (1, 0))
        elif raw_output.ndim == 3:
            preds = raw_output[0]
        else:
            preds = raw_output

        boxes: List[List[float]] = []
        scores: List[float] = []
        class_ids: List[int] = []

        for row in preds:
            cx, cy, bw, bh = row[:4]
            class_scores = row[4:]
            cls_id = int(np.argmax(class_scores))
            conf = float(class_scores[cls_id])
            if conf >= self.conf_threshold:
                x1 = (cx - bw / 2.0 - pad_x) / scale
                y1 = (cy - bh / 2.0 - pad_y) / scale
                x2 = (cx + bw / 2.0 - pad_x) / scale
                y2 = (cy + bh / 2.0 - pad_y) / scale

                boxes.append(
                    [max(0.0, x1), max(0.0, y1), min(float(orig_w), x2), min(float(orig_h), y2)]
                )
                scores.append(conf)
                class_ids.append(cls_id)

        # Apply Non-Maximum Suppression
        indices = self._nms(boxes, scores, self.iou_threshold)
        for i in indices:
            b = boxes[i]
            cid = class_ids[i]
            cname = self.map_class(cid)
            detections.append(
                Detection(
                    class_name=cname,
                    conf=round(float(scores[i]), 3),
                    box=Box(
                        x1=round(b[0], 1),
                        y1=round(b[1], 1),
                        x2=round(b[2], 1),
                        y2=round(b[3], 1),
                    ),
                )
            )

        meta = FrameMeta(
            ts=timestamp,
            frame_id=frame_id,
            camera_id=self.camera_id,
            detections=detections,
            frame=frame_dims,
        )
        self._last_meta = meta
        return meta
