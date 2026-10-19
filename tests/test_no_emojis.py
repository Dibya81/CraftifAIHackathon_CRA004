"""Test ensuring zero emojis exist anywhere in tracked text files and dashboard bundle."""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_emoji(ch: str) -> bool:
    """Detects emojis across standard Unicode emoji blocks and pictographs."""
    cp = ord(ch)
    # Emoticons, symbols, pictographs, transport/map, supplemental symbols
    if (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or (0x1F600 <= cp <= 0x1F64F):
        return True
    return False


def test_zero_emojis_in_tracked_repository_files():
    """Verify that zero emojis exist across all tracked repository text files."""
    repo_root = Path(__file__).resolve().parent.parent
    tracked = subprocess.check_output(["git", "ls-files"], cwd=repo_root, text=True).splitlines()

    violations = []
    ignored_binary_exts = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".tar.gz",
        ".zip",
    }

    for rel_path in tracked:
        target = repo_root / rel_path
        if not target.is_file() or target.suffix.lower() in ignored_binary_exts:
            continue

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for line_idx, line in enumerate(content.splitlines(), start=1):
            for col_idx, char in enumerate(line, start=1):
                if is_emoji(char):
                    violations.append(
                        f"{rel_path}:{line_idx}:{col_idx} emoji '{char}' (U+{ord(char):04X})"
                    )

    assert not violations, (
        f"Found {len(violations)} emoji(s) in tracked repository files:\n"
        + "\n".join(violations[:20])
    )


def test_zero_emojis_in_dashboard_dist_if_built():
    """If dashboard/dist exists, verify no emojis exist in bundled JS/CSS/HTML."""
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dashboard" / "dist"
    if not dist_dir.exists():
        return  # Dashboard bundle not built yet in this stage

    violations = []
    for file_path in dist_dir.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in {
            ".html",
            ".js",
            ".css",
            ".txt",
        }:
            continue
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for line_idx, line in enumerate(content.splitlines(), start=1):
            for col_idx, char in enumerate(line, start=1):
                if is_emoji(char):
                    violations.append(
                        f"{file_path.relative_to(repo_root)}:{line_idx}:{col_idx} emoji '{char}'"
                    )

    assert not violations, "Found emojis in dashboard build bundle:\n" + "\n".join(violations)
