"""SiteSentinel Stream Capture Tool.

Captures raw MQTT detection messages (or tails JSON files) and persists them
into a timestamped NDJSON capture with a metadata header.

Usage:
  python tools/capture_stream.py --output tests/fixtures/pipegen_real_capture.ndjson --duration 10
  python tools/capture_stream.py --source file --file /path/to/stream.jsonl --output capture.ndjson
"""

from __future__ import annotations

import argparse
import datetime
import json
import signal
import sys
import time
from pathlib import Path

# Ensure project root in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sentinel.config import load_sentinel_config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture raw perception stream to NDJSON.")
    parser.add_argument("--source", choices=["mqtt", "file"], default="mqtt", help="Stream source")
    parser.add_argument("--file", type=str, default=None, help="Input file path when source=file")
    parser.add_argument("--host", type=str, default=None, help="MQTT host")
    parser.add_argument("--port", type=int, default=None, help="MQTT port")
    parser.add_argument("--topic", type=str, default=None, help="MQTT topic to subscribe to")
    parser.add_argument("--output", type=str, default=None, help="Output NDJSON file path")
    parser.add_argument("--count", type=int, default=0, help="Stop after capturing N frames (0 for timed/infinite)")
    parser.add_argument("--duration", type=float, default=10.0, help="Capture duration in seconds (0 for manual stop)")
    args = parser.parse_args()

    cfg = load_sentinel_config()
    host = args.host or cfg.mqtt.host
    port = args.port or cfg.mqtt.port
    topic = args.topic or cfg.mqtt.detections_topic

    if args.output:
        out_path = Path(args.output)
    else:
        now_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(f"tests/fixtures/captures/capture_{now_ts}.ndjson")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = {
        "_sentinel_capture_header": True,
        "tool": "tools/capture_stream.py",
        "version": "0.1.0",
        "source": f"mqtt://{host}:{port}/{topic}" if args.source == "mqtt" else f"file://{args.file}",
        "topic": topic if args.source == "mqtt" else None,
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": "Raw stream capture for deterministic replay and test fixtures",
    }

    frames_captured = 0
    stop_requested = False

    def sig_handler(sig, frame):
        nonlocal stop_requested
        print("\nStopping capture...")
        stop_requested = True

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    print("SiteSentinel Stream Capture")
    print(f"Source: {header['source']}")
    print(f"Output: {out_path}")
    print(f"Limit: {args.count} frames or {args.duration} seconds (Ctrl+C to stop)")

    with open(out_path, "w", encoding="utf-8") as out_f:
        out_f.write(json.dumps(header) + "\n")
        out_f.flush()

        start_time = time.time()

        if args.source == "file":
            in_file = Path(args.file)
            if not in_file.exists():
                print(f"ERROR: Input file {in_file} not found.", file=sys.stderr)
                sys.exit(1)
            with open(in_file, "r", encoding="utf-8") as in_f:
                for line in in_f:
                    if stop_requested:
                        break
                    line_clean = line.strip()
                    if not line_clean or "_sentinel_capture_header" in line_clean:
                        continue
                    out_f.write(line_clean + "\n")
                    frames_captured += 1
                    if args.count > 0 and frames_captured >= args.count:
                        break
        else:
            # MQTT Capture
            import paho.mqtt.client as mqtt_client

            def on_message(client, userdata, msg):
                nonlocal frames_captured
                try:
                    payload_str = msg.payload.decode("utf-8", errors="replace").strip()
                    if payload_str:
                        out_f.write(payload_str + "\n")
                        out_f.flush()
                        frames_captured += 1
                        if frames_captured % 25 == 0:
                            print(f"Captured {frames_captured} frames...")
                except Exception as e:
                    print(f"Warning: error writing message: {e}", file=sys.stderr)

            client = mqtt_client.Client(client_id=f"sentinel-capture-{int(time.time())}")
            client.on_message = on_message
            try:
                client.connect(host, port, 60)
                client.subscribe(topic)
                client.loop_start()

                while not stop_requested:
                    time.sleep(0.1)
                    elapsed = time.time() - start_time
                    if args.duration > 0 and elapsed >= args.duration:
                        break
                    if args.count > 0 and frames_captured >= args.count:
                        break
                client.loop_stop()
                client.disconnect()
            except Exception as ex:
                print(f"MQTT connection failed ({host}:{port}): {ex}", file=sys.stderr)
                print("Falling back or exiting.")

    print(f"Capture completed: {frames_captured} frames written to {out_path}")


if __name__ == "__main__":
    main()
