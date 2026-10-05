#!/usr/bin/env python3
import json
import pathlib
import sys
from scripts.utility.log.logger import get_logger

logger = get_logger("scripts.utility.webpage.patch_report_ips")

ticket = sys.argv[1]
outputs_path = sys.argv[2]

report_path = pathlib.Path(f"reports/{ticket}/index.html")
if not report_path.exists():
    logger.error(
        f"report file not found",
        extra={
            "issue": ticket,
            "function": "patch_report_ips"
        }
    )
    sys.exit(f"ERROR: report file not found at {report_path.resolve()}")


html = report_path.read_text(encoding="utf-8")

data = json.loads(pathlib.Path(outputs_path).read_text())
vm_ips = data.get("vm_ips", {})

if not vm_ips:
    logger.error(
        f"vm_ips is empty in vm_outputs.json - nothing to patch",
        extra={
            "issue": ticket,
            "function": "patch_report_ips"
        }
    )
    sys.exit("ERROR: vm_ips is empty in vm_outputs.json - nothing to patch")

missing = []
patched = 0

for vm_name, ip in vm_ips.items():
    placeholder = f"{{PRIVATE_IP:{vm_name}}}"
    count_before = html.count(placeholder)

    if count_before == 0:
        missing.append((vm_name, placeholder))
        continue

    html = html.replace(placeholder, ip or "Pending")
    patched += count_before

report_path.write_text(html, encoding="utf-8")

if missing:
    print(f"Successfully patched {patched} occurrence(s).")
    print(f"WARNING: {len(missing)} placeholder(s) NOT found in {report_path}:")
    for vm_name, placeholder in missing:
        print(f"  - vm_name={vm_name!r} expected placeholder={placeholder!r}")
    # Show what IS in the file near "PRIVATE_IP" to help debug the mismatch
    for line in html.splitlines():
        if "PRIVATE_IP" in line:
            print(f"  actual line in file: {line.strip()!r}")
    sys.exit(1)

print(f"Patched {patched} IP(s) into {report_path} (verified)")
logger.info(
    f"Patched {patched} IP(s) into {report_path} (verified)",
    extra={
        "issue": ticket,
    }
)
