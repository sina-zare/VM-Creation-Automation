#!/usr/bin/env python3

import logging
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from zoneinfo import ZoneInfo

import jdatetime
from pythonjsonlogger import jsonlogger

from scripts.configs import LOG_FILE


class TehranJalaliJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter with Tehran time converted to Jalali."""

    def formatTime(self, record, datefmt=None):
        tehran_time = datetime.fromtimestamp(
            record.created,
            tz=ZoneInfo("Asia/Tehran"),
        )
        jalali_time = jdatetime.datetime.fromgregorian(
            datetime=tehran_time,
        )
        
        return jalali_time.strftime("%Y-%m-%d %H:%M:%S")

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["ts"] = datetime.fromtimestamp(
            record.created,
            tz=timezone.utc,
        ).isoformat()


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger.

    Call from other modules with:

        logger = get_logger(__name__)

    The module name will automatically appear in the
    JSON log as the "name" field.

    Example:

        scripts.data_fetcher
        scripts.utility.functions.data_validators
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Prevent duplicate handlers if get_logger() is called multiple times for the same logger.
    if logger.handlers:
        return logger

    handler = TimedRotatingFileHandler(
        filename=LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )

    formatter = TehranJalaliJsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s %(issue)s %(funcName)s",
    json_ensure_ascii=False,
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_cli():
    """
    Command-line logging.

    Usage:

        python3 -m scripts.utility.log.logger \
            SERVICEDESK-123 \
            "Terraform apply started"
    """

    if len(sys.argv) < 3:
        print(
            "Usage: python3 -m scripts.utility.log.logger "
            "<ticket_no> <message>",
            file=sys.stderr,
        )
        sys.exit(1)

    ticket = sys.argv[1]
    message = " ".join(sys.argv[2:])

    logger = get_logger(__name__)

    logger.info(
        message,
        extra={
            "issue": ticket,
        },
    )


if __name__ == "__main__":
    log_cli()




### How to use it from other modules
"""
For example, in data_fetcher.py:

from scripts.utility.log.logger import get_logger

logger = get_logger(__name__)

logger.info(
    "Fetching Jira ticket",
    extra={
        "issue": ticket_no,
        "function": "fetch_data",
    },
)

If the module is: scripts/data_fetcher.py
the JSON will contain:
{
  "asctime": "1405-06-29 10:14:32",
  "levelname": "INFO",
  "name": "scripts.data_fetcher",
  "message": "Fetching Jira ticket",
  "issue": "SERVICEDESK-123",
  "function": "fetch_data"
}
"""