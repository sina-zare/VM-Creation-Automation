variable "vcenter" {
  type = object({
    datacenter_name = string
    vc_addr         = string
  })
}

variable "vms" {
  type = map(object({
    os_type         = string
    zabbix_server   = string
    template_name   = string
    compute_cluster = string
    vcenter_folder  = string
    num_cpus        = number
    memory          = number

    disks = list(object({
      label           = string
      size            = number
      type            = string
      storage_cluster = string
      unit_number     = number
      datastore       = string
    }))

    network = object({
      portgroup_name = string
      ipv4_addr      = optional(string)
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
  type = object({
    ad_ou                = string
    ad_desc              = string
    domain               = string
    domain_join_user     = optional(string)
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

variable "custom_attribute_names" {
  type = set(string)
  default = [
    "Owner", "CompanyName", "Creation Ticket ID", "National ID",
    "Creation Date", "ProductLine", "Public IP", "RepMail", "Business Value","Link-VraServer",
    "RepName", "RepNumber", "URL", "IDS/IPS", "Sepidar-Lock", "Industry", 
    "Physical Dongle", "Site-to-Site VPN", "WAF Service", "NativeBackup"
  ]
}
