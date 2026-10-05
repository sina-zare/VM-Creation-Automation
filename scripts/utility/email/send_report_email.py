#!/usr/bin/env python3

import json
import pathlib
import sys
from scripts.configs import *
from scripts.utility.log.logger import get_logger
from scripts.utility.functions.data_validators import send_anonymous_email

logger = get_logger(__name__)

def collect_recipients(tfvars: dict) -> list[str]:
    emails = set()

    for user in tfvars.get("ad_info", {}).get("users", []):
        email = user.get("email")
        if email:
            emails.add(email)

    return sorted(emails)


if len(sys.argv) != 3:
    logger.error("usage: send_report_email.py <ticket_key> <tfvars_path>")
    sys.exit("usage: send_report_email.py <ticket_key> <tfvars_path>")

ticket = sys.argv[1]
tfvars_path = pathlib.Path(sys.argv[2])


report_path = pathlib.Path(f"reports/{ticket}/index.html")
if not report_path.exists():
    logger.error(
        "report not found at",
        extra={
            "issue": ticket,
        }
    )
    sys.exit(f"ERROR: report not found at {report_path.resolve()}")

html_msg = report_path.read_text(encoding="utf-8")


if "{PRIVATE_IP:" in html_msg:
    # Safety net: don't email out a report that still has an unfilled placeholder in it
    logger.error(
           f"{report_path} still contains an unfilled {{PRIVATE_IP:...}} placeholder - refusing to send",
            extra={
                "issue": ticket,
            }
        )
    sys.exit(
        f"ERROR: {report_path} still contains an unfilled "
        f"{{PRIVATE_IP:...}} placeholder - refusing to send"
    )


tfvars = json.loads(tfvars_path.read_text(encoding="utf-8"))
recipients = collect_recipients(tfvars)

if not recipients:
    logger.error(
        "no agent/deployer emails found in tfvars - refusing to send with empty recipient list",
        extra={
            "issue": ticket,
        }
    )
    sys.exit("ERROR: no agent/deployer emails found in tfvars - refusing to send with empty recipient list")


print(f"Sending report for {ticket} to: {recipients}")

send_anonymous_email(
    jira_issue=ticket,
    mail_server=MAIL_SERVER,
    from_email="Automation@abramad.com",
    to_email=recipients,
    cc_email=CC_EMAIL,
    subject=f"Abramad Customers VM Report - {ticket}",
    html_message=html_msg,
    direction="rtl",
)

print("Email sent.")
