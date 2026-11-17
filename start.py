#!/usr/bin/env python3
"""Start the local client directly from a checkout. No pip install required."""

import sys
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit("Agent Connect requires Python 3.11 or newer.")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from iteraconnect.cli import main  # noqa: E402

raise SystemExit(main(["app", "--settings", str(ROOT / "agent-connect.local.toml"), *sys.argv[1:]]))
