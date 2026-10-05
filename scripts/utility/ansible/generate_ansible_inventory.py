#!/usr/bin/env python3

import json
import yaml
from pathlib import Path
from scripts.utility.log.logger import get_logger

logger = get_logger("scripts.utility.ansible.generate_inventory")

TFVARS_FILE = "vms.tfvars.json"
OUTPUTS_FILE = "vm_outputs.json"
INVENTORY_FILE = "ansible/inventory/hosts.yml"


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


tfvars = load_json(TFVARS_FILE)
outputs = load_json(OUTPUTS_FILE)
vm_ips = outputs.get("vm_ips", {})

inventory = {
    "all": {
        "children": {
            "domain_controllers": {
                "vars": {
                    "ansible_connection": "winrm",
                    "ansible_port": 5985,
                    "ansible_user": "{{ lookup('env', 'AD_ANSIBLE_USER') }}",
                    "ansible_password": "{{ lookup('env', 'AD_ANSIBLE_PASSWORD') }}",
                    "ansible_winrm_transport": "ntlm",
                    "ansible_winrm_server_cert_validation": "ignore"
                },
                "hosts": {
                    "dc01": {
                        "ansible_host": "{{ lookup('env', 'AD_SERVER') }}"
                    }
                }
            },

            "windows_clients": {
                "vars": {
                    "ansible_connection": "winrm",
                    "ansible_port": 5985,
                    "ansible_user": "{{ lookup('env', 'WINDOWS_ANSIBLE_USER') }}",
                    "ansible_password": "{{ lookup('env', 'WINDOWS_ANSIBLE_PASSWORD') }}",
                    "ansible_winrm_transport": "ntlm",
                    "ansible_winrm_server_cert_validation": "ignore"
                },
                "hosts": {}
            },

            "linux_clients": {
                "vars": {
                    "ansible_connection": "ssh",
                    "ansible_port": 22,
                    "ansible_user": "{{ lookup('env', 'LINUX_ANSIBLE_USER') }}",
                    "ansible_private_key_file": "{{ lookup('env', 'LINUX_SSH_PRIVATE_KEY') }}"
                },
                "hosts": {}
            }
        }
    }
}


for vm_name, vm in tfvars["vms"].items():

    os_type = vm.get("os_type", "").lower()

    # Ignore unsupported OS types
    if os_type not in ("windows", "linux"):
        continue

    ip = vm_ips.get(vm_name)
    vm_issue = vm.get("custom_attrs", {}).get("Creation Ticket ID")

    if not ip:
        logger.error(
            "No Terraform Private IP found for VM",
            extra={
                "issue": vm_issue,
                "vm": vm_name,
            }
        )
        raise RuntimeError(
            f"No Terraform Private IP found for {os_type} VM '{vm_name}'"
        )

    if os_type == "windows":
        inventory["all"]["children"]["windows_clients"]["hosts"][vm_name] = {
            "ansible_host": ip,
            "zabbix_server": vm.get("zabbix_server")
        }

    elif os_type == "linux":
        inventory["all"]["children"]["linux_clients"]["hosts"][vm_name] = {
            "ansible_host": ip
        }


Path(INVENTORY_FILE).parent.mkdir(parents=True, exist_ok=True)

with open(INVENTORY_FILE, "w", encoding="utf-8") as fh:
    yaml.safe_dump(
        inventory,
        fh,
        sort_keys=False,
        default_flow_style=False
    )

print(f"Inventory written to {INVENTORY_FILE}")

logger.info(
    "Inventory written to %s",
    INVENTORY_FILE,
    extra={
        "issue": vm_issue
    }
)