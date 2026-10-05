data "vsphere_datacenter" "dc" {
  name = var.vcenter.datacenter_name
}

data "vsphere_compute_cluster" "vm_cluster" {
  for_each      = var.vms
  name          = each.value.compute_cluster
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_network" "vm_network" {
  for_each      = var.vms
  name          = each.value.network.portgroup_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_virtual_machine" "templates" {
  for_each      = var.vms
  name          = each.value.template_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_custom_attribute" "attrs" {
  for_each = var.custom_attribute_names
  name     = each.value
}

locals {
  # Every unique datastore name referenced by any disk, across all VMs.
  all_datastores = toset(flatten([
    for vm in var.vms : [for d in vm.disks : d.datastore]
  ]))
}

data "vsphere_datastore" "ds" {
  for_each      = local.all_datastores
  name          = each.value
  datacenter_id = data.vsphere_datacenter.dc.id
}
