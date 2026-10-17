"""Offline evaluation: run a labelled test clip through the pipeline and rule engine.

Outputs precision, recall and alert latency per rule to reports/eval_<date>.json and .md.
Usage: python eval/evaluate.py --clip data/test_clips/site01.mp4 --labels data/labelled/site01.json
"""
# TODO: load ground-truth incident intervals, replay detections, match incidents, compute metrics
