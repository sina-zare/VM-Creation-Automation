#!/usr/bin/env python3
try:
    from prometheus_client import CollectorRegistry, Gauge, push_to_gateway, Counter
    from scripts.utility.functions.data_validators import *
    from scripts.utility.functions.netbox import *
    from pyVim.connect import Disconnect
    from scripts.utility.log.logger import get_logger
    from jira import JIRA
    from scripts.configs import *
    import time
    import json
    import sys

    logger = get_logger(__name__)

    # Metric Definition
    script_name = 'vm_creation_data_fetcher'
    job_name = 'python_scripts'
    instance = script_name
    target = 'vm_specs'

    # Create a registry for our custom metrics
    registry = CollectorRegistry()

    # Define metrics
    duration_gauge = Gauge('script_exec_duration_seconds', 'Duration of my script', registry=registry)
    status_gauge = Gauge('script_success', 'Whether script succeeded (1) or failed (0)', registry=registry)
    last_error_message = Gauge(
        'script_last_error_message',
        'The last error message encountered during script execution',
        ['error_summary', 'error_detail'],
        registry=registry)

    start_time = time.time()

    if len(sys.argv) != 2:
        raise ValueError("Usage: data_fetcher.py <ticket_id>")

    TICKET_ID = sys.argv[1]
    #TICKET_ID = 'SERVICDESK-83929'

    jira = JIRA(server=JIRA_ADDR, token_auth=JIRA_TOKEN)
    issue = jira.issue(TICKET_ID)
    fields = issue.fields

    # Show ticket fields
    # print(json.dumps(
    #     issue.fields.__dict__,
    #     ensure_ascii=False,
    #     indent=2,
    #     default=str
    # ))

    # Data Gathering
    # General Spec
    datacenter = getattr(issue.fields, jira_field_dict[JIRA_SRV]['datacenter'], None).value.strip().lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['datacenter'], None) else ""
    vm_base_name = getattr(issue.fields, jira_field_dict[JIRA_SRV]['vm_base_name'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['vm_base_name'], None) else ""
    product_line = getattr(issue.fields, jira_field_dict[JIRA_SRV]['product_line'], None).value if getattr(issue.fields, jira_field_dict[JIRA_SRV]['product_line'], None) else "N/A"
    category = getattr(issue.fields, jira_field_dict[JIRA_SRV]['category'], None).value if getattr(issue.fields, jira_field_dict[JIRA_SRV]['category'], None) else "N/A"
    instances = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['instances'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['instances'], None) else 1
    company_name = getattr(issue.fields, jira_field_dict[JIRA_SRV]['company_name'], None) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['company_name'], None) else ""
    national_id = getattr(issue.fields, jira_field_dict[JIRA_SRV]['national_id'], None) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['national_id'], None) else ""
    server_os = getattr(issue.fields, jira_field_dict[JIRA_SRV]['server_os'], None).value.strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['server_os'], None) else None
    os_type = os_selector(product_line, server_os, issue)
    business_value = getattr(issue.fields, jira_field_dict[JIRA_SRV]['business_value'], None).value.strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['business_value'], None) else ""  
    industry = getattr(issue.fields, jira_field_dict[JIRA_SRV]['industry'], None).value.strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['industry'], None) else ""
    init_vcenter_folder = getattr(issue.fields, jira_field_dict[JIRA_SRV]['vcenter_folder'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['vcenter_folder'], None) else ""
    ad_ou = getattr(issue.fields, jira_field_dict[JIRA_SRV]['ad_ou'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['ad_ou'], None) else ""

    if datacenter.lower() == 'vanak':
        nb_scope = 'vanak'
    elif datacenter.lower() == 'miremad':
        nb_scope = 'ME'
    nb_target = 'customers'

    sepidar_lock = getattr(issue.fields, jira_field_dict[JIRA_SRV]['sepidar_lock'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['sepidar_lock'], None) and product_line == "Sepidar Server" else ""
    vra_server = getattr(issue.fields, jira_field_dict[JIRA_SRV]['vra_server'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['vra_server'], None) and product_line == "BI Server" else ""

    is_new_customer = True if (getattr(issue.fields, jira_field_dict[JIRA_SRV]['is_new_customer'], None).value.strip().lower() == "new customer") else False
    idsips_enabled = True if (getattr(issue.fields, jira_field_dict[JIRA_SRV]['idsips_enabled'], None).value.strip().lower() == "yes") else False
    waf_enabled = True if (getattr(issue.fields, jira_field_dict[JIRA_SRV]['waf_enabled'], None).value.strip().lower() == "yes") else False
    dongle_enabled = True if (getattr(issue.fields, jira_field_dict[JIRA_SRV]['dongle_enabled'], None).value.strip().lower() == "yes") else False
    stsvpn_enabled = True if (getattr(issue.fields, jira_field_dict[JIRA_SRV]['stsvpn_enabled'], None).value.strip().lower() == "yes") else False
    native_backup_needed = True if (getattr(issue.fields, jira_field_dict[JIRA_SRV]['native_backup_needed'], None).value.strip().lower() == "yes") else False
    public_ip_needed = True if (getattr(issue.fields, jira_field_dict[JIRA_SRV]['public_ip_needed'], None).value.strip().lower() == "yes") else False

    # AD OU and vCenter Folder
    if is_new_customer:
        print(f'New Customer: {is_new_customer}')
        ad_ou = vm_base_name
        vcenter_folder = vcenter_folder_selector(
            _is_new_customer=is_new_customer,
            _base_name=vm_base_name,
            vm_product_line=product_line,
            jira_issue=issue
        )
    else:
        print(f'New Customer: {is_new_customer}')
        vcenter_folder = vcenter_folder_selector(
            _is_new_customer=is_new_customer,
            _base_name=init_vcenter_folder,
            vm_product_line=product_line,
            jira_issue=issue
        )

    # Server Count
    if product_line == "Rahkaran Server" and category == "R II":
        server_count = 2  # 1(DB) + 1(App)
    elif product_line == "Rahkaran Server" and category == "R III":
        server_count = 2 + instances  # 1(DB) + 1(LB) + N(App)
    else:
        server_count = 1

    # Human Resources Info
    agent_fullname = getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_fullname'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_fullname'], None) else None
    agent_phone = getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_phone'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_phone'], None) else None
    agent_natid = getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_natid'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_natid'], None) else None
    agent_email = getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_email'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['agent_email'], None) else None

    deployer_fullname = getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_fullname'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_fullname'], None) else None
    deployer_phone = getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_phone'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_phone'], None) else None
    deployer_natid = getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_natid'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_natid'], None) else None
    deployer_email = getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_email'], None).strip() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['deployer_email'], None) else None

    # Specs Info
    processor_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['processor_type'], None).value if getattr(issue.fields, jira_field_dict[JIRA_SRV]['processor_type'], None) else ""
    compute_cluster = vcenter_dict.get(datacenter, {}).get("compute_cluster", {}).get(processor_type, "")

    # Memory and CPU Specs
    app_init_memory = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_memory'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_memory'], None) else 0  # APP
    db_init_memory = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_memory'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_memory'], None) else 0  # DB
    lb_init_memory = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_memory'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_memory'], None) else 0  # LB

    app_init_cpu = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_cpu'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_cpu'], None) else 0  # APP
    db_init_cpu = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_cpu'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_cpu'], None) else 0  # DB
    lb_init_cpu = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_cpu'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_cpu'], None) else 0  # LB
    # Disk Specs
    app_disk_count = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk_count'], None).value) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk_count'], None) else 0  # APP

    app_disk1_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk1_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk1_size'], None) else 0  # APP
    app_disk2_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk2_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk2_size'], None) else 0  # APP
    app_disk3_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk3_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk3_size'], None) else 0  # APP
    app_disk4_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk4_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk4_size'], None) else 0  # APP
    app_disk5_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk5_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk5_size'], None) else 0  # APP

    app_disk1_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk1_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk1_type'], None) else ""  # APP
    app_disk2_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk2_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk2_type'], None) else ""  # APP
    app_disk3_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk3_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk3_type'], None) else ""  # APP
    app_disk4_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk4_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk4_type'], None) else ""  # APP
    app_disk5_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk5_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['app_disk5_type'], None) else ""  # APP
    # ===========================================================================================================
    db_disk_count = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk_count'], None).value) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk_count'], None) else 0  # DB

    db_disk1_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk1_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk1_size'], None) else 0  # DB
    db_disk2_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk2_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk2_size'], None) else 0  # DB
    db_disk3_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk3_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk3_size'], None) else 0  # DB
    db_disk4_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk4_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk4_size'], None) else 0  # DB
    db_disk5_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk5_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk5_size'], None) else 0  # DB

    db_disk1_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk1_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk1_type'], None) else ""  # DB
    db_disk2_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk2_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk2_type'], None) else ""  # DB
    db_disk3_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk3_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk3_type'], None) else ""  # DB
    db_disk4_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk4_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk4_type'], None) else ""  # DB
    db_disk5_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk5_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['db_disk5_type'], None) else ""  # DB
    # ===========================================================================================================
    lb_disk_count = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk_count'], None).value) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk_count'], None) else 0  # LB

    lb_disk1_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk1_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk1_size'], None) else 0  # LB
    lb_disk2_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk2_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk2_size'], None) else 0  # LB
    lb_disk3_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk3_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk3_size'], None) else 0  # LB
    lb_disk4_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk4_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk4_size'], None) else 0  # LB
    lb_disk5_size = int(getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk5_size'], None)) if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk5_size'], None) else 0  # LB

    lb_disk1_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk1_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk1_type'], None) else ""  # LB
    lb_disk2_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk2_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk2_type'], None) else ""  # LB
    lb_disk3_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk3_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk3_type'], None) else ""  # LB
    lb_disk4_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk4_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk4_type'], None) else ""  # LB
    lb_disk5_type = getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk5_type'], None).value.lower() if getattr(issue.fields, jira_field_dict[JIRA_SRV]['lb_disk5_type'], None) else ""  # LB

    disk_map = {
        "app": [
            {"size": app_disk1_size, "type": app_disk1_type},
            {"size": app_disk2_size, "type": app_disk2_type},
            {"size": app_disk3_size, "type": app_disk3_type},
            {"size": app_disk4_size, "type": app_disk4_type},
            {"size": app_disk5_size, "type": app_disk5_type},
        ],
        "db": [
            {"size": db_disk1_size, "type": db_disk1_type},
            {"size": db_disk2_size, "type": db_disk2_type},
            {"size": db_disk3_size, "type": db_disk3_type},
            {"size": db_disk4_size, "type": db_disk4_type},
            {"size": db_disk5_size, "type": db_disk5_type},
        ],
        "lb": [
            {"size": lb_disk1_size, "type": lb_disk1_type},
            {"size": lb_disk2_size, "type": lb_disk2_type},
            {"size": lb_disk3_size, "type": lb_disk3_type},
            {"size": lb_disk4_size, "type": lb_disk4_type},
            {"size": lb_disk5_size, "type": lb_disk5_type},
        ]
    }

    # print(f"""
    #     App Disk Count: {app_disk_count}
    #         Disk1
    #             Size: {app_disk1_size}
    #             Type: {app_disk1_type}

    #         Disk2
    #             Size: {app_disk2_size}
    #             Type: {app_disk2_type}

    #         Disk3
    #             Size: {app_disk3_size}
    #             Type: {app_disk3_type}


    #     DB Disk Count: {db_disk_count}
    #         Disk1
    #             Size: {db_disk1_size}
    #             Type: {db_disk1_type}

    #         Disk2
    #             Size: {db_disk2_size}
    #             Type: {db_disk2_type}


    #     LB Disk Count: {lb_disk_count}
    #         Disk1
    #             Size: {lb_disk1_size}
    #             Type: {lb_disk1_type}

    #         Disk2
    #             Size: {lb_disk2_size}
    #             Type: {lb_disk2_type}
    # """)

