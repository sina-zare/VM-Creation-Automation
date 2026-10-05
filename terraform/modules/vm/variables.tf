variable "vcenter" {
  description = "vCenter-level settings that aren't tied to one specific VM"
  type = object({
    datacenter_name = string
    vc_addr         = string
  })
}

variable "vms" {
  description = "Map of VMs to create, keyed by hostname (must match tfvars.json)"
  type = map(object({
    os_type         = string # "linux" or "windows"
    zabbix_server   = string
    template_name   = string
    compute_cluster = string
    vcenter_folder  = string
    num_cpus        = number
    memory          = number # MB

    disks = list(object({
      label           = string
      size            = number
      type            = string # informational only, not used to place the disk
      storage_cluster = string # informational only, not used to place the disk
      unit_number     = number
      datastore       = string # the actual datastore/LUN the disk is placed on
    }))

    network = object({
      portgroup_name = string
      ipv4_addr      = optional(string)      # omit/null => DHCP
      subnet_mask    = optional(number)
      gw_addr        = optional(string)
      dns_addr_list  = optional(list(string), [])
      dns_sfx_list   = optional(list(string), [])
    })

    custom_attrs = optional(map(string), {})
  }))
}

variable "domain_join_password" {
  type      = string
  sensitive = true
}

variable "local_admin_password" {
  type      = string
  sensitive = true
}

variable "domain_join_user" {
  type      = string
}

variable "ad_info" {
  description = "Active Directory configuration and user/group information"
  type = object({
    ad_ou                = string
    ad_desc              = string
    domain               = string
    timezone             = optional(number, 160)

    users = list(object({
      role      = string
      username  = string
      full_name = string
      email     = string
      phone     = string
      company   = string
      ou        = string
      groups    = list(string)
    }))

    groups = list(object({
      name        = string
      description = string
      scope       = string
      category    = string
    }))
  })
}

# Every vCenter custom attribute this module is allowed to write.
# Keys used in a VM's custom_attrs map must match one of these EXACTLY
# (case + spelling), and the attribute must already exist in vCenter. "Sales Agent"
variable "custom_attribute_names" {
  type = set(string)
  default = [
    "Owner", "CompanyName", "Creation Ticket ID", "National ID",
    "Creation Date", "ProductLine", "Public IP", "RepMail", "Business Value","Link-VraServer",
    "RepName", "RepNumber", "URL", "IDS/IPS", "Sepidar-Lock", "Industry", 
    "Physical Dongle", "Site-to-Site VPN", "WAF Service", "NativeBackup"
  ]
}
