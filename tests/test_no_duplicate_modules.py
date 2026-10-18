"""Test enforcement against duplicate modules and shallow re-export stubs."""

from __future__ import annotations

import ast
from pathlib import Path


def test_no_known_duplicate_files():
    """Assert known duplicate modules have been eliminated."""
    root = Path(__file__).resolve().parent.parent

    # Defect 8: duplicate modules next to layered packages
    banned_root_modules = [
        "rules.py",
        "zones.py",
        "models.py",
        "evidence.py",
        "mqtt_client.py",
        "tracker_assoc.py",
        "incidents.py",
        "api.py",
    ]
    for mod in banned_root_modules:
        target = root / "src" / "sentinel" / mod
        assert not target.exists(), f"Duplicate module {target} must not exist in src/sentinel/ root."

    # Soak duplicate: tools/soak_test.py vs tools/soak.py
    assert not (root / "tools/soak_test.py").exists(), (
        "tools/soak_test.py must not exist. The canonical soak tool is tools/soak.py."
    )

    # Benchmark duplicate: tests/test_benchmark.py vs tests/perf/test_benchmarks.py
    assert not (root / "tests/test_benchmark.py").exists(), (
        "tests/test_benchmark.py must not exist. Performance benchmarks live in tests/perf/test_benchmarks.py."
    )

    # API test duplicate: tests/test_api_v1.py vs tests/test_api.py
    assert not (root / "tests/test_api_v1.py").exists(), (
        "tests/test_api_v1.py must not exist. The unified API test suite is tests/test_api.py."
    )


def test_no_shallow_reexport_files():
    """Assert no python file under 30 lines exists merely to shallowly re-export symbols without value."""
    root = Path(__file__).resolve().parent.parent
    src_dir = root / "src" / "sentinel"

    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        lines = [
            line.strip()
            for line in py_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if len(lines) < 30:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            has_defs = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                for node in tree.body
            )
            # If all top-level statements are just Imports and ImportFroms, it's a shallow re-export stub
            all_imports = all(
                isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr)) for node in tree.body
            )
            if all_imports and not has_defs:
                raise AssertionError(
                    f"Shallow re-export module found: {py_file.relative_to(root)} ({len(lines)} lines) "
                    "merely re-exports symbols without defining any functions or classes."
                )
