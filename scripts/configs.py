#!/usr/bin/env python3

import os
from pathlib import Path

# Gitlab
GIT_PUSH_TOKEN = os.environ["GIT_PUSH_TOKEN"]   # used for pushing final reports to the vm-creation project
GIT_API_TOKEN = os.environ["GIT_API_TOKEN"]     # used to fetch failed stage state and traceback of vm-creation project
BIND_PUSH_TOKEN = os.environ["BIND_PUSH_TOKEN"] # used to push changes to bind project for dns section

# DNS (used for resolving abramad.cloud domain records)
DNS_SERVER = os.environ["DNS_SERVER"]
PUBLIC_ZONE = os.environ["PUBLIC_ZONE"]

# Mattermost
MATTERMOST_NOTIFY_WEBHOOK = os.environ["MATTERMOST_NOTIFY_WEBHOOK"]
MATTERMOST_FAILURE_WEBHOOK = os.environ["MATTERMOST_FAILURE_WEBHOOK"]

# Email
MAIL_SERVER = os.environ["MAIL_SERVER"]
CC_EMAIL = os.environ["CC_EMAIL"]

# Logs
CI_PROJECT_DIR = Path(os.environ.get("CI_PROJECT_DIR", "."))
CI_JOB_NAME = os.environ.get("CI_JOB_NAME", "local")

# sanitize job name for use in a filename (job names can contain ':', '/', etc. in matrix jobs)
_safe_job_name = CI_JOB_NAME.replace("/", "_").replace(":", "_")

LOG_FILE = CI_PROJECT_DIR / f"automation.{_safe_job_name}.log"

# Zabbix
VNK_CUSTOMERZABBIX_URL = os.environ["VNK_CUSTOMERZABBIX_URL"]
VNK_CUSTOMERZABBIX_TOKEN = os.environ["VNK_CUSTOMERZABBIX_TOKEN"]
ME_CUSTOMERZABBIX_URL = os.environ["ME_CUSTOMERZABBIX_URL"]
ME_CUSTOMERZABBIX_TOKEN = os.environ["ME_CUSTOMERZABBIX_TOKEN"]

# Pushgateway
success = True
error_string_summary = ""
error_string_detail = ""
PUSHGATEWAY_URL = os.environ["PUSHGATEWAY_URL"]

# Jira
JIRA_SRV = os.environ["JIRA_SRV"]
JIRA_TOKEN = os.environ["JIRA_TOKEN"]
JIRA_ADDR = os.environ["JIRA_ADDR"]
JIRA_CLOSE_TRANSITION_NAME = os.environ.get("JIRA_CLOSE_TRANSITION_NAME", "close") # ID in test 101
JIRA_TICKET_KEY = os.environ["JIRA_TICKET_KEY"]

# vCenter
VSPHERE_USER = os.environ["VSPHERE_USER"]
VSPHERE_PASSWORD = os.environ["VSPHERE_PASSWORD"]
VSPHERE_NORMAL_CLUSTER_CPU_LIMIT = int(os.getenv('NORMAL_CLUSTER_CPU_LIMIT', 30))
VSPHERE_HIGHPERF_CLUSTER_CPU_LIMIT = int(os.getenv('HIGHPERF_CLUSTER_CPU_LIMIT', 48))
VSPHERE_NORMAL_CLUSTER_RAM_LIMIT = int(os.getenv('NORMAL_CLUSTER_RAM_LIMIT', 128))
VSPHERE_HIGHPERF_CLUSTER_RAM_LIMIT = int(os.getenv('HIGHPERF_CLUSTER_RAM_LIMIT', 256)) 
VSPHERE_DATASTORE_MAX_UTILIZATION = float(os.getenv('DATASTORE_MAX_UTILIZATION', 80)) / 100

