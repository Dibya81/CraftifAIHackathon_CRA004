# Evaluation harness
Ground truth is a JSON list of intervals: `{"type": "NO_HELMET", "start_s": 12.0, "end_s": 20.5, "track": "A"}`.
An incident counts as a true positive if it fires inside a ground-truth interval; latency is fire time minus interval start.
