#!/usr/bin/env python3

import traceback
from scripts.utility.log.logger import get_logger
from scripts.configs import *
import pynetbox

logger = get_logger(__name__)

"""
Find the most-free public prefix in NetBox for a given scope (e.g. "me", "vanak"),
and reserve the next available IP address from it.

Requires:
    pip install pynetbox

Env vars:
    NETBOX_URL    - e.g. https://netbox.abramad.com
    NETBOX_TOKEN  - API token with read on prefixes, write on ip-addresses
"""


def get_client():
    url = NETBOX_URL
    token = NETBOX_TOKEN
    if not url or not token:
        raise ValueError(
                    f"ERROR: NETBOX_URL and NETBOX_TOKEN must be set as environment variables."
                )
    return pynetbox.api(url, token=token)


def find_best_prefix(nb, scope: str, target: str, jira_issue):
    """
    Return the public prefix matching `scope` with the most available IPs.
    Assumes prefixes have custom fields: cf_public (bool) and cf_scope (str/select).
    id_scope-ts-label id_cf_Public-ts-label
    """
    try:
        candidates = nb.ipam.prefixes.filter(cf_Public=True, cf_Target=target ,site=scope)

        best_prefix = None
        best_free_count = -1

        for prefix in candidates:
            total = prefix.prefix.split("/")
            
            try:
                available = nb.ipam.prefixes.get(prefix.id).available_ips.list(limit=0)
                free_count = len(available)
            except Exception:
                # Fallback: use utilization field to estimate, if available_ips call fails
                free_count = 0

            logger.info(
                f"Prefix {prefix.prefix} (id={prefix.id}) scope={scope} -> {free_count} free IPs",
                extra={
                "issue": jira_issue.key,
                "Prefix": prefix.prefix,
                "scope": scope,
                "target": target,
                "free_ips": free_count
                }
            )

            if free_count > best_free_count:
                best_free_count = free_count
                best_prefix = prefix

        if best_prefix is None or best_free_count <= 0:
            raise ValueError(
                    f"ERROR: No public prefix with free IPs found for scope '{scope}' and target '{target}'."
                )

        logger.info(f"Selected prefix {best_prefix}")
        return best_prefix, best_free_count
    
    except Exception as err:
        global error_string_detail
        global error_string_summary
        global success
        
        success = False
        error_string_summary += f"{type(err).__name__}: {err}"

        # Get the traceback and extract the last traceback frame
        tb = traceback.extract_tb(err.__traceback__)
        last_call = tb[-1]  # the last traceback frame, where the exception occurred
        error_string_detail += f"Error occurred in line {last_call.lineno}: {last_call.line}"
        print(f"Script failed: {error_string_summary}\n{error_string_detail}")

        logger.error(
            f"find_best_prefix() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise

def reserve_ip(nb, prefix, description: str, jira_issue):
    """
    Reserve (create) the next available IP address inside the given prefix,
    unless an IP with this exact description already exists (e.g. from a
    previous failed pipeline run for the same ticket) — in that case, return
    the existing record instead of allocating a new one.
    """
    try:

        # Idempotency check: has this ticket/description already reserved an IP?
        existing = list(nb.ipam.ip_addresses.filter(description=description))

        if existing:
            if len(existing) > 1:
                logger.warning(
                    f"Multiple existing IPs found for description '{description}', "
                    f"using the first one: {[ip.address for ip in existing]}",
                    extra={
                        "issue": jira_issue.key,
                        "description": description,
                        "candidates": [str(ip.address) for ip in existing],
                    }
                )

            existing_ip = existing[0]
            logger.info(
                f"Reusing existing IP reservation: {existing_ip.address} (id={existing_ip.id})",
                extra={
                    "issue": jira_issue.key,
                    "IP": str(existing_ip.address),
                    "description": description,
                    "reused": True,
                }
            )
            return existing_ip
        
        # No existing record — proceed with a fresh reservation
        available_ips_endpoint = nb.ipam.prefixes.get(prefix.id).available_ips
        new_ip = available_ips_endpoint.create({
            "description": description,
            "status": "active",
        })

        logger.info(
                f"Reserved IP: {new_ip.address} (id={new_ip.id})",
                extra={
                "issue": jira_issue.key,
                "IP": new_ip.address
                }
            )
        return new_ip
    
    except Exception as err:
        global error_string_detail
        global error_string_summary
        global success
        
        success = False
        error_string_summary += f"{type(err).__name__}: {err}"

        # Get the traceback and extract the last traceback frame
        tb = traceback.extract_tb(err.__traceback__)
        last_call = tb[-1]  # the last traceback frame, where the exception occurred
        error_string_detail += f"Error occurred in line {last_call.lineno}: {last_call.line}"
        print(f"Script failed: {error_string_summary}\n{error_string_detail}")

        logger.error(
            f"reserve_ip() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise

def delete_ip(nb, ip: str, jira_issue):
    """
    Delete an IP address record from NetBox given its address (with or without CIDR).
    """
    try:
        # available_ips lookups need CIDR notation, but ip-addresses.get() wants just the address
        # or full CIDR - pynetbox's .get(address=...) does a filter+match, so pass it as-is
        # and fall back to appending /32 if no match is found and no prefix was given.
        record = nb.ipam.ip_addresses.get(address=ip)

        if record is None and "/" not in ip:
            record = nb.ipam.ip_addresses.get(address=f"{ip}/32")

        if record is None:
            raise ValueError(f"ERROR: No IP address record found for '{ip}'.")

        deleted = record.delete()
        if not deleted:
            raise ValueError(f"ERROR: NetBox refused to delete IP record for '{ip}'.")

        print(f"Deleted IP record: {ip}")
        logger.info(
            f"Deleted IP record",
            extra={
                "issue": jira_issue.key,
                "ip": ip,
            }
        )
        return True

    except Exception as err:
        global error_string_detail
        global error_string_summary
        global success

        success = False
        error_string_summary += f"{type(err).__name__}: {err}"

        tb = traceback.extract_tb(err.__traceback__)
        last_call = tb[-1]
        error_string_detail += f"Error occurred in line {last_call.lineno}: {last_call.line}"
        print(f"Script failed: {error_string_summary}\n{error_string_detail}")

        logger.error(
            f"delete_ip() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


# nb = get_client()
# scope = "vanak"
# prefix, free_count = find_best_prefix(nb, scope)
# print(f"Selected prefix {prefix.prefix} (id={prefix.id}) with {free_count} free IPs")

#delete_ip(nb, "78.31.232.12")
# new_ip = reserve_ip(nb, prefix, 'sina')
# ip_only = str(new_ip.address).split("/")[0]
#
# print(f"Reserved IP: {new_ip.address} (id={new_ip.id})")
# print(ip_only)
