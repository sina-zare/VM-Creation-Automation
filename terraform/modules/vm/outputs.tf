output "vm_ids" {
  description = "vSphere managed object IDs, keyed by VM name"
  value       = { for k, v in vsphere_virtual_machine.vm : k => v.id }
}

output "vm_ips" {
  description = "Guest IPs reported by VMware Tools once customization completes"
  value       = { for k, v in vsphere_virtual_machine.vm : k => v.default_ip_address }
}
