#!/usr/bin/env python3

from scripts.configs import VNK_CUSTOMERZABBIX_URL, ME_CUSTOMERZABBIX_URL, ME_CUSTOMERZABBIX_TOKEN, VNK_CUSTOMERZABBIX_TOKEN, JIRA_TICKET_KEY
from scripts.utility.log.logger import get_logger
from pyzabbix import ZabbixAPI
from textwrap import dedent
import traceback
import json

logger = get_logger("scripts.utility.zabbix.add_url_monitoring")


def zabbix_node_adder(url, token, hosts_dict, template_list, host_group_list, tag_list):

    try:
        #  host_dict involves key values, that the values are a list consisting of 3 indexes ['Host Name', 'IP Address', 'Description']
        template_ids = {}
        host_group_ids = {}

        # Connect to Zabbix API
        zapi = ZabbixAPI(url)
        #zapi.login(username, password)

        zapi.session.headers.update({
            "Authorization": f"Bearer {token}"
        })

        # Step 1: Get the Template ID
        for template_name in template_list:
            template = zapi.template.get(filter={"host": template_name})
            if not template:
                raise Exception(f"Template '{template_name}' not found.")
            template_ids[template_name] = template[0]["templateid"]
        # Create the "groups" list dynamically
        templates = [{"templateid": tpl_id} for tpl_id in template_ids.values()]
        # Create the final config
        templates_config = {"templates": templates}


        # Step 2: Get the Host Group ID
        for host_group_name in host_group_list:
            host_group = zapi.hostgroup.get(filter={"name": host_group_name})
            if not host_group:
                raise Exception(f"Host group '{host_group_name}' not found.")
            host_group_ids[host_group_name] = host_group[0]["groupid"]
        # Create the "groups" list dynamically
        hgroups = [{"groupid": group_id} for group_id in host_group_ids.values()]
        # Create the final config
        hgroups_config = {"groups": hgroups}


        # Step 3: Create the new host with description and visible name
        for host in hosts_dict:
            try:

                # Host information
                host_name = hosts_dict[host][0].split('.')[0]           # {HOST.HOST}
                host_visible_name = hosts_dict[host][0].split('.')[0]   # {HOST.NAME}
                host_ip = hosts_dict[host][1].strip()                   # Host IP
                host_macro = hosts_dict[host][2]                        # Host Macro
                host_desc = hosts_dict[host][3]                         # Host Description 

                zabbix_macros = [
                    {"macro": "{$HOST.URL}", "value": f"{host_macro}"}
                ]

                new_host = zapi.host.create({
                    "host": host_name,
                    "name": host_visible_name,
                    "description": host_desc,
                    "groups": hgroups_config["groups"],
                    "templates": templates_config["templates"],
                    "tags": tag_list,
                    "macros": zabbix_macros,
                    "interfaces": [{
                    "type": 1,  # Type 1 = Agent
                    "main": 1,  # Mark this as the main interface
                    "useip": 1,  # Use IP address for connection
                    "ip": host_ip,
                    "dns": "",
                    "port": "10050"
                    }]

                })


                print(f"Host '{host_name}' created with ID {new_host['hostids'][0]}")
                print('#############\n')

            except Exception as loop_err:
                print(f"Error adding host '{host_name}': {loop_err}")

    except Exception as err:
        print(f"Error: {err}")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

# =====================================================================

TFVARS_FILE = "vms.tfvars.json"

tfvars = load_json(TFVARS_FILE)

urL_monitored_product_lines = ["Rahkaran Server"]

for vm_name, vm in tfvars["vms"].items():
    try:
        _product_line = vm.get("custom_attrs").get("ProductLine", None)
        _company_name = vm.get("custom_attrs").get("CompanyName", None)
        _national_id  = vm.get("custom_attrs").get("National ID", None)
        _public_ip    = vm.get("custom_attrs").get("Public IP", None)

        if _product_line in urL_monitored_product_lines:
            _url = vm.get("custom_attrs").get("URL", None)
            
            if _url:
                _zabbix_server = vm.get("zabbix_server", None).lower()
                if _zabbix_server == 'vnk-customerzabbix':
                    zabbix_url = ME_CUSTOMERZABBIX_URL
                    zabbix_token = ME_CUSTOMERZABBIX_TOKEN

                    if vm_name.lower().startswith('vr1-'):
                        specific_hostgroup = "VR1"
                    elif vm_name.lower().startswith('vr2-'):
                        specific_hostgroup = "VR2"
                    elif vm_name.lower().startswith('vr3-'):
                        specific_hostgroup = "VR3"

                    hostgroups = ["Rahkaran_OnPrem_Grp", "Support_Team", specific_hostgroup]

                elif _zabbix_server == 'me-customerzabbix':
                    zabbix_url = VNK_CUSTOMERZABBIX_URL
                    zabbix_token = VNK_CUSTOMERZABBIX_TOKEN
                    hostgroups = ["Rahkaran_OnPrem_Grp", "Support_Team", "MER-Grp"]

                else:
                    logger.error(
                        f"Unknown zabbix_server.",
                        extra={
                            "issue": JIRA_TICKET_KEY,
                            "zabbix_server": _zabbix_server
                        }
                    )
                    raise SystemExit(f"Unknown zabbix_server. {_zabbix_server}")

                # Add Node
                zabbix_node_adder(
                url=zabbix_url,
                token=zabbix_token,
                hosts_dict={
                    vm_name.lower(): [
                        vm_name.lower(),
                        _public_ip,
                        _url,
                        dedent(f"""
                            VM-Creation-Automation

                            Product line: {_product_line}
                            Company Name: {_company_name}
                            National ID: {_national_id}
                        """).strip()
                    ]
                },
                template_list=["Rahkaran-OnPrem-Tpl-Far"],
                host_group_list=hostgroups,
                tag_list=[
                    {"tag": "Note", "value": ""},
                    {"tag": "Owner", "value": "Support_Team"},
                    {"tag": "__zbx_jira", "value": "1"}
                ]
                )

            else:
                logger.info(
                        f"Skipping {vm_name}",
                        extra={
                            "issue": JIRA_TICKET_KEY,
                            "product_line": _product_line,
                            "vm_name": vm_name
                        }
                    )
                print(f"Skipping {vm_name}")

        else:
            logger.info(
                    f"No URL monitoring needed for {vm_name}",
                    extra={
                        "issue": JIRA_TICKET_KEY,
                        "product_line": _product_line,
                        "vm_name": vm_name
                    }
                )
            print(f"No URL monitoring needed for {vm_name}")

        
    except Exception as err:

        error_string_summary = f"{type(err).__name__}: {err}"

        # Get the traceback and extract the last traceback frame
        tb = traceback.extract_tb(err.__traceback__)
        last_call = tb[-1]  # the last traceback frame, where the exception occurred
        error_string_detail = f"Error occurred in line {last_call.lineno}: {last_call.line}"
        print(f"Script failed: {error_string_summary}\n{error_string_detail}")

        logger.error(
            f"add_url_monitoring() failed",
            extra={
                "issue": JIRA_TICKET_KEY,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise  
        