except Exception as err:
    
    success = False
    error_string_summary += f"{type(err).__name__}: {err}"

    # Get the traceback and extract the last traceback frame
    tb = traceback.extract_tb(err.__traceback__)
    last_call = tb[-1]  # the last traceback frame, where the exception occurred
    error_string_detail += f"Error occurred in line {last_call.lineno}: {last_call.line}"
    print(f"Script failed: {error_string_summary}\n{error_string_detail}")

    logger.error(
        f"data_fetcher() failed",
        extra={
            "issue": TICKET_ID,
            "error_summary": error_string_summary,
            "error_detail": error_string_detail,
        }
    )

    raise

try:
    try:
        vc_addr = vcenter_dict[datacenter.lower()].get("addr")
        vc_datacenter = vcenter_dict[datacenter.lower()].get("dc")
    except:
        logger.error(
            f"No automation procedure available for datacenter '{datacenter}'",
            extra={
                "issue": issue.key,
                "vm_datacenter": datacenter,
            }
        )

        raise ValueError(
            f"No automation procedure available for datacenter '{datacenter}'"
        )

    # Data Filling
    virtual_machines = {}
    si = get_vcenter_connection(
        vcenter_addr=vc_addr,
        vcenter_user=VSPHERE_USER,
        vcenter_password=VSPHERE_PASSWORD
    )
    vm_names = get_vcenter_vm_names(si)
    #vc_datacenter_names = get_datacenter_names(si)
    #print(vc_datacenter_names)
    for i_srv in range(1, server_count + 1):
        name = vm_name_selector(
            vm_datacenter=datacenter,
            _base_name=vm_base_name,
            vm_product_line=product_line,
            vm_category=category,
            jira_issue=issue,
            vcenter_vm_names=vm_names,
            server_iterator=i_srv,
        )

        zabbix_server = zabbix_server_selector(
            _datacenter=datacenter, 
            _product_line=product_line, 
            jira_issue=issue
        )

        memory = memory_validator(
            vm_category=category,
            vm_processor_type=processor_type,
            jira_issue=issue,
            app_ram=app_init_memory,
            db_ram=db_init_memory,
            lb_ram=lb_init_memory,
            server_iterator=i_srv
        )

        cpu = cpu_validator(
            vm_category=category,
            vm_processor_type=processor_type,
            jira_issue=issue,
            app_cpu=app_init_cpu,
            db_cpu=db_init_cpu,
            lb_cpu=lb_init_cpu,
            server_iterator=i_srv
        )
        # print(f'VM{i_srv} - Name: {name}, Memory: {memory}MB, CPU: {cpu} cores')

        init_disks = disk_compactor(
            _datacenter=datacenter,
            _category=category,
            _disk_map=disk_map,
            _app_disk_count=app_disk_count,
            _db_disk_count=db_disk_count,
            _lb_disk_count=lb_disk_count,
            server_iterator=i_srv
        )
        # print(f'VM{i_srv} - Init Disks: {init_disks}')

        # for disk in init_disks:
        #     print(
        #         f"VM{i_srv} - disk={disk['label']}, "
        #         f"size={disk['size']}, "
        #         f"type={disk['type']}, "
        #         f"storage_cluster={disk['storage_cluster']!r}"
        #     )

        disks = pick_datastore(
            vc_connection=si,
            disks=init_disks,
            jira_issue=issue,
            max_utilization=VSPHERE_DATASTORE_MAX_UTILIZATION
        )
        # print(f'VM{i_srv} - Disks: {disks}')

        template = template_selector(
            vm_datacenter=datacenter,
            vm_name=name,
            vm_os=server_os,
            vm_product_line=product_line,
            vm_category=category,
            jira_issue=issue
        )
        # print(f'VM{i_srv} - Template: {template}')

        port_group = portgroup_selector(
            _datacenter=datacenter,
            _product_line=product_line,
            _category=category,
            jira_issue=issue
        )
        # print(f'VM{i_srv} - Port Group: {port_group}')

        url = ""
        public_ip = ""
        if public_ip_needed:
            url = url_selector(
                _base_name=vm_base_name,
                vm_product_line=product_line,
                jira_issue=issue
            )
            # print(f'VM{i_srv} - URL: {url}')

            # Netbox
            nb = get_client()
            if product_line == "Rahkaran Server":
                if category == "R I":
                    if i_srv == 1:  # Main Server
                        prefix, free_count = find_best_prefix(nb, nb_scope, nb_target, issue)
                        public_ip_obj = reserve_ip(nb, prefix, f'{name} - {issue.key}', issue)
                        public_ip = str(public_ip_obj.address).split("/")[0]

                elif category == "R II":
                    if i_srv == 1:  # App Server
                        prefix, free_count = find_best_prefix(nb, nb_scope, nb_target, issue)
                        public_ip_obj = reserve_ip(nb, prefix, f'{name} - {issue.key}', issue)
                        public_ip = str(public_ip_obj.address).split("/")[0]

                elif category == "R III":
                    if i_srv == 2:  # LB Server
                        prefix, free_count = find_best_prefix(nb, nb_scope, nb_target, issue)
                        public_ip_obj = reserve_ip(nb, prefix, f'{name} - {issue.key}', issue)
                        public_ip = str(public_ip_obj.address).split("/")[0]
            else:
                prefix, free_count = find_best_prefix(nb, nb_scope, nb_target, issue)
                public_ip_obj = reserve_ip(nb, prefix, f'{name} - {issue.key}', issue)
                public_ip = str(public_ip_obj.address).split("/")[0]

            # print(f'VM{i_srv} - Public IP: {public_ip}')

        custom_attributes = attribute_selector(
            vm_product_line=product_line,
            vm_category=category,
            _creation_date_time=tehran_datetime(),
            _url=url,
            _public_ip=public_ip,
            _company_name=company_name,
            _national_id=national_id,
            _native_backup_needed=native_backup_needed,
            _dongle_enabled=dongle_enabled,
            _idsips_enabled=idsips_enabled,
            _waf_enabled=waf_enabled,
            _stsvpn_enabled=stsvpn_enabled,
            _industry=industry,
            _business_value=business_value,
            _agent_email=agent_email,
            _agent_fullname=agent_fullname,
            _agent_phone=agent_phone,
            _sepidar_lock=sepidar_lock,
            _vra_server=vra_server,
            jira_issue=issue,
            server_iterator=i_srv
        )

        virtual_machines[name] = {
            # General
            "os_type": os_type,
            "zabbix_server": zabbix_server,
            "template_name": template,
            "compute_cluster": compute_cluster,
            "vcenter_folder": vcenter_folder,

            # Specs
            "num_cpus": cpu,
            "memory": memory,
            "disks": disks,
            "network": {"portgroup_name": port_group},
            "custom_attrs": custom_attributes,
        }

    ad_info = {
        # AD
        "ad_ou": ad_ou,
        "ad_desc": company_name,
        "domain": DOMAIN,

        # Human Resource
        "users": [
            {
            "role": "agent",
            "username": agent_natid,
            "full_name": agent_fullname,
            "email": agent_email,
            "phone": agent_phone,
            "company": company_name,
            "ou": ad_ou,
            "groups": ["ADSelfServiceEnrollment", f"{ad_ou}Members"],
            },
        ],
         
        "groups": [
            {
                "name": f"{ad_ou}Deploy",
                "description": f"Deployers of {ad_ou}",
                "scope": "global",
                "category": "security"
            },
            {
                "name": f"{ad_ou}Support",
                "description": f"Support of {ad_ou}",
                "scope": "global",
                "category": "security"
            },
            {
                "name": f"{ad_ou}Members",
                "description": f"Members of {ad_ou}",
                "scope": "global",
                "category": "security"
            },
            {
                "name": f"{ad_ou}Computers",
                "description": f"Computers of {ad_ou}",
                "scope": "global",
                "category": "security"
            },
        ]
    }

    # Add Deployer user if existed
    if deployer_fullname and deployer_natid and deployer_email and deployer_phone:
        ad_info["users"].append(
            {
            "role": "deployer",
            "username": deployer_natid,
            "full_name": deployer_fullname,
            "email": deployer_email,
            "phone": deployer_phone,
            "company": "SystemGroup",
            "ou": "Deploy",
            "groups": ["ADSelfServiceEnrollment", "DeployMembers", f"{ad_ou}Deploy"]
            }
        )

    # Add OU-ComputerName-Members for each VM
    for hostname in virtual_machines:
        ad_info["groups"].append(
            {
            "name": f"{ad_ou}{hostname}Members",
            "description": f"Admins of {hostname}",
            "scope": "global",
            "category": "security"
            }
        )
    

    # tfvars.json
    with open("vms.tfvars.json", "w", encoding="utf-8") as f:
        json.dump({
            "vcenter": {"datacenter_name": vc_datacenter, "vc_addr": vc_addr},
            "vms": virtual_machines,
            "ad_info": ad_info,
        },
            f,
            indent=2,
            ensure_ascii=False)

    # reports
    reporter(
    jira_issue=issue,
    user_natid=agent_natid,
    virtual_machines=virtual_machines,
    )
    

