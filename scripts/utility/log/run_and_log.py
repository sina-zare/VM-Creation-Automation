#!/usr/bin/env python3
"""
Run a command, stream its output to the console live, and log the
full output as a single JSON record once the command finishes.

Usage:
    python3 -m scripts.utility.log.run_and_log <ticket_no> <source> -- <command...>
"""

import re
import subprocess
import sys
from scripts.utility.log.logger import get_logger

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


args = sys.argv[1:]
sep = args.index("--")
ticket, source = args[0], args[1]
cmd = args[sep + 1 :]

logger = get_logger(f"scripts.utility.log.run_and_log.{source}")

proc = subprocess.Popen(
    ["stdbuf", "-oL", "-eL", *cmd],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

collected: list[str] = []
interrupted = False

try:
    for raw_line in proc.stdout:
        clean = strip_ansi(raw_line.rstrip())
        print(clean)
        if clean:
            collected.append(clean)
except KeyboardInterrupt:
    interrupted = True
    raise
finally:
    proc.wait()

    message = "\n".join(collected) if collected else "(no output captured)"
    if interrupted:
        message += "\n\n[run_and_log: interrupted before command finished]"

    if proc.returncode == 0:
        logger.info(
        message,
        extra={
            "issue": ticket,
            "source": source,
            "exit_code": proc.returncode,
            "line_count": len(collected),
        },
        )
        
    else:
        logger.info(
        message,
        extra={
            "issue": ticket,
            "source": source,
            "exit_code": proc.returncode,
            "line_count": len(collected),
        },
        )
    

sys.exit(proc.returncode)
