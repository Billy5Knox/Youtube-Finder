"""Repo-root entry point for the YouTube Finder supervisor.

Adds backend/ to sys.path so we can `import app.launcher` cleanly,
then delegates to its main().
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.launcher import main

if __name__ == "__main__":
    sys.exit(main(REPO_ROOT))
