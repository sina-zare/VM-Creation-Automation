#!/usr/bin/env python3
"""
Merge all per-job automation.*.log files into one automation.log,
sorted by timestamp.

Usage:
    python3 -m scripts.utility.log.merge_logs
"""

import json
import os
import sys
from pathlib import Path


project_dir = Path(os.environ["CI_PROJECT_DIR"])
log_files = sorted(project_dir.glob("automation.*.log"))

if not log_files:
    print("No per-job log files found to merge.")
    sys.exit(0)

lines = []
for f in log_files:
    lines.extend(f.read_text(encoding="utf-8").splitlines())


def sort_key(line: str) -> str:
    try:
        return json.loads(line).get("asctime", "")
    except json.JSONDecodeError:
        return ""


lines.sort(key=sort_key)

merged_path = project_dir / "automation.log"
merged_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Merged {len(log_files)} log files -> {merged_path} ({len(lines)} lines)")
