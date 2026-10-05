module "vm" {
  source = "../modules/vm"

  vcenter                = var.vcenter
  vms                    = var.vms
  ad_info                = var.ad_info
  custom_attribute_names = var.custom_attribute_names

  domain_join_password = var.domain_join_password
  domain_join_user     = var.domain_join_user
  local_admin_password = var.local_admin_password

}


# When firewall-policy / dns-record modules exist, add their calls here too,
# e.g.:
# module "firewall_policy" {
#   source   = "../../modules/firewall-policy"
#   vm_ips   = module.vm.vm_ips
# }

output "vm_ids" {
  value = module.vm.vm_ids
}

output "vm_ips" {
  value = module.vm.vm_ips
}
