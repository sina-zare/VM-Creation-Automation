terraform {
  required_providers {
    vsphere = {
      source  = "vmware/vsphere"
      version = "2.16.1"
    }
  }
}

provider "vsphere" {
  vsphere_server       = var.vcenter.vc_addr
  allow_unverified_ssl = true
}
