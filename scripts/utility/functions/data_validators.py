#!/usr/bin/env python3

import jdatetime, datetime, json
from zoneinfo import ZoneInfo
from scripts.configs import *
from scripts.utility.log.logger import get_logger
import traceback
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.header import Header
from pyVim.connect import SmartConnect
from pyVmomi import vim
import ssl
import re
import os

logger = get_logger(__name__)

def get_vcenter_connection(vcenter_addr, vcenter_user, vcenter_password):
    """
    Connects to vCenter using credentials from environment variables.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.verify_mode = ssl.CERT_NONE

    si = SmartConnect(
        host=vcenter_addr,
        user=vcenter_user,
        pwd=vcenter_password,
        sslContext=context
    )
    return si

def get_obj(content, vimtype, name):
    view = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for obj in view.view:
        if obj.name == name:
            return obj
    return None

def get_datacenter_names(vc_connection):
    """
    Returns a list of all datacenter names in vCenter.
    """
    content = vc_connection.RetrieveContent()

    container = content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.Datacenter],
        True
    )

    datacenter_names = [dc.name for dc in container.view]
    container.Destroy()
    
    return datacenter_names

def pick_datastore(vc_connection, disks, jira_issue, max_utilization):
    """
    Input argument example:
    disks: list of {
        "label": str,
        "size": int,
        "type": str,
        "storage_cluster": str
    }

    Selects a datastore for each disk while ensuring that the
    datastore will not exceed 80% utilization after the disk is added.
    """
    try:
        content = vc_connection.RetrieveContent()

        # cluster_name -> {
        #     datastore_name: {
        #         "free_space": int,
        #         "capacity": int
        #     }
        # }
        cluster_datastores = {}

        for disk in disks:
            cname = disk["storage_cluster"]
            size_bytes = disk["size"] * 1024 ** 3

            if cname not in cluster_datastores:
                pod = get_obj(content, [vim.StoragePod], cname)

                if pod is None:
                    raise Exception(
                        f"Datastore cluster not found: {cname}"
                    )

                cluster_datastores[cname] = {
                    ds.name: {
                        "free_space": ds.summary.freeSpace,
                        "capacity": ds.summary.capacity
                    }
                    for ds in pod.childEntity
                }

            candidates = cluster_datastores[cname]

            if not candidates:
                raise Exception(
                    f"Datastore cluster {cname} contains no datastores"
                )

            eligible_datastores = {}

            for ds_name, ds_info in candidates.items():
                capacity = ds_info["capacity"]
                free_space = ds_info["free_space"]

                current_used = capacity - free_space
                max_allowed_used = capacity * max_utilization
                remaining_allowed = max_allowed_used - current_used

                if remaining_allowed >= size_bytes:
                    eligible_datastores[ds_name] = remaining_allowed

            if not eligible_datastores:
                raise Exception(
                    f"No datastore in cluster {cname} can accommodate disk {disk['label']} ({disk['size']} GB) without exceeding {max_utilization:.0%} utilization"
                )

            # Pick the datastore with the most remaining capacity before reaching the "max_utilization"% utilization limit.
            best_ds = max(
                eligible_datastores,
                key=eligible_datastores.get
            )

            disk["datastore"] = best_ds

            # Reserve the disk space for subsequent disks in this request.
            candidates[best_ds]["free_space"] -= size_bytes

        logger.info(
            f"disks selected",
            extra={
                "issue": jira_issue.key,
                "disks": disks
            }
        )
        return disks

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
            f"pick_datastore() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise

def get_vcenter_vm_names(si):
    content = si.RetrieveContent()

    container = content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.VirtualMachine],
        True
    )

    try:
        return {vm.name.lower() for vm in container.view}
    finally:
        container.Destroy()

def is_vm_name_unique(vm_names, vm_name):
    return vm_name.lower() not in vm_names


def _normalize_recipients(value):
    """Accept a comma-separated string, a list/tuple/set of addresses, or None -
    always return a clean list[str] with no empty/whitespace entries."""
    if not value:
        return []
    if isinstance(value, str):
        return [addr.strip() for addr in value.split(",") if addr.strip()]
    return [addr.strip() for addr in value if addr and addr.strip()]


def send_anonymous_email(
    jira_issue, 
    from_email, 
    to_email, 
    cc_email, 
    subject, 
    html_message, 
    direction,
    mail_server='mail.abramad.com', 
    attachments=None
):
    
    try:
        email_body = html_message

        to_email_list = _normalize_recipients(to_email)
        cc_email_list = _normalize_recipients(cc_email)
        all_recipients = to_email_list + cc_email_list

        if not all_recipients:
            logger.error(
                f"no recipients provided (to_email and cc_email are both empty)",
                extra={
                    "issue": jira_issue,
                    "to": to_email_list,
                    "cc": cc_email_list,
                }
            )
            raise ValueError("send_anonymous_email: no recipients provided (to_email and cc_email are both empty)")

        # Create the email message
        msg = MIMEMultipart()
        msg["From"] = Header(from_email, "utf-8")
        msg["To"] = Header(", ".join(to_email_list), "utf-8")  # For display purposes
        msg["CC"] = Header(", ".join(cc_email_list), "utf-8")  # For display purposes
        msg["Subject"] = Header(subject, "utf-8")

        # Attach HTML body
        msg.attach(MIMEText(email_body, "html", "utf-8"))

        # Attach files if any
        if attachments:
            for attachment in attachments:
                if os.path.exists(attachment):
                    with open(attachment, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(attachment))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                        msg.attach(part)
                else:
                    print(f"Warning: Attachment {attachment} not found.")
                    logger.warning(
                        f"Attachment not found.",
                        extra={
                            "issue": jira_issue,
                            "attachment": attachment,
                        }
                    )

        # Connect to the mail server and send the email
        with smtplib.SMTP(mail_server, 25) as server:
            server.sendmail(from_email, all_recipients, msg.as_string())
            print("Email sent successfully.")

        logger.info(
            f"Email report sent.",
            extra={
                "issue": jira_issue,
                "to": to_email_list,
                "cc": cc_email_list,
            }
        )

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
            f"send_anonymous_email() failed",
            extra={
                "issue": jira_issue,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def zabbix_server_selector(_datacenter, _product_line, jira_issue):
    try:
        monitored_product_lines = ["Rahkaran Server", "Sepidar Server", "Automation Server", "BI Server", "SahamFasl Server", "Managed IaaS Server"]
        _zabbix_server = None
        if _datacenter.lower() == "vanak":
            if _product_line in monitored_product_lines:
                _zabbix_server = "vnk-customerzabbix"
            else:
                logger.warning(
                    f"zabbix_server_selector() did not select any Zabbix server.",
                    extra={
                        "issue": jira_issue.key,
                        "zabbix_server": _zabbix_server,
                        "datacenter": _datacenter,
                        "product_line": _product_line
                    }
                )

        elif _datacenter.lower() == "miremad":
            if _product_line in monitored_product_lines:
                _zabbix_server = "me-customerzabbix"
            else:
                logger.warning(
                    f"zabbix_server_selector() did not select any Zabbix server.",
                    extra={
                        "issue": jira_issue.key,
                        "zabbix_server": _zabbix_server,
                        "datacenter": _datacenter,
                        "product_line": _product_line
                    }
                )

        logger.info(
            "Zabbix Server selected",
            extra={
                "issue": jira_issue.key,
                "zabbix_server": _zabbix_server,
                "datacenter": _datacenter,
                "product_line": _product_line
            }
        )
        return _zabbix_server
    

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
            f"zabbix_server_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def vm_name_selector(
        _base_name,
        vm_datacenter,
        vm_product_line,
        vm_category,
        jira_issue,
        vcenter_vm_names,
        server_iterator=1,
):
    try:
        if 2 <= len(_base_name) <= 8:
            pass
        else:
            logger.error(
                "VM base name must be between 2-8 characters",
                extra={
                    "issue": jira_issue.key,
                    "base_name": _base_name,
                    "length": len(_base_name),
                    "maximum": 8,
                    "minimum": 2
                }
            )

            raise ValueError(
                f"VM base name {_base_name} must be between 2-8 characters"
            )
        if vm_datacenter.lower() == "vanak":
            if vm_product_line == "Rahkaran Server":
                if vm_category == "R Dev":  # VRD-XYZ
                    vm_name = f"VRD-{_base_name}"

                elif vm_category == "R I":  # VR1-XYZ
                    vm_name = f"VR1-{_base_name}"

                elif vm_category == "R II":  # VR2-XYZ-[A1|DB]
                    if server_iterator == 1:
                        vm_name = f"VR2-{_base_name}-A1"
                    elif server_iterator == 2:
                        vm_name = f"VR2-{_base_name}-DB"

                elif vm_category == "R III":  # VR3-XYZ-[A[1-5]|DB|LB]
                    if server_iterator == 1:
                        vm_name = f"VR3-{_base_name}-DB"
                    elif server_iterator == 2:
                        vm_name = f"VR3-{_base_name}-LB"
                    else:
                        app_no = server_iterator - 2
                        vm_name = f"VR3-{_base_name}-A{app_no}"

            elif vm_product_line == "Sepidar Server":
                vm_name = f"VSP-{_base_name}"

            elif vm_product_line == "Automation Server":
                vm_name = f"VAT-{_base_name}"

            elif vm_product_line == "BI Server":
                vm_name = f"VBI-{_base_name}"

            elif vm_product_line == "SahamFasl Server":
                vm_name = f"VSF-{_base_name}"

            elif vm_product_line == "Managed IaaS Server":
                vm_name = f"VMI-{_base_name}"

            elif vm_product_line == "IaaS Server":
                vm_name = f"VIA-{_base_name}"

            else:
                logger.error(
                    f"Product '{vm_product_line}' is not a standard type",
                    extra={
                        "issue": jira_issue.key,
                        "vm_product_line": vm_product_line,
                    }
                )

                raise ValueError(
                    f"Product '{vm_product_line}' is not a standard type"
                )

        else:
            logger.error(
                f"No automation procedure available for datacenter '{vm_datacenter}'",
                extra={
                    "issue": jira_issue.key,
                    "vm_datacenter": vm_datacenter,
                }
            )

            raise ValueError(
                f"No automation procedure available for datacenter '{vm_datacenter}'"
            )

        # vCenter uniqueness check
        if not is_vm_name_unique(vcenter_vm_names, vm_name):
            logger.error(
                "VM name already exists in vCenter",
                extra={
                    "issue": jira_issue.key,
                    "vm_name": vm_name,
                    "_base_name": _base_name,
                    "vm_product_line": vm_product_line
                }
            )
            raise ValueError(
                f"VM name '{vm_name}' already exists in vCenter"
            )

        logger.info(
            "VM name validated",
            extra={
                "issue": jira_issue.key,
                "vm_name": vm_name,
                "_base_name": _base_name,
                "vm_product_line": vm_product_line
            }
        )
        return vm_name

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
            f"vm_name_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def template_selector(vm_name, vm_datacenter, vm_os, vm_product_line, vm_category, jira_issue):
    try:
        if vm_datacenter.lower() == "vanak":
            if vm_product_line == "Rahkaran Server":
                if vm_category == "R Dev" or vm_category == "R I":
                    template_name = template_dict.get("RI")

                elif vm_category == "R II" or vm_category == "R III":  # VR2-XYZ-[A1|DB] VR3-XYZ-[A[1-5]|DB|LB]
                    if re.match(r'^.R\d-.+-(?:A|LB).*', vm_name.upper()):
                        template_name = template_dict.get("RII-APP")
                    elif re.match(r'^.R\d-.+-(?:DB).*', vm_name.upper()):
                        template_name = template_dict.get("RII-DB")

            elif vm_product_line == "Sepidar Server":
                template_name = template_dict.get("SEP")

            elif vm_product_line == "BI Server":
                template_name = template_dict.get("BI")

            elif vm_product_line == "IaaS Server":
                if vm_os.lower() == "windows server 2022":
                    template_name = template_dict.get("MIaaS-W22")
                elif vm_os.lower() == "linux ubuntu 24.04":
                    template_name = template_dict.get("IaaS-U24")
                elif vm_os.lower() == "linux ubuntu 26.04":
                    template_name = template_dict.get("IaaS-U26")
                elif vm_os.lower() == "linux rockey 9.8":
                    template_name = template_dict.get("IaaS-R98")
                elif vm_os.lower() == "linux oracle 9.0":
                    template_name = template_dict.get("IaaS-O9")

            elif vm_product_line == "Managed IaaS Server":
                template_name = template_dict.get("MIaaS-W22")

            else:
                logger.error(
                    f"No templates found for: '{vm_product_line}' '{vm_os}'",
                    extra={
                        "issue": jira_issue.key,
                        "product_line": vm_product_line,
                        "os": vm_os,
                    }
                )

                raise ValueError(
                    f"template_selector() - No templates found for: '{vm_product_line}' '{vm_os}'"
                )

            logger.info(
                "Template name selected",
                extra={
                    "issue": jira_issue.key,
                    "vm_name": vm_name,
                    "template": template_name,
                }
            )

            return template_name

        else:
            logger.error(
                f"No automation procedure available for datacenter '{vm_datacenter}'",
                extra={
                    "issue": jira_issue.key,
                    "vm_datacenter": vm_datacenter,
                }
            )

            raise ValueError(
                f"No automation procedure available for datacenter '{vm_datacenter}'"
            )

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
            f"template_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise

def os_selector(_product_line, _server_os, jira_issue):
    try:
        if _server_os:
            os_type = 'windows' if _server_os.lower().startswith('windows') else 'linux'

        else:
            os_type = 'windows'

        
        logger.info(
            "OS selected",
            extra={
                "issue": jira_issue.key,
                "product_line": _product_line,
                "os": _server_os,
                "os_type": os_type
            }
        )

        return os_type
    
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
            f"os_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def portgroup_selector(_datacenter, _product_line, _category, jira_issue):
    try:
        if _product_line == "Rahkaran Server":
            if _category == "R Dev":
                port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VRD")
            elif _category == "R I":
                port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VRI")
            elif _category == "R II":
                port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VRII")
            elif _category == "R III":
                port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VRIII")

        elif _product_line == "Sepidar Server":
            port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VSP")

        elif _product_line == "BI Server":
            port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VBI")

        elif _product_line == "IaaS Server":
            port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VIA")

        elif _product_line == "Managed IaaS Server":
            port_grp = vcenter_dict.get(_datacenter).get("portgroup").get("VMI")

        else:
            logger.error(
                f"No portgroups found for: '{_product_line}' - datacenter: '{_datacenter}'",
                extra={
                    "issue": jira_issue.key,
                    "product_line": _product_line,
                    "datacenter": _datacenter,
                }
            )

            raise ValueError(
                f"portgroup_selector() - No portgroups found for: '{_product_line}' - datacenter: '{_datacenter}'"
            )

        logger.info(
            "Portgroup selected",
            extra={
                "issue": jira_issue.key,
                "product_line": _product_line,
                "datacenter": _datacenter,
                "portgroup": port_grp,
            }
        )

        return port_grp


        # else:
        #     logger.error(
        #         f"No automation procedure available for datacenter '{_datacenter}'",
        #         extra={
        #             "issue": jira_issue.key,
        #             "vm_datacenter": _datacenter,
        #         }
        #     )

        #     raise ValueError(
        #         f"No automation procedure available for datacenter '{_datacenter}'"
        #     )

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
            f"portgroup_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def memory_validator(
        vm_category,
        vm_processor_type,
        jira_issue,
        app_ram,
        db_ram=None,
        lb_ram=None,
        server_iterator=1
):
    try:
        limits = {
            "High Performance Processor": VSPHERE_HIGHPERF_CLUSTER_RAM_LIMIT,
            "Normal Processor": VSPHERE_NORMAL_CLUSTER_RAM_LIMIT,
        }

        if vm_processor_type not in limits:
            logger.error(
                f"Unsupported processor type: '{vm_processor_type}'",
                extra={
                    "issue": jira_issue.key,
                    "processor_type": vm_processor_type,
                    "valid_processor_types": list(limits.keys()),
                }
            )

            raise ValueError(
                f"memory_validator() - Unsupported processor type: '{vm_processor_type}'"
            )

        max_ram = limits[vm_processor_type]

        if vm_category == "R II":
            if server_iterator == 1:
                target_ram = int(app_ram)
            elif server_iterator == 2:
                target_ram = int(db_ram)

        elif vm_category == "R III":
            if server_iterator == 1:
                target_ram = int(db_ram)
            elif server_iterator == 2:
                target_ram = int(lb_ram)
            elif server_iterator >= 3:
                target_ram = int(app_ram)
        else:
            target_ram = int(app_ram)

        if not 1 <= target_ram <= max_ram:
            logger.error(
                f"VM memory must be between [1-{max_ram}]GB for '{vm_processor_type}' type",
                extra={
                    "issue": jira_issue.key,
                    "processor_type": vm_processor_type,
                    "maximum": max_ram,
                    "minimum": 1,
                    "requested_memory": target_ram,
                }
            )

            raise ValueError(
                f"VM memory must be between [1-{max_ram}]GB for '{vm_processor_type}' type"
            )

        return target_ram * 1024

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
            f"memory_validator() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def cpu_validator(
        vm_category,
        vm_processor_type,
        jira_issue,
        app_cpu,
        db_cpu=None,
        lb_cpu=None,
        server_iterator=1
):
    try:
        limits = {
            "High Performance Processor": VSPHERE_HIGHPERF_CLUSTER_CPU_LIMIT,
            "Normal Processor": VSPHERE_NORMAL_CLUSTER_CPU_LIMIT,
        }

        if vm_processor_type not in limits:
            logger.error(
                f"Unsupported processor type: '{vm_processor_type}'",
                extra={
                    "issue": jira_issue.key,
                    "processor_type": vm_processor_type,
                    "valid_processor_types": list(limits.keys()),
                }
            )

            raise ValueError(
                f"cpu_validator() - Unsupported processor type: '{vm_processor_type}'"
            )

        max_cpu_cores = limits[vm_processor_type]

        if vm_category == "R II":
            if server_iterator == 1:
                target_cpu = int(app_cpu)
            elif server_iterator == 2:
                target_cpu = int(db_cpu)

        elif vm_category == "R III":
            if server_iterator == 1:
                target_cpu = int(db_cpu)
            elif server_iterator == 2:
                target_cpu = int(lb_cpu)
            elif server_iterator >= 3:
                target_cpu = int(app_cpu)
        else:
            target_cpu = int(app_cpu)

        if not (2 <= target_cpu <= max_cpu_cores):
            logger.error(
                f"VM CPU must be between [2-{VSPHERE_HIGHPERF_CLUSTER_CPU_LIMIT}]cores for '{vm_processor_type}' type, given {target_cpu}.",
                extra={
                    "issue": jira_issue.key,
                    "processor_type": vm_processor_type,
                    "maximum": max_cpu_cores,
                    "minimum": 2,
                    "requested_cpu": target_cpu,
                }
            )

            raise ValueError(
                f"VM CPU must be between [2-{VSPHERE_HIGHPERF_CLUSTER_CPU_LIMIT}]cores for '{vm_processor_type}' type, given {target_cpu}."
            )

        return target_cpu

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
            f"cpu_validator() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def disk_compactor(
        _datacenter,
        _category,
        _disk_map,
        _app_disk_count,
        _db_disk_count,
        _lb_disk_count,
        server_iterator
):
    # Output Example:
    # "disks": [
    #     {"label": "disk0", "size": 50, "type": "standard", "storage_cluster": "VNK-PS-E2U3-Std-Pool01-CUS-ABR", "unit_number": 0},
    #     {"label": "disk1", "size": 100, "type": "advanced", "storage_cluster": "VNK-PS-E2U3-Adv-Pool01-CUS-ABR", "unit_number": 1},
    #     {"label": "disk2", "size": 20, "type": "pro", "storage_cluster": "VNK-PS-E2U3-Pro-Pool01-CUS-ABR", "unit_number": 2},
    # ]

    try:
        if _category == "R II":
            if server_iterator == 1:
                target_disk_count = _app_disk_count
                target_disk_entity = 'app'
            elif server_iterator == 2:
                target_disk_count = _db_disk_count
                target_disk_entity = 'db'

        elif _category == "R III":
            if server_iterator == 1:
                target_disk_count = _db_disk_count
                target_disk_entity = 'db'
            elif server_iterator == 2:
                target_disk_count = _lb_disk_count
                target_disk_entity = 'lb'
            elif server_iterator >= 3:
                target_disk_count = _app_disk_count
                target_disk_entity = 'app'
        else:
            target_disk_count = _app_disk_count
            target_disk_entity = 'app'

        selected_disks = _disk_map[target_disk_entity]

        disks = []
        for i, disk in enumerate(selected_disks[:target_disk_count]):
            calculated_storage_cluster = vcenter_dict.get(_datacenter, {}).get("storage_cluster", {}).get(disk["type"], "N/A")
            if calculated_storage_cluster == "N/A":
                logger.error(
                    f"disk_compactor() failed to calculate storage cluster from storage type",
                    extra={
                        "issue": JIRA_TICKET_KEY,
                        "disks": disk,
                        "datacenter": _datacenter,
                        "vcenter_dict": vcenter_dict,
                    }
                )
                raise

            disks.append({
                "label": f"disk{i}",
                "size": disk["size"],
                "type": disk["type"],
                "storage_cluster": calculated_storage_cluster,
                "unit_number": i
            })

        logger.info(
            f"disk_compactor() compacted disks",
            extra={
                "issue": JIRA_TICKET_KEY,
                "disks": disks
            }
        )
        return disks

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
            f"disk_compactor() failed",
            extra={
                "issue": JIRA_TICKET_KEY,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def reporter(
        jira_issue,
        user_natid,
        virtual_machines: dict,
):
    try:

        html_msg = f"""
        <!DOCTYPE html>

        <html lang="fa" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>اطلاعات دسترسی به سرور</title>
        </head>

        <body style="margin:0; padding:0; background-color:#f4f6f8; font-family:DiodrumArabic-Regular,Tahoma, Arial, sans-serif; color:#263238;">

        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f6f8; padding:30px 0;">
        <tr>
        <td align="center">

        <table width="700" cellpadding="0" cellspacing="0" border="0"
            style="background-color:#ffffff; border-radius:10px; overflow:hidden;">

        <tr>
            <td style="background-color:#1f4e79; padding:24px 30px;">
                <div style="font-size:22px; font-weight:bold; color:#ffffff;">
                    اطلاعات دسترسی به سرور - تیکت {jira_issue.key}
                </div>
                <div style="font-size:13px; color:#dceaf5; margin-top:7px;">
                    تیم پشتیبانی فنی ابرآمد
                </div>
            </td>
        </tr>

        <tr>
            <td style="padding:30px;">

                <p style="font-size:15px; line-height:2; margin-top:0;">
                    با سلام و احترام
                </p>

                <p style="font-size:15px; line-height:2;">
                    همراه گرامی ابرآمد،
                </p>

                <p style="font-size:14px; line-height:2.1;">
                    ضمن تشکر از انتخاب ابرآمد، به اطلاع می‌رساند جهت امن‌سازی سرویس ارائه‌شده،
                    دسترسی به سرور شما در زیرساخت ابرآمد از طریق بستر VPN امکان‌پذیر می‌باشد.
                    جهت اتصال به VPN لطفاً از نرم‌افزار FortiClient استفاده نمایید.
                </p>

                <!-- VPN -->
                <div style="font-size:16px; font-weight:bold; color:#1f4e79; margin:22px 0 10px;">
                    اطلاعات دسترسی VPN/RDP
                </div>

                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                    style="border-collapse:collapse; font-size:13px; margin-bottom:22px;">

                    <tr>
                        <td width="65%" style="padding:12px; border:1px solid #dce3ea; direction:ltr; text-align:left; font-family:DiodrumArabic-Regular,Consolas,monospace;">
                            {user_natid}@cloud.local
                        </td>
                        <td style="padding:12px; border:1px solid #dce3ea; direction:ltr; font-weight:bold;">
                            VPN/RDP Username
                        </td>
                    </tr>

                    <tr style="background-color:#f8fafc;">
                        <td style="padding:12px; border:1px solid #dce3ea; direction:ltr; text-align:left;">
                            Set/Change password via "selfservice.abramad.com"
                        </td>
                        <td style="padding:12px; border:1px solid #dce3ea; direction:ltr; font-weight:bold;">
                            VPN/RDP Password
                        </td>
                    </tr>

                </table>

                <!-- Password -->
                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                    style="background-color:#fff8e6; border-right:4px solid #f0ad00; margin-bottom:22px;">
                    <tr>
                        <td style="padding:15px 18px; font-size:13px; line-height:2;">

                            <strong>الزامات رمز عبور</strong><br>

                            رمز عبور کاربری هر <strong>180 روز</strong> منقضی می‌شود.
                            در صورت مشاهده خطای
                            <span style="direction:ltr; display:inline-block;"><strong>Permission Denied</strong></span>
                            هنگام اتصال FortiClient، لطفاً از طریق سامانه
                            <span style="direction:ltr; display:inline-block;"><strong>selfservice.abramad.com</strong></span>
                            نسبت به تغییر رمز عبور اقدام نمایید.

                            <br><br>

                            رمز عبور باید <strong>حداقل 14 کاراکتر</strong> و شامل عدد، حروف بزرگ، حروف کوچک و کاراکتر ویژه (Symbol) باشد نیز، نباید شامل کد ملی، شماره موبایل، نام و یا نام خانوادگی ثبت‌شده در سامانه سلف‌سرویس باشد.

                        </td>
                    </tr>
                </table>

                <!-- Server -->
                <div style="font-size:16px; font-weight:bold; color:#1f4e79; margin-bottom:10px;">
                    اطلاعات سرورها
                </div>
        """

        
        # ============================================================
        # VM INFORMATION
        # ============================================================

        for vm_name, vm in virtual_machines.items():

            html_msg += f"""
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                style="border-collapse:collapse; font-size:13px; margin-bottom:22px; direction:ltr;">

                <!-- General Information Header -->
                <tr>
                    <td colspan="2"
                        style="padding:14px 12px;
                            border:1px solid #dce3ea;
                            background-color:#eef3f7;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;
                            color:#1f4e79;">
                        General Information
                    </td>
                </tr>

                <!-- {vm_name} -->
                <tr>
                    <td width="35%"
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;">
                        Server Name
                    </td>

                    <td width="65%"
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-family:DiodrumArabic-Regular,Consolas,monospace;">
                        {vm_name}
                    </td>
                </tr>

                <!-- CPU -->
                <tr style="background-color:#f8fafc;">
                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;">
                        CPU
                    </td>

                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-family:DiodrumArabic-Regular,Consolas,monospace;">
                        {vm.get('num_cpus', 'N/A')} Cores
                    </td>
                </tr>

                <!-- Memory -->
                <tr>
                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;">
                        Memory
                    </td>

                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-family:DiodrumArabic-Regular,Consolas,monospace;">
                        {int(vm.get('memory', 0)) / 1024:g} GB
                    </td>
                </tr>

                <!-- Private IP -->
                <tr style="background-color:#f8fafc;">
                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;">
                        Private IP
                    </td>

                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-family:DiodrumArabic-Regular,Consolas,monospace;">
                        {{PRIVATE_IP:{vm_name}}}
                    </td>
                </tr>

                <!-- Public IP -->
                <tr>
                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;">
                        Public IP
                    </td>

                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-family:DiodrumArabic-Regular,Consolas,monospace;">
                        {vm.get('custom_attrs', {}).get('Public IP', 'N/A')}
                    </td>
                </tr>

                <!-- URL -->
                <tr style="background-color:#f8fafc;">
                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;">
                        URL
                    </td>

                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-family:DiodrumArabic-Regular,Consolas,monospace;">
                        {vm.get('custom_attrs', {}).get('URL', 'N/A')}
                    </td>
                </tr>

            """

            # ============================================================
            # DISK INFORMATION
            # ============================================================

            disks = vm.get('disks', [])

            if disks:

                html_msg += """
                <!-- Disk Information Header -->
                <tr>
                    <td colspan="2"
                        style="padding:14px 12px;
                            border:1px solid #dce3ea;
                            background-color:#eef3f7;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;
                            color:#1f4e79;">
                        Disk Information
                    </td>
                </tr>
                """

                for disk_index, disk in enumerate(disks):

                    # Alternate disk background
                    disk_background = "#ffffff" if disk_index % 2 == 0 else "#f8fafc"

                    html_msg += f"""
                    <!-- {disk.get('label', f'Disk {disk_index}')} -->

                    <tr style="background-color:{disk_background};">
                        <td
                            style="padding:12px;
                                border:1px solid #dce3ea;
                                direction:ltr;
                                text-align:left;
                                font-weight:bold;">
                            Disk
                        </td>

                        <td
                            style="padding:12px;
                                border:1px solid #dce3ea;
                                direction:ltr;
                                text-align:left;
                                font-family:DiodrumArabic-Regular,Consolas,monospace;">
                            {disk.get('label', 'N/A')}
                        </td>
                    </tr>

                    <tr style="background-color:{disk_background};">
                        <td
                            style="padding:12px;
                                border:1px solid #dce3ea;
                                direction:ltr;
                                text-align:left;
                                font-weight:bold;">
                            Size
                        </td>

                        <td
                            style="padding:12px;
                                border:1px solid #dce3ea;
                                direction:ltr;
                                text-align:left;
                                font-family:DiodrumArabic-Regular,Consolas,monospace;">
                            {disk.get('size', 'N/A')} GB - {disk.get('type', 'N/A')}
                        </td>
                    </tr>
                    """

            else:

                html_msg += """
                <!-- No Disks -->
                <tr>
                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-weight:bold;">
                        Disks
                    </td>

                    <td
                        style="padding:12px;
                            border:1px solid #dce3ea;
                            direction:ltr;
                            text-align:left;
                            font-family:DiodrumArabic-Regular,Consolas,monospace;">
                        N/A
                    </td>
                </tr>
                """

            html_msg += """
            </table>
            """



        # ============================================================
        # ADDITIONAL DATA
        # ============================================================

        for vm_name, vm in virtual_machines.items():

            # VM-specific additional information
            # This checks the VM NAME because vm_name is the dictionary key.

            if vm.get('custom_attrs', {}).get('ProductLine') == 'Sepidar Server':

                html_msg += f"""
                <!-- Additional Data -->

                <div style="font-size:16px; font-weight:bold; color:#1f4e79; margin-bottom:10px;">
                    اطلاعات جانبی
                </div>

                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                    style="border-collapse:collapse; font-size:13px; margin-bottom:22px;">

                    <tr>
                        <td width="65%" style="padding:12px; border:1px solid #dce3ea; direction:ltr; text-align:left; font-family:DiodrumArabic-Regular,Consolas,monospace;">
                            {vm.get('vm_lock_addr', 'N/A')}
                        </td>
                        <td style="padding:12px; border:1px solid #dce3ea; direction:ltr; font-weight:bold;">
                            Lock Server Address
                        </td>
                    </tr>

                </table>
                """

        # ============================================================
        # DOWNLOADS
        # ============================================================

        html_msg += f"""
                <!-- Downloads -->

                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                    style="background-color:#f1f8f4; border-right:4px solid #35a66f; margin-bottom:25px;">

                    <tr>
                        <td style="padding:10px 18px; font-size:13px">
                            <strong>نرم‌افزار و راهنمای اتصال</strong><br><br>

                            راهنمای FortiClient - مرکز داده ونک<br>

                            <a href="https://abramad.thr-storage.abramad.com/support/Forti-404--Guide/VPN-vanak-404.pdf"
                            style="color:#1f6fb2;">
                                مشاهده / دانلود راهنما
                            </a>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:10px 18px; font-size:13px">
                            راهنمای FortiClient - مرکز داده میرعماد<br>

                            <a href="https://abramad.thr-storage.abramad.com/support/Forti-404--Guide/VPN-Miremad.pdf"
                            style="color:#1f6fb2;">
                                مشاهده / دانلود راهنما
                            </a>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:10px 18px; font-size:13px">
                            نرم‌افزار FortiClient<br>

                            <a {FORTICLIENT_DOWNLOAD_URL}"
                            style="color:#1f6fb2;">
                                دانلود FortiClient
                            </a>
                        </td>
                    </tr>

                </table>

            </td>
        </tr>

        <tr>
            <td style="background-color:#f4f6f8; padding:15px 30px; text-align:center; font-size:11px; color:#78909c;">
                تیم پشتیبانی فنی ابرآمد
            </td>
        </tr>

        </table>

        </td>
        </tr>
        </table>

        </body>
        </html>
        """

        # ============================================================
        # SAVE HTML REPORT FOR GITLAB PAGES
        # ============================================================

        report_dir = os.path.join(
            "reports",
            jira_issue.key
        )

        os.makedirs(report_dir, exist_ok=True)

        report_path = os.path.join(
            report_dir,
            "index.html"
        )

        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(html_msg)

        print(f"HTML report created: {report_path}")


    except Exception as err:

        global error_string_detail
        global error_string_summary
        global success

        success = False

        error_string_summary += (
            f"{type(err).__name__}: {err}"
        )

        tb = traceback.extract_tb(err.__traceback__)
        last_call = tb[-1]

        error_string_detail += (
            f"Error occurred in line {last_call.lineno}: "
            f"{last_call.line}"
        )

        print(
            f"Script failed: "
            f"{error_string_summary}\n"
            f"{error_string_detail}"
        )

        logger.error(
            "reporter() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )

        raise





def url_selector(_base_name, vm_product_line, jira_issue):
    try:
        if vm_product_line == "Rahkaran Server":
            url = f"https://{_base_name}-r.abramad.cloud"
        elif vm_product_line == "BI Server":
            url = f"https://{_base_name}-b.abramad.cloud"
        else:
            return None

        logger.info(
            "URL selected",
            extra={
                "issue": jira_issue.key,
                "url": url,
            }
        )

        return url

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
            f"url_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def attribute_selector(
        vm_product_line,
        vm_category,
        _creation_date_time,
        _url,
        _public_ip,
        _company_name,
        _national_id,
        _native_backup_needed,
        _dongle_enabled,
        _idsips_enabled,
        _waf_enabled,
        _stsvpn_enabled,
        _industry,
        _business_value,
        _agent_email,
        _agent_fullname,
        _agent_phone,

        _sepidar_lock,
        _vra_server,
        jira_issue,
        server_iterator=1,
):
    # Initials
    custom_attributes = {
        "CompanyName": _company_name,
        "Creation Date": _creation_date_time,
        "Creation Ticket ID": jira_issue.key,
        "National ID": _national_id,
        "NativeBackup": str(_native_backup_needed),
        "Physical Dongle": str(_dongle_enabled),
        "IDS/IPS": str(_idsips_enabled),
        "WAF Service": str(_waf_enabled),
        "Site-to-Site VPN": str(_stsvpn_enabled),
        "Owner": "Support Team",
        "ProductLine": vm_product_line,
        "Business Value": _business_value,
        "RepMail": _agent_email,
        "RepName": _agent_fullname,
        "RepNumber": _agent_phone,
    }

    try:
        # Rahkaran
        if vm_product_line == "Rahkaran Server":
            custom_attributes["Industry"] = _industry

            if vm_category == "R I":
                if server_iterator == 1:  # Main Server
                    custom_attributes["URL"] = _url
                    custom_attributes["Public IP"] = _public_ip

            elif vm_category == "R II":
                if server_iterator == 1:  # App Server
                    custom_attributes["URL"] = _url
                    custom_attributes["Public IP"] = _public_ip

            elif vm_category == "R III":
                if server_iterator == 2:  # LB Server
                    custom_attributes["URL"] = _url
                    custom_attributes["Public IP"] = _public_ip

        # BI
        if vm_product_line == "BI Server":
            custom_attributes["Link-VraServer"] = _vra_server
            custom_attributes["URL"] = _url
            custom_attributes["Public IP"] = _public_ip

        # Sepidar
        if vm_product_line == "Sepidar Server":
            custom_attributes["Public IP"] = _public_ip
            custom_attributes["Sepidar-Lock"] = _sepidar_lock

        # IaaS/Managed IaaS
        if vm_product_line == "IaaS Server" or vm_product_line == "Managed IaaS Server":
            custom_attributes["Public IP"] = _public_ip

        logger.info(
            "Custom attributes selected",
            extra={
                "issue": jira_issue.key,
                "custom_attributes": custom_attributes,
            }
        )

        return custom_attributes

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
            f"attribute_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise


def tehran_datetime():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_tehran = now_utc.astimezone(ZoneInfo("Asia/Tehran"))
    d = jdatetime.datetime.fromgregorian(datetime=now_tehran)

    return d.strftime('%Y/%m/%d-%H:%M')


def vcenter_folder_selector(
        _is_new_customer,
        _base_name,
        vm_product_line,
        jira_issue
):
    try:
        if _is_new_customer:
            customer_status = "new"

            # Rahkaran
            if vm_product_line == "Rahkaran Server":
                vc_folder = f"AbramadCustomers/Rahkaran/{_base_name}"
            # BI
            elif vm_product_line == "BI Server":
                vc_folder = f"AbramadCustomers/BI/{_base_name}"
            # Sepidar
            elif vm_product_line == "Sepidar Server":
                vc_folder = f"AbramadCustomers/Sepidar/{_base_name}"
            # IaaS
            elif vm_product_line == "IaaS Server":
                vc_folder = f"AbramadCustomers/IaaS/{_base_name}"
            # Managed IaaS
            elif vm_product_line == "Managed IaaS Server":
                vc_folder = f"AbramadCustomers/ManagedIaaS/{_base_name}"
            else:
                logger.error(
                    f"Unsupported product line. No automation procedure available for '{vm_product_line}'",
                    extra={
                        "issue": jira_issue.key,
                        "product_line": vm_product_line,
                    }
                )

                raise ValueError(
                    f"Unsupported product line. No automation procedure available for '{vm_product_line}'"
                )

        else:
            customer_status = "old"

            if '/' in _base_name:
                vc_folder = _base_name
            
            else:
                logger.error(
                    f"Invalid vcenter folder inputed.",
                    extra={
                        "issue": jira_issue.key,
                        "product_line": vm_product_line,
                        "input_vcenter_folder": _base_name
                    }
                )


        logger.info(
            "vCenter folder selected",
            extra={
                "issue": jira_issue.key,
                "vcenter_folder": vc_folder,
                "customer_status": customer_status
            }
        )

        return vc_folder

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
            f"vcenter_folder_selector() failed",
            extra={
                "issue": jira_issue.key,
                "error_summary": error_string_summary,
                "error_detail": error_string_detail,
            }
        )
        raise

