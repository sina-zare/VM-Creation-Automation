#!/usr/bin/env python3

import sys
import json
import time
import dns.resolver
from scripts.configs import JIRA_TICKET_KEY
from scripts.utility.log.logger import get_logger

logger = get_logger("scripts.utility.dns.dns_resolver")

def dns_resolver(hostname: str, dns_server: str) -> bool:
    """
    Resolve a hostname using the specified DNS server(s).

    Args:
        hostname: Hostname to resolve.
        dns_server: Comma-separated DNS server IP addresses.

    Returns:
        True if the hostname resolves successfully, otherwise False.
    """

    result = {
        "success": False,
        "ip": "",
        "response_time_ms": 0,
        "error": "",
    }

    resolver = dns.resolver.Resolver()
    resolver.nameservers = dns_server.split(",")

    start = time.perf_counter()

    try:
        answer = resolver.resolve(hostname, "A")

        result["success"] = True
        result["ip"] = answer[0].to_text()

    except Exception as exc:
        result["error"] = str(exc)

    finally:
        result["response_time_ms"] = round(
            (time.perf_counter() - start) * 1000,
            2,
        )


    if result["success"]:
        logger.info(
            "Hostname resolved successfully.",
            extra={
                "issue": JIRA_TICKET_KEY,
                "hostname": hostname,
                "dns_server": dns_server,
                "result": result,
            },
        )
    else:
        logger.error(
            "Hostname could not be resolved.",
            extra={
                "issue": JIRA_TICKET_KEY,
                "hostname": hostname,
                "dns_server": dns_server,
                "result": result,
            },
        )

    print(json.dumps(result))

    return result["success"]