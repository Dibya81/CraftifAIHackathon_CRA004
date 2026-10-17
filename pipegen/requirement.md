# PipeGen Requirement (frozen text for stage 1)
Detect people, hard hats and high-visibility vests from a site camera. Track people across
frames, blur faces, and publish per-frame detections to MQTT and JSON. Output an annotated
RTSP stream. Run on an NVIDIA GPU with TensorRT.

Keep the generated export in `pipegen/export/` untouched. Only consume its outputs.