except Exception as err:
    error_string_detail
    error_string_summary
    success

    success = False
    error_string_summary += f"{type(err).__name__}: {err}"

    # Get the traceback and extract the last traceback frame
    tb = traceback.extract_tb(err.__traceback__)
    last_call = tb[-1]  # the last traceback frame, where the exception occurred
    error_string_detail += f"Error occurred in line {last_call.lineno}: {last_call.line}"
    print(f"Script failed: {error_string_summary}\n{error_string_detail}")

    logger.error(
        f"data_fetcher() failed",
        extra={
            "issue": issue.key,
            "error_summary": error_string_summary,
            "error_detail": error_string_detail,
        }
    )

finally:
    Disconnect(si)
    # Finalizing Metrics
    # Script Duration
    duration = time.time() - start_time
    duration_gauge.set(duration)

    # Script Success Status
    status_gauge.set(1 if success else 0)

    if not success:
        # Script Last Error Message
        last_error_message.labels(error_summary=error_string_summary, error_detail=error_string_detail).set(1)

    elif success:
        # Script Last Error Message
        last_error_message.labels(error_summary="None", error_detail="None").set(0)

    # Push metrics to Pushgateway
    push_to_gateway(
        gateway=PUSHGATEWAY_URL,
        job=job_name,
        grouping_key={'instance': instance, 'target': target, 'datacenter': datacenter},
        registry=registry
    )

    logger.info(
            f"data_fetcher() metrics sent",
            extra={
                "issue": JIRA_TICKET_KEY,
            }
        )
    print('data_fetcher() Metrics Sent')
    
        
    
    if not success:

        with open(LOG_FILE) as f:
            for line in f:
                data = json.loads(line)
                #print(json.dumps(data, indent=2))

                print(json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                default=str
                ))

        sys.exit(1)