# Windows
DOMAIN = os.getenv('DOMAIN', "cloud.local")
DOMAIN_JOIN_USER = os.environ['DOMAIN_JOIN_USER']
DOMAIN_JOIN_PASSWORD = os.environ['DOMAIN_JOIN_PASSWORD']
LOCAL_ADMIN_PASSWORD = os.environ['LOCAL_ADMIN_PASSWORD']
# Below Vars are created in Gitlab and Used in Ansible Inventory file
# AD_ANSIBLE_PASSWORD
# AD_ANSIBLE_USER
# AD_SERVER
# WINDOWS_ANSIBLE_USER
# WINDOWS_ANSIBLE_PASSWORD
# LINUX_ANSIBLE_USER
# LINUX_SSH_PRIVATE_KEY

# Netbox
NETBOX_URL = os.environ["NETBOX_URL"]
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]


# Dictionaries
template_dict = {
    "RII-APP":   "TMP-RII-W2022APP",
    "RII-DB":    "TMP-RII-W2022DB",
    "RI":        "TMP-RI-W2022",
    "BI":        "TMP-BI-W2022",
    "SEP":       "TMP-SEP-W2022",
    "IaaS-W22":  "TMP-IaaS-W2022",
    "IaaS-U24":  "TMP-IaaS-U2404",
    "IaaS-U26":  "TMP-IaaS-U2604",
    "IaaS-R98":  "TMP-IaaS-R9.8",
    "IaaS-O9":   "TMP-IaaS-O9",
    "MIaaS-W22": "TMP-MIaaS-W2022",
}

vcenter_dict = {
    "vanak": {
        "addr": "vts-lab-vc01.abramad.com", 
        "dc": "VTS-LAB-Datacenter",
        "compute_cluster" : {
            "High Performance Processor": "VTS-LAB-Sandy Bridge-E5-2600",
            "Normal Processor": "",
        },
        "storage_cluster" : {
            "standard": "VTS-VNX5400-Std-Pool01-15K-LAB",
            "advanced": "VTS-VNX5400-Adv-Pool01-15K-LAB",
            "pro":      "VTS-VNX5400-Pro-Pool01-15K-LAB",
            "ultra":    "VTS-VNX5400-Ultra-Pool01-15K-LAB",
        },
        "portgroup" : {
            "VRD": "AbramadRahkaranDev-VRD-NSX-217",
            "VRI": "AbramadRahkaran-VR1-NSX-212",
            "VRII": "AbramadRahkaran-VR2-NSX-213",
            "VRIII": "AbramadRahkaran-VR3-NSX-214",
            "VBI": "AbramadBI-VBI-NSX-220",
            "VSP": "AbramadSepidar-VSP-NSX-223",
            "VIA": "AbramadIaaS-VIA-NSX-226",
            "VMI": "AbramadMIaaS-VMI-NSX-229",
        },
        },

    "vanak-main": {
        "addr": "vab-vc01.abramad.com",
        "dc": "VAB-Datacenter",
        "compute_cluster" : {
            "High Performance Processor": "VAB-HighPerformance-SapphireRapids-8558P",
            "Normal Processor": "",
        },
        "storage_cluster" : {
            "standard": "VNK-PS-E2U3-Std-Pool01-CUS-ABR",
            "advanced": "VNK-PS-E2U3-Adv-Pool01-CUS-ABR",
            "pro":      "VNK-PS-E2U3-Pro-Pool01-CUS-ABR",
            "ultra":    "VNK-PS-E2U3-Ultra-Pool01-CUS-ABR",
        },
        "portgroup" : {
            "VRD": "AbramadRahkaranDev-VRD-NSX-217",
            "VRI": "AbramadRahkaran-VR1-NSX-212",
            "VRII": "AbramadRahkaran-VR2-NSX-213",
            "VRIII": "AbramadRahkaran-VR3-NSX-214",
            "VBI": "AbramadBI-VBI-NSX-220",
            "VSP": "AbramadSepidar-VSP-NSX-223",
            "VIA": "AbramadIaaS-VIA-NSX-226",
            "VMI": "AbramadMIaaS-VMI-NSX-229",
        },
        },

    "miremad": {
        "addr": "me-vc01.abramad.com",
        "dc": "ME-Datacenter",
        "compute_cluster" : {
            "High Performance Processor": "",
            "Normal Processor": "",
        },
        "storage_cluster" : {
            "standard": "",
            "advanced": "",
            "pro":      "",
            "ultra":    "",
        },
        "portgroup" : {
            "MRD": "RahkaranTO-58-NSX",
            "MRI": "Rahkaran1-59-NSX",
            "MRII": "Rahkaran2-60-NSX",
            "MRIII": "Rahkaran3-61-NSX",
            "MBI": "BI-62-NSX",
            "MSP": "Sepidar-64-NSX",
            "MIA": "IaaS-66-NSX",
            "MMI": "MIaaS-65-NSX",
        },
        },
}

