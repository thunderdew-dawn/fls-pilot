#!/usr/bin/env python3
"""CLI: analyze an audio file's tempo + key (offline, no FL).

python scripts/analyze_file.py <path-to-wav-or-mp3>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fl_studio_mcp.tools.audio import audio_analyze  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: analyze_file.py <path>")
        return 2
    path = sys.argv[1]
    if not os.path.isfile(path):
        print("file not found:", path)
        return 1
    print(json.dumps(audio_analyze(path), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
