#!/usr/bin/env python3

import json
import sys
import time
from pathlib import Path
from scripts.configs import MATTERMOST_NOTIFY_WEBHOOK, JIRA_TICKET_KEY, JIRA_TARGET_PRODUCTLINE, PUSHGATEWAY_URL
from scripts.utility.mattermost.notifier import send_mattermost_message
from scripts.utility.pipeline.send_time_metrics import push_time_metrics
import os
import re


PROJECT_DIR = Path(os.environ.get("CI_PROJECT_DIR", "."))
TIMING_DIR = PROJECT_DIR / "pipeline_timing"


def load_timing() -> dict:
    """Merge every per-mark file in TIMING_DIR into one dict."""
    if not TIMING_DIR.exists():
        return {}

    data = {}
    for f in TIMING_DIR.glob("*.json"):
        with f.open("r", encoding="utf-8") as fh:
            data.update(json.load(fh))
    return data


def mark(name: str) -> None:
    """Record the current Unix timestamp under its own uniquely-named file."""
    TIMING_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.time()

    with (TIMING_DIR / f"{name}.json").open("w", encoding="utf-8") as f:
        json.dump({name: ts}, f, indent=2)

    print(f"{name}={ts}")


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def build_summary(data: dict) -> str:
    """Build a human-readable pipeline timing summary, tolerating missing stages."""
    pipeline_start = data.get("pipeline_start")
    log_shipping_end = data.get("log_shipping_end")

    if pipeline_start is None or log_shipping_end is None:
        return "Total time: unavailable (missing pipeline_start/log_shipping_end)"

    stages = [
        ("reconnaissance", "pipeline_start", "reconnaissance_end"),
        ("terraform", "reconnaissance_end", "terraform_end"),
        ("ansible", "terraform_end", "ansible_end"),
        ("dns", "ansible_end", "dns_end"),
        ("zabbix", "dns_end", "zabbix_end"),
        ("reporting", "reporting_start", "reporting_end"),
        ("log_and_metric_shipping", "reporting_end", "log_shipping_end")
    ]

    lines = [f"Total time:     {format_duration(log_shipping_end - pipeline_start)}"]
    for name, start_key, end_key in stages:
        start, end = data.get(start_key), data.get(end_key)
        if start is None or end is None:
            lines.append(f"{name}:{' ' * max(1, 15 - len(name))}skipped")
        else:
            lines.append(f"{name}:{' ' * max(1, 15 - len(name))}{format_duration(end - start)}")

    return "\n".join(lines)


def timing_to_markdown(raw: str) -> str:
    total = None
    rows = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("total time"):
            total = line.split(":", 1)[1].strip()
            continue
        m = re.match(r"^([\w\- ]+?)\s*:\s*(.+)$", line)
        if m:
            rows.append((m.group(1).strip(), m.group(2).strip()))

    table = ["| Stage | Duration |", "|:------|---------:|"]
    table += [f"| {name} | {duration} |" for name, duration in rows]
    if total:
        table.append(f"| **Total** | **{total}** |")
    return "\n".join(table)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.utility.pipeline.timing <start|mark|summary> [name]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        mark("pipeline_start")

    elif command == "mark":
        if len(sys.argv) != 3:
            print("Usage: timing.py mark <name>")
            sys.exit(1)
        mark(sys.argv[2])

    elif command == "summary":
        data = load_timing()
        time_msg = build_summary(data)
        print(time_msg)

        msg = "\n".join([
            f"#### :alarm_clock: Time Table Report for **{JIRA_TICKET_KEY}**",
            "---"
            "",
            timing_to_markdown(time_msg),
            "---"
        ])

        send_mattermost_message(
            webhook_url=MATTERMOST_NOTIFY_WEBHOOK,
            ticket=JIRA_TICKET_KEY,
            message=msg,
            username="VM Automation",
            icon_emoji=":alarm_clock:",
        )

        push_time_metrics(
            data=data, 
            product_line=JIRA_TARGET_PRODUCTLINE, 
            gateway=PUSHGATEWAY_URL)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()