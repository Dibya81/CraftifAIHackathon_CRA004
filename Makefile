PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
RUFF ?= $(shell if [ -f .venv/bin/ruff ]; then echo .venv/bin/ruff; else echo ruff; fi)
MYPY ?= $(shell if [ -f .venv/bin/mypy ]; then echo .venv/bin/mypy; else echo mypy; fi)
PYTEST ?= $(shell if [ -f .venv/bin/pytest ]; then echo .venv/bin/pytest; else echo pytest; fi)

.PHONY: all install test lint format sim demo eval report test-privacy submission clean

all: lint test

install:
	@if [ ! -d .venv ]; then python3 -m venv .venv; fi
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(RUFF) check src tests
	$(MYPY) src

format:
	$(RUFF) format src tests
	$(RUFF) check --fix src tests

test:
	$(PYTEST) -v --durations=10
	npm --prefix dashboard test

test-dashboard:
	npm --prefix dashboard test

build-dashboard:
	npm --prefix dashboard run build

sim:
	$(PYTHON) tools/simulate.py --scenario compliant --fps 25

demo:
	./scripts/run_demo.sh --sim

eval:
	$(PYTHON) eval/evaluate.py --clip data/test_clips/site01.mp4 --labels data/labelled/site01.json

report:
	$(PYTHON) tools/engine_report.py

test-privacy:
	$(PYTHON) tools/privacy_audit.py --dir evidence

submission:
	$(PYTHON) tools/make_submission.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache
