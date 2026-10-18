"""SiteSentinel Baseline CPU Detector (ONNX Runtime).

Provides a software CPU detection fallback for offline testing, local evaluation,
and development when a PipeGen DeepStream + TensorRT hardware export is not available.

IMPORTANT: This is a BASELINE development detector. It does not replace the hardware-accelerated
PipeGen TensorRT engine. All metrics produced using this detector must be marked as BASELINE/SIMULATED.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

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
    ) -> None:
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.camera_id = camera_id
        self._session: Any = None
        self._input_name: Optional[str] = None
        self._input_shape: Tuple[int, int] = (640, 640)

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
            opts.intra_op_num_threads = 2
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

    def preprocess(self, img: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Resize and pad image to input shape preserving aspect ratio."""
        h, w = img.shape[:2]
        net_h, net_w = self._input_shape
        scale = min(net_w / w, net_h / h)
        nw, nh = int(w * scale), int(h * scale)

        import cv2

        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((net_h, net_w, 3), 114, dtype=np.uint8)
        pad_x, pad_y = (net_w - nw) // 2, (net_h - nh) // 2
        canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized

        # Normalize to [0, 1] RGB NCHW
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)
        return blob, scale, (pad_x, pad_y)

    def detect(
        self,
        frame: np.ndarray,
        frame_id: int = 0,
        timestamp: float = 0.0,
    ) -> FrameMeta:
        """Run object detection inference on a single BGR video frame."""
        if self._session is None:
            raise RuntimeError(
                f"Baseline weights missing at {self.model_path}. "
                "Run scripts/fetch_baseline_model.sh to download permissive CPU weights."
            )

        orig_h, orig_w = frame.shape[:2]
        blob, scale, (pad_x, pad_y) = self.preprocess(frame)

        outputs = self._session.run(None, {self._input_name: blob})
        raw_output = outputs[0]

        detections: List[Detection] = []
        if raw_output.ndim == 3 and raw_output.shape[1] < raw_output.shape[2]:
            # Format [batch, num_features, num_predictions] -> transpose to [num_predictions, num_features]
            preds = np.transpose(raw_output[0], (1, 0))
        elif raw_output.ndim == 3:
            preds = raw_output[0]
        else:
            preds = raw_output

        boxes = []
        scores = []
        class_ids = []

        for row in preds:
            cx, cy, bw, bh = row[:4]
            class_scores = row[4:]
            cls_id = int(np.argmax(class_scores))
            conf = float(class_scores[cls_id])
            if conf >= self.conf_threshold:
                # Unpad and scale coordinates to original image
                x1 = (cx - bw / 2.0 - pad_x) / scale
                y1 = (cy - bh / 2.0 - pad_y) / scale
                x2 = (cx + bw / 2.0 - pad_x) / scale
                y2 = (cy + bh / 2.0 - pad_y) / scale

                boxes.append(
                    [max(0.0, x1), max(0.0, y1), min(float(orig_w), x2), min(float(orig_h), y2)]
                )
                scores.append(conf)
                class_ids.append(cls_id)

        # Non-maximum suppression
        if boxes:
            import cv2

            indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, self.iou_threshold)
            for idx in indices.flatten() if hasattr(indices, "flatten") else indices:
                i = int(idx)
                b = boxes[i]
                cid = class_ids[i]
                cname = (
                    self.DEFAULT_CLASSES[cid] if cid < len(self.DEFAULT_CLASSES) else f"class_{cid}"
                )
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

        return FrameMeta(
            ts=timestamp,
            frame_id=frame_id,
            camera_id=self.camera_id,
            detections=detections,
            frame=FrameDimensions(width=orig_w, height=orig_h),
        )
