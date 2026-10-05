#!/usr/bin/env python3
"""
Posts a VM summary comment on a Jira ticket and transitions it to Closed.

Usage:
    python3 -m scripts.utility.jira.close_ticket <TICKET_KEY> <REPORT_HTML_PATH>

Env vars:
    JIRA_ADDR                     e.g. https://jira.abramad.com
    JIRA_TOKEN                    API token
    JIRA_CLOSE_TRANSITION_NAME    default: "Closed"
"""

import os
import sys
import traceback
from jira import JIRA
from bs4 import BeautifulSoup
from scripts.configs import error_string_summary, error_string_detail, JIRA_TOKEN, JIRA_ADDR, JIRA_CLOSE_TRANSITION_NAME, MATTERMOST_NOTIFY_WEBHOOK, JIRA_TICKET_KEY
from scripts.utility.mattermost.notifier import send_mattermost_message
from scripts.utility.log.logger import get_logger

logger = get_logger("scripts.utility.jira.close_ticket")


def parse_report(html_path):
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    servers = []
    current = None
    section = None

    for row in soup.find_all("tr"):
        cells = row.find_all("td")

        # Section header rows span both columns (colspan="2")
        if len(cells) == 1:
            header = cells[0].get_text(strip=True)
            if header == "General Information":
                if current:
                    servers.append(current)
                current = {"disks": []}
                section = "general"
            elif header == "Disk Information":
                section = "disk"
            continue

        if len(cells) != 2 or current is None:
            continue

        label = cells[0].get_text(strip=True)
        value = cells[1].get_text(strip=True)

        if section == "general":
            current[label] = value
        elif section == "disk":
            if label == "Disk":
                current["disks"].append({"Disk": value})
            elif label == "Size" and current["disks"]:
                current["disks"][-1]["Size"] = value

    if current:
        servers.append(current)
    return servers


GENERAL_FIELDS = ["Server Name", "CPU", "Memory", "Private IP", "Public IP", "URL"]
DISK_FIELDS = ["Server", "Disk", "Size"]


def clean(value):
    # Empty value -> "N/A", and make sure everything is text
    if value is None or value == "":
        return "N/A"
    text = str(value)
    # A "|" inside a value would break the table, so escape it
    return text.replace("|", "\\|")


def make_bold(text, destination):
    if destination == "jira":
        return "*" + text + "*"
    else:
        return "**" + text + "**"


def make_table(headers, rows, destination):
    lines = []

    # Header row: this is the only part that differs between Jira and Mattermost
    if destination == "jira":
        lines.append("|| " + " || ".join(headers) + " ||")
    else:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    # Data rows: same for both
    for row in rows:
        cells = []
        for value in row:
            cells.append(clean(value))
        lines.append("| " + " | ".join(cells) + " |")

    return lines


def build_comment_body(servers, ticket, destination):
    if destination not in ("jira", "mattermost"):
        raise ValueError(f"Unsupported destination: {destination!r}")

    # Titles differ per destination
    if destination == "jira":
        prefix = ""
        general_title = "General Specs"
        disk_title = "Disk Specs"
    else:
        prefix = "#### :white_check_mark: "
        general_title = ":desktop_computer: General Specs"
        disk_title = ":floppy_disk: Disk Specs"

    # Collect the rows for the first table
    general_rows = []
    for server in servers:
        row = []
        for field in GENERAL_FIELDS:
            row.append(server.get(field))
        general_rows.append(row)

    # Collect the rows for the disk table
    disk_rows = []
    for server in servers:
        for disk in server.get("disks", []):
            disk_rows.append([server.get("Server Name"), disk.get("Disk"), disk.get("Size")])

    # Put everything together
    lines = []
    lines.append(prefix + "VM provisioning complete for " + make_bold(ticket, destination) + ".")
    lines.append("---")
    lines.append("")

    lines.append(make_bold(general_title, destination))
    lines.append("")  # blank line before a table is required in Mattermost
    lines += make_table(GENERAL_FIELDS, general_rows, destination)

    lines.append("")
    lines.append(make_bold(disk_title, destination))
    lines.append("")  # blank line again
    lines += make_table(DISK_FIELDS, disk_rows, destination)
    lines.append("---")

    return "\n".join(lines)



try:
    if len(sys.argv) != 3:
        logger.error(
            f"Usage: close_ticket.py <TICKET_KEY> <REPORT_HTML_PATH>",
            extra={
                "issue": JIRA_TICKET_KEY,
            }
        )
        raise SystemExit("Usage: close_ticket.py <TICKET_KEY> <REPORT_HTML_PATH>")


    ticket, report_path = sys.argv[1], sys.argv[2]
    jira_addr = os.environ["JIRA_ADDR"]
    jira_token = os.environ["JIRA_TOKEN"]
    transition_name = JIRA_CLOSE_TRANSITION_NAME

    servers = parse_report(report_path)
    if not servers:
        logger.error(
            f"No server data found in {report_path}",
            extra={
                "issue": ticket,
            }
        )
        raise SystemExit(f"No server data found in {report_path}")

    body_jira = build_comment_body(servers, ticket, 'jira')
    body_mattermost = build_comment_body(servers, ticket, 'mattermost')

    send_mattermost_message(
    webhook_url=MATTERMOST_NOTIFY_WEBHOOK,
    ticket = JIRA_TICKET_KEY,
    message=body_mattermost,
    username="VM Automation",
    icon_emoji=":robot_face:",
    )

    jira = JIRA(server=jira_addr, token_auth=jira_token)
    jira.add_comment(ticket, body_jira)
    jira.transition_issue(ticket, transition_name)

    print(f"Commented and closed {ticket}")
    logger.info(
            f"Commented and closed {ticket}",
            extra={
                "issue": ticket,
            }
        )

except Exception as err:

        error_string_summary += f"{type(err).__name__}: {err}"

        # Get the traceback and extract the last traceback frame
        tb = traceback.extract_tb(err.__traceback__)
        last_call = tb[-1]  # the last traceback frame, where the exception occurred
        error_string_detail += f"Error occurred in line {last_call.lineno}: {last_call.line}"
        print(f"Script failed: {error_string_summary}\n{error_string_detail}")

        logger.error(
            f"close_ticket() failed",
            extra={
                "issue": ticket,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise