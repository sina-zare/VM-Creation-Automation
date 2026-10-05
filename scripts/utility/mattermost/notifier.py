#!/usr/bin/env python3

from scripts.configs import JIRA_TICKET_KEY
from scripts.utility.log.logger import get_logger
from typing import Optional
import traceback
import requests
import sys
logger = get_logger("scripts.utility.mattermost.notifier")


def send_mattermost_message(
    webhook_url: str,
    ticket: str,
    message: str,
    *,
    username: Optional[str] = None,
    channel: Optional[str] = None,
    icon_url: Optional[str] = None,
    icon_emoji: Optional[str] = None,
    timeout: int = 30,
) -> bool:

    payload = {"text": message}

    if username:
        payload["username"] = username
    
    if channel:
        payload["channel"] = channel # If webhook permits

    if icon_url:
        payload["icon_url"] = icon_url

    if icon_emoji:
        payload["icon_emoji"] = icon_emoji

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=timeout,
        )

        response.raise_for_status()

        logger.info(
            f"mattermost message sent",
            extra={
                "issue": ticket,
            }
        )
        return True


    except Exception as err:

        error_string_summary = f"{type(err).__name__}: {err}"

        # Get the traceback and extract the last traceback frame
        tb = traceback.extract_tb(err.__traceback__)
        last_call = tb[-1]  # the last traceback frame, where the exception occurred
        error_string_detail = f"Error occurred in line {last_call.lineno}: {last_call.line}"
        print(f"Script failed: {error_string_summary}\n{error_string_detail}")

        logger.error(
            f"notifier() failed",
            extra={
                "issue": ticket,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise
    

if __name__ == "__main__":

    webhook = sys.argv[1]
    msg = sys.argv[2]

    send_mattermost_message(
    webhook_url=webhook,
    ticket=JIRA_TICKET_KEY,
    message=msg,
    username="VM Automation",
    icon_emoji=":robot_face:",
    )


'''
# Usage

send_mattermost_message(
    webhook_url="https://mattermost.example.com/hooks/xxxxxxxx",
    ticket=JIRA_TICKET_KEY,
    message="""
## VM Provisioning Report

**Customer:** Leon

### Created VMs

| VM | IP |
|----|----|
| VSP-Leon | 10.10.10.10 |
| VIA-Leon | 10.10.10.11 |

:white_check_mark: Provisioning completed successfully.
""",
    username="VM Automation",
    icon_emoji=":robot_face:",
    channel="vm-provisioning",
)
'''