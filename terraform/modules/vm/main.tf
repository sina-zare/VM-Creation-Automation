locals {
  # Builds { <custom-attribute-id> = <value> } per VM from each VM's
  # custom_attrs map. Anything whose key isn't in var.custom_attribute_names
  # is silently skipped.
  final_custom_attrs = {
    for vm_key, vm in var.vms : vm_key => {
      for attr_name, attr_value in vm.custom_attrs :
      data.vsphere_custom_attribute.attrs[attr_name].id => attr_value
      if contains(var.custom_attribute_names, attr_name)
    }
  }
}

resource "vsphere_folder" "customer_folder" {
  for_each = toset([
    for vm in var.vms : vm.vcenter_folder
  ])

  path          = each.value
  type          = "vm"
  datacenter_id = data.vsphere_datacenter.dc.id
}

resource "vsphere_virtual_machine" "vm" {
  for_each = var.vms

  name             = each.key
  folder           = each.value.vcenter_folder
  resource_pool_id = data.vsphere_compute_cluster.vm_cluster[each.key].resource_pool_id
  datastore_id     = data.vsphere_datastore.ds[each.value.disks[0].datastore].id
  firmware         = "efi"

  num_cpus = each.value.num_cpus
  memory   = each.value.memory
  guest_id = data.vsphere_virtual_machine.templates[each.key].guest_id

  cpu_hot_add_enabled    = true
  memory_hot_add_enabled = true

  network_interface {
    network_id = data.vsphere_network.vm_network[each.key].id
  }

  dynamic "disk" {
    for_each = each.value.disks
    content {
      label            = disk.value.label
      size             = disk.value.size
      unit_number      = disk.value.unit_number
      datastore_id     = data.vsphere_datastore.ds[disk.value.datastore].id
      thin_provisioned = true
    }
  }

  clone {
    template_uuid = data.vsphere_virtual_machine.templates[each.key].id

    customize {
      dynamic "linux_options" {
        for_each = each.value.os_type == "linux" ? [1] : []
        content {
          host_name = lower(each.key)
          domain    = var.ad_info.domain
        }
      }

      dynamic "windows_options" {
        for_each = each.value.os_type == "windows" ? [1] : []
        content {
          computer_name         = each.key
          admin_password        = var.local_admin_password
          join_domain           = var.ad_info.domain
          domain_admin_user     = var.domain_join_user
          domain_admin_password = var.domain_join_password
          time_zone             = var.ad_info.timezone
        }
      }

      network_interface {
        ipv4_address = each.value.network.ipv4_addr # null => DHCP
        ipv4_netmask = each.value.network.subnet_mask
      }

      ipv4_gateway    = each.value.network.gw_addr
      dns_server_list = each.value.network.dns_addr_list
      dns_suffix_list = each.value.network.dns_sfx_list
    }
  }

  custom_attributes = local.final_custom_attrs[each.key]

  # Ignore changes if below sections differed from state in future.
  lifecycle {
    ignore_changes = [
      num_cpus,
      memory,
      disk,
      clone[0].customize,
    ]
  }
  
  depends_on = [vsphere_folder.customer_folder]
}
