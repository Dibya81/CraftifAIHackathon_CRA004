"""Synthetic detection stream generator and video simulator for SiteSentinel.

Generates realistic detection streams (walking persons, track ID churn, occlusions, jitter)
and publishes to MQTT at 25 FPS (or writes synthetic video + JSON).

Named scenarios:
- compliant: Worker with helmet and vest walking in walkway.
- no_helmet: Worker without helmet in zone requiring helmet (triggers NO_HELMET).
- restricted_entry: Worker enters press-area (restricted zone).
- danger_dwell: Worker enters and dwells in crane-drop (danger zone) for > 5 s.
- crowd: 5-10 people walking, crossing paths, overlapping bounding boxes.
- flicker: Detections that flap/jitter to rigorously test the debounce state machine.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

# Ensure src/ is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel.domain.models import Detection, FrameMeta


class Simulator:
    """Convenience simulation harness providing typed FrameMeta and Detection objects."""

    def __init__(self, fps: float = 25.0, camera_id: str = "cam-01") -> None:
        self.fps = fps
        self.camera_id = camera_id

    def generate_scenario(
        self,
        scenario: str,
        duration_s: float = 5.0,
        start_ts: Optional[datetime.datetime] = None,
    ) -> List[Tuple[FrameMeta, List[Detection]]]:
        from sentinel.adapters.pipegen import PipeGenAdapter

        gen = SyntheticScenarioGenerator(scenario=scenario, fps=self.fps)
        adapter = PipeGenAdapter(default_camera_id=self.camera_id)
        frames: List[Tuple[FrameMeta, List[Detection]]] = []

        total_frames = int(duration_s * self.fps)
        base_dt = start_ts or datetime.datetime.now(datetime.timezone.utc)

        for f_idx in range(total_frames):
            t_sec = f_idx / self.fps
            raw_dict = gen.generate_frame(f_idx, t_sec)
            frame_dt = base_dt + datetime.timedelta(seconds=t_sec)
            raw_dict["ts"] = frame_dt.isoformat()
            meta, detections = adapter.parse_frame(raw_dict)
            frames.append((meta, detections))

        return frames


class SyntheticScenarioGenerator:
    """Generates synthetic bounding boxes and tracks based on predefined scenarios."""

    def __init__(self, scenario: str = "compliant", fps: float = 25.0) -> None:
        self.scenario = scenario
        self.fps = fps
        self.frame_width = 1920
        self.frame_height = 1080

    def generate_frame(self, frame_idx: int, t_sec: float) -> Dict[str, Any]:
        """Generates a canonical detection frame dictionary for time t_sec."""
        objects: List[Dict[str, Any]] = []

        if self.scenario == "compliant":
            # Worker walks along walkway: x from 200 to 800, y around 800
            x = 200.0 + (t_sec * 40.0) % 600.0
            y = 750.0 + 5.0 * math.sin(t_sec * 3.0)
            p_box = [x, y - 200.0, x + 80.0, y]
            objects.append({"track_id": 1, "class": "person", "conf": 0.94, "bbox": p_box})
            # Helmet on head (top 20%)
            h_box = [x + 10.0, y - 200.0, x + 70.0, y - 150.0]
            objects.append({"track_id": None, "class": "helmet", "conf": 0.96, "bbox": h_box})
            # Vest on torso
            v_box = [x + 5.0, y - 150.0, x + 75.0, y - 60.0]
            objects.append({"track_id": None, "class": "vest", "conf": 0.91, "bbox": v_box})

        elif self.scenario == "no_helmet":
            # Worker walks in walkway without helmet
            x = 300.0 + (t_sec * 35.0) % 500.0
            y = 780.0 + 4.0 * math.cos(t_sec * 2.5)
            p_box = [x, y - 220.0, x + 90.0, y]
            objects.append({"track_id": 2, "class": "person", "conf": 0.93, "bbox": p_box})
            # Vest is worn, but head is uncovered (explicit head/no_helmet)
            head_box = [x + 15.0, y - 220.0, x + 75.0, y - 165.0]
            objects.append({"track_id": None, "class": "no_helmet", "conf": 0.92, "bbox": head_box})
            v_box = [x + 10.0, y - 165.0, x + 80.0, y - 70.0]
            objects.append({"track_id": None, "class": "vest", "conf": 0.89, "bbox": v_box})

        elif self.scenario == "restricted_entry":
            # Worker walks from walkway (x=800, y=600) into press-area (x=1150, y=600)
            # Boundary is at x=1000
            x = 750.0 + t_sec * 50.0
            y = 650.0
            p_box = [x, y - 200.0, x + 80.0, y]
            objects.append({"track_id": 3, "class": "person", "conf": 0.95, "bbox": p_box})
            objects.append({"track_id": None, "class": "helmet", "conf": 0.94, "bbox": [x + 10.0, y - 200.0, x + 70.0, y - 150.0]})
            objects.append({"track_id": None, "class": "vest", "conf": 0.90, "bbox": [x + 5.0, y - 150.0, x + 75.0, y - 60.0]})

        elif self.scenario == "danger_dwell":
            # Worker enters crane-drop danger zone (x=1200..1500, y=100..300) and lingers
            x = 1350.0 + 10.0 * math.sin(t_sec * 1.5)
            y = 220.0 + 5.0 * math.cos(t_sec * 1.5)
            p_box = [x, y - 120.0, x + 50.0, y]
            objects.append({"track_id": 4, "class": "person", "conf": 0.92, "bbox": p_box})
            objects.append({"track_id": None, "class": "helmet", "conf": 0.95, "bbox": [x + 5.0, y - 120.0, x + 45.0, y - 90.0]})
            objects.append({"track_id": None, "class": "vest", "conf": 0.88, "bbox": [x + 2.0, y - 90.0, x + 48.0, y - 40.0]})

        elif self.scenario == "flicker":
            # Person missing helmet for 1.2s, wears it for 0.5s, removes it again (flaps)
            x = 400.0
            y = 750.0
            p_box = [x, y - 200.0, x + 80.0, y]
            objects.append({"track_id": 5, "class": "person", "conf": 0.92, "bbox": p_box})
            # Flap cycle: 1.2s missing, 0.6s present -> cycle 1.8s
            phase = t_sec % 1.8
            if phase >= 1.2:
                # Helmet appears temporarily
                objects.append({"track_id": None, "class": "helmet", "conf": 0.90, "bbox": [x + 10.0, y - 200.0, x + 70.0, y - 150.0]})
            else:
                objects.append({"track_id": None, "class": "no_helmet", "conf": 0.91, "bbox": [x + 15.0, y - 200.0, x + 65.0, y - 150.0]})

        elif self.scenario == "crowd":
            # 6 people crossing paths
            for i in range(6):
                track_id = i + 10
                speed = 25.0 + i * 5.0
                direction = 1 if i % 2 == 0 else -1
                x = 300.0 + ((t_sec * speed * direction + i * 150.0) % 1200.0)
                y = 500.0 + (i * 70.0)
                p_box = [x, y - 180.0, x + 70.0, y]
                objects.append({"track_id": track_id, "class": "person", "conf": 0.88 + (i % 3) * 0.03, "bbox": p_box})
                if i % 3 != 0:
                    # Helmet
                    objects.append({"track_id": None, "class": "helmet", "conf": 0.92, "bbox": [x + 8.0, y - 180.0, x + 62.0, y - 135.0]})
                else:
                    objects.append({"track_id": None, "class": "no_helmet", "conf": 0.90, "bbox": [x + 10.0, y - 180.0, x + 60.0, y - 135.0]})
                if i % 2 == 0:
                    objects.append({"track_id": None, "class": "vest", "conf": 0.89, "bbox": [x + 5.0, y - 135.0, x + 65.0, y - 60.0]})

        return {
            "camera_id": "cam-01",
            "frame_id": frame_idx,
            "ts": t_sec,
            "frame": {"width": self.frame_width, "height": self.frame_height},
            "objects": objects,
        }

    def render_frame_image(self, frame_dict: Dict[str, Any]) -> np.ndarray:
        """Renders synthetic detection frame into an annotated OpenCV BGR image."""
        img = np.full((self.frame_height, self.frame_width, 3), (30, 42, 51), dtype=np.uint8)

        # Draw site zones
        # Walkway: safe (blue #1F6FD0 -> BGR 208, 111, 31)
        cv2.polylines(img, [np.array([[100, 600], [900, 600], [900, 1000], [100, 1000]])], True, (208, 111, 31), 2)
        cv2.putText(img, "ZONE: WALKWAY (SAFE)", (110, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (208, 111, 31), 2)

        # Press area: restricted (amber #F2A900 -> BGR 0, 169, 242)
        cv2.polylines(img, [np.array([[1000, 300], [1700, 300], [1700, 900], [1000, 900]])], True, (0, 169, 242), 2)
        cv2.putText(img, "ZONE: PRESS-AREA (RESTRICTED)", (1010, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 169, 242), 2)

        # Crane drop: danger (hazard orange #E8590C -> BGR 12, 89, 232)
        cv2.polylines(img, [np.array([[1200, 100], [1500, 100], [1500, 300], [1200, 300]])], True, (12, 89, 232), 2)
        cv2.putText(img, "ZONE: CRANE-DROP (DANGER)", (1210, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (12, 89, 232), 2)

        # Draw detected objects
        for obj in frame_dict["objects"]:
            cls_name = obj["class"]
            b = obj["bbox"]
            pt1 = (int(b[0]), int(b[1]))
            pt2 = (int(b[2]), int(b[3]))

            if cls_name == "person":
                cv2.rectangle(img, pt1, pt2, (200, 200, 200), 2)
                lbl = f"person #{obj['track_id']} ({obj['conf']:.2f})"
                cv2.putText(img, lbl, (pt1[0], max(20, pt1[1] - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

                # Simulate face blur on the head area (privacy rule enforcement)
                head_y2 = pt1[1] + int(0.25 * (pt2[1] - pt1[1]))
                head_roi = img[pt1[1]:head_y2, pt1[0]:pt2[0]]
                if head_roi.size > 0:
                    blurred = cv2.GaussianBlur(head_roi, (51, 51), 30)
                    img[pt1[1]:head_y2, pt1[0]:pt2[0]] = blurred

            elif cls_name == "helmet":
                cv2.rectangle(img, pt1, pt2, (0, 255, 0), 2)
                cv2.putText(img, f"helmet {obj['conf']:.2f}", (pt1[0], max(20, pt1[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            elif cls_name == "no_helmet":
                cv2.rectangle(img, pt1, pt2, (0, 0, 255), 2)
                cv2.putText(img, f"NO HELMET {obj['conf']:.2f}", (pt1[0], max(20, pt1[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
            elif cls_name == "vest":
                cv2.rectangle(img, pt1, pt2, (255, 255, 0), 2)
                cv2.putText(img, f"vest {obj['conf']:.2f}", (pt1[0], max(20, pt1[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

        # Timestamp and scenario overlay
        info_str = f"SiteSentinel Sim | {self.scenario.upper()} | Frame: {frame_dict['frame_id']} | t={frame_dict['ts']:.2f}s"
        cv2.putText(img, info_str, (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (244, 245, 246), 2)
        return img


def run_simulator(
    scenario: str = "compliant",
    fps: float = 25.0,
    duration: float = 30.0,
    mqtt_host: str = "localhost",
    mqtt_port: int = 1883,
    mqtt_topic: str = "sentinel/detections",
    use_mqtt: bool = True,
    out_video: Optional[str] = None,
    out_json: Optional[str] = None,
    stream_url: Optional[str] = "http://localhost:8000/api/stream/frame",
) -> None:
    generator = SyntheticScenarioGenerator(scenario=scenario, fps=fps)

    # Initialize MQTT client if requested
    client = None
    if use_mqtt:
        try:
            client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2, client_id="sentinel-sim")
            client.connect(mqtt_host, mqtt_port, keepalive=60)
            client.loop_start()
            print(f"[Sim] Connected to MQTT broker at {mqtt_host}:{mqtt_port}, streaming to {mqtt_topic}")
        except Exception as e:
            print(f"[Sim] Note: MQTT broker unavailable ({e}). Continuing in standalone streaming mode.")
            client = None

    # Video writer setup
    video_writer = None
    if out_video:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        Path(out_video).parent.mkdir(parents=True, exist_ok=True)
        video_writer = cv2.VideoWriter(out_video, fourcc, fps, (1920, 1080))
        print(f"[Sim] Writing annotated video to {out_video}")

    # JSONL file setup
    json_f = None
    if out_json:
        p = Path(out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        json_f = open(p, "w", encoding="utf-8")
        print(f"[Sim] Writing JSONL detections to {out_json}")

    total_frames = int(duration * fps) if duration > 0 else 1000000
    frame_interval = 1.0 / fps

    print(f"[Sim] Starting scenario '{scenario}' at {fps} FPS (total frames: {total_frames})...")
    start_wall_time = time.time()

    import urllib.request

    try:
        for f_idx in range(total_frames):
            t_sec = f_idx * frame_interval
            frame_data = generator.generate_frame(f_idx, t_sec)

            # Publish to MQTT
            if client:
                try:
                    client.publish(mqtt_topic, json.dumps(frame_data), qos=0)
                except Exception:
                    pass

            # Write JSON line
            if json_f:
                json_f.write(json.dumps(frame_data) + "\n")
                json_f.flush()

            # Render frame image if needed for video, stream, or relay
            frame_img = None
            if video_writer or stream_url:
                frame_img = generator.render_frame_image(frame_data)

            if video_writer and frame_img is not None:
                video_writer.write(frame_img)

            if stream_url and frame_img is not None:
                success, encoded = cv2.imencode(".jpg", frame_img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if success:
                    jpeg_bytes = encoded.tobytes()
                    try:
                        from sentinel.interfaces.api.app import state as api_state
                        if hasattr(api_state, "relay") and api_state.relay:
                            api_state.relay.update_jpeg(jpeg_bytes)
                    except Exception:
                        pass
                    try:
                        req = urllib.request.Request(
                            stream_url,
                            data=jpeg_bytes,
                            headers={"Content-Type": "image/jpeg"},
                            method="POST",
                        )
                        urllib.request.urlopen(req, timeout=0.08)
                    except Exception:
                        pass

            # Pacing to real-time FPS if running live
            if not out_video and not out_json:
                target_time = start_wall_time + (f_idx + 1) * frame_interval
                sleep_dur = target_time - time.time()
                if sleep_dur > 0:
                    time.sleep(sleep_dur)

    except KeyboardInterrupt:
        print("\n[Sim] Stopped by user.")
    finally:
        if client:
            client.loop_stop()
            client.disconnect()
        if video_writer:
            video_writer.release()
        if json_f:
            json_f.close()
        print(f"[Sim] Completed scenario '{scenario}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteSentinel Synthetic Detection Simulator")
    parser.add_argument("--scenario", choices=["compliant", "no_helmet", "restricted_entry", "danger_dwell", "crowd", "flicker"], default="compliant")
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--duration", type=float, default=30.0, help="Duration in seconds (0 for infinite)")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--mqtt-topic", default="sentinel/detections")
    parser.add_argument("--no-mqtt", action="store_true")
    parser.add_argument("--out-video", default=None, help="Path to write synthetic annotated MP4 video")
    parser.add_argument("--out-json", default=None, help="Path to write JSONL stream")
    parser.add_argument("--stream-url", default="http://localhost:8000/api/stream/frame", help="HTTP endpoint to push frames for live MJPEG streaming")
    parser.add_argument("--no-stream-http", action="store_true", help="Disable HTTP frame streaming")

    args = parser.parse_args()
    stream_url = None if args.no_stream_http else args.stream_url
    run_simulator(
        scenario=args.scenario,
        fps=args.fps,
        duration=args.duration,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_topic=args.mqtt_topic,
        use_mqtt=not args.no_mqtt,
        out_video=args.out_video,
        out_json=args.out_json,
        stream_url=stream_url,
    )


if __name__ == "__main__":
    main()