jira_field_dict = {
    "test": {
        # General Fields
        "datacenter":           "customfield_13004",
        "vm_base_name":         "customfield_13593",
        "product_line":         "customfield_11377",
        "category":             "customfield_11385",
        "instances":            "customfield_13564",
        "company_name":         "customfield_11328",
        "national_id":          "customfield_11223",
        "server_os":            "customfield_11342",
        "business_value":       "customfield_13460",
        "industry":             "customfield_13514",
        "vcenter_folder":       "customfield_13562",
        "ad_ou":                "customfield_13563",
        "sepidar_lock":         "customfield_11512",
        "vra_server":           "customfield_12798",
        "processor_type":       "customfield_11291",

        # Boolean Fields
        "is_new_customer":      "customfield_11292",
        "idsips_enabled":       "customfield_13518",
        "waf_enabled":          "customfield_13519",
        "dongle_enabled":       "customfield_13520",
        "stsvpn_enabled":       "customfield_13521",
        "native_backup_needed": "customfield_11338",
        "public_ip_needed":     "customfield_11372",

        # Contact Fields
        "agent_fullname":       "customfield_13522",
        "agent_phone":          "customfield_11345",
        "agent_natid":          "customfield_13523",
        "agent_email":          "customfield_11234",
        "deployer_fullname":    "customfield_13524",
        "deployer_phone":       "customfield_13526",
        "deployer_natid":       "customfield_13525",
        "deployer_email":       "customfield_13527",

        # App Fields
        "app_memory":           "customfield_11250",
        "app_cpu":              "customfield_11352",
        "app_disk_count":       "customfield_13528",

        "app_disk1_size":       "customfield_13529",
        "app_disk2_size":       "customfield_13531",
        "app_disk3_size":       "customfield_13532",
        "app_disk4_size":       "customfield_13594",
        "app_disk5_size":       "customfield_13596",

        "app_disk1_type":       "customfield_13586",
        "app_disk2_type":       "customfield_13587",
        "app_disk3_type":       "customfield_13588",
        "app_disk4_type":       "customfield_13595",
        "app_disk5_type":       "customfield_13597",

        # DB Fields
        "db_memory":           "customfield_13570",
        "db_cpu":              "customfield_13569",
        "db_disk_count":       "customfield_13571",

        "db_disk1_size":       "customfield_13573",
        "db_disk2_size":       "customfield_13583",
        "db_disk3_size":       "customfield_13598",
        "db_disk4_size":       "customfield_13600",
        "db_disk5_size":       "customfield_13602",

        "db_disk1_type":       "customfield_13589",
        "db_disk2_type":       "customfield_13590",
        "db_disk3_type":       "customfield_13599",
        "db_disk4_type":       "customfield_13601",
        "db_disk5_type":       "customfield_13603",

        # LB Fields
        "lb_memory":           "customfield_13575",
        "lb_cpu":              "customfield_13574",
        "lb_disk_count":       "customfield_13576",

        "lb_disk1_size":       "customfield_13579",
        "lb_disk2_size":       "customfield_13606",
        "lb_disk3_size":       "customfield_13604",
        "lb_disk4_size":       "customfield_13607",
        "lb_disk5_size":       "customfield_13609",

        "lb_disk1_type":       "customfield_13591",
        "lb_disk2_type":       "customfield_13592",
        "lb_disk3_type":       "customfield_13605",
        "lb_disk4_type":       "customfield_13608",
        "lb_disk5_type":       "customfield_13610",
    },

    "main": {
        # General Fields
        "datacenter":           "customfield_13004",
        "vm_base_name":         "customfield_11246",
        "product_line":         "customfield_11377",
        "category":             "customfield_11385",
        "instances":            "customfield_13564",
        "company_name":         "customfield_11328",
        "national_id":          "customfield_11223",
        "server_os":            "customfield_11342",
        "business_value":       "customfield_13460",
        "industry":             "customfield_13514",
        "vcenter_folder":       "customfield_13562",
        "ad_ou":                "customfield_13563",
        "sepidar_lock":         "customfield_11512",
        "vra_server":           "customfield_12798",
        "processor_type":       "customfield_11291",

        # Boolean Fields
        "is_new_customer":      "customfield_11292",
        "idsips_enabled":       "customfield_13518",
        "waf_enabled":          "customfield_13519",
        "dongle_enabled":       "customfield_13520",
        "stsvpn_enabled":       "customfield_13521",
        "native_backup_needed": "customfield_11338",
        "public_ip_needed":     "customfield_11372",

        # Contact Fields
        "agent_fullname":       "customfield_13522",
        "agent_phone":          "customfield_11345",
        "agent_natid":          "customfield_13523",
        "agent_email":          "customfield_11234",
        "deployer_fullname":    "customfield_13524",
        "deployer_phone":       "customfield_13526",
        "deployer_natid":       "customfield_13525",
        "deployer_email":       "customfield_13527",

        # App Fields
        "app_memory":           "customfield_11250",
        "app_cpu":              "customfield_11352",
        "app_disk_count":       "customfield_13528",

        "app_disk1_size":       "customfield_13529",
        "app_disk2_size":       "customfield_13531",
        "app_disk3_size":       "customfield_13532",
        "app_disk4_size":       "customfield_13594",
        "app_disk5_size":       "customfield_13596",

        "app_disk1_type":       "customfield_13586",
        "app_disk2_type":       "customfield_13587",
        "app_disk3_type":       "customfield_13588",
        "app_disk4_type":       "customfield_13595",
        "app_disk5_type":       "customfield_13597",

        # DB Fields
        "db_memory":           "customfield_13570",
        "db_cpu":              "customfield_13569",
        "db_disk_count":       "customfield_13571",

        "db_disk1_size":       "customfield_13573",
        "db_disk2_size":       "customfield_13583",
        "db_disk3_size":       "customfield_13598",
        "db_disk4_size":       "customfield_13600",
        "db_disk5_size":       "customfield_13602",

        "db_disk1_type":       "customfield_13589",
        "db_disk2_type":       "customfield_13590",
        "db_disk3_type":       "customfield_13599",
        "db_disk4_type":       "customfield_13601",
        "db_disk5_type":       "customfield_13603",

        # LB Fields
        "lb_memory":           "customfield_13575",
        "lb_cpu":              "customfield_13574",
        "lb_disk_count":       "customfield_13576",

        "lb_disk1_size":       "customfield_13579",
        "lb_disk2_size":       "customfield_13606",
        "lb_disk3_size":       "customfield_13604",
        "lb_disk4_size":       "customfield_13607",
        "lb_disk5_size":       "customfield_13609",

        "lb_disk1_type":       "customfield_13591",
        "lb_disk2_type":       "customfield_13592",
        "lb_disk3_type":       "customfield_13605",
        "lb_disk4_type":       "customfield_13608",
        "lb_disk5_type":       "customfield_13610",
    }
}
