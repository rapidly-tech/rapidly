# Rapidly infrastructure — private network shared by every Hetzner server.

locals {
  base_labels = merge(
    {
      project     = "rapidly"
      environment = var.environment
      managed-by  = "terraform"
    },
    var.labels,
  )

  network_cidr = "10.0.0.0/16"
  subnet_cidr  = "10.0.0.0/24"
}

resource "hcloud_network" "rapidly" {
  name     = "rapidly-internal"
  ip_range = local.network_cidr
  labels   = local.base_labels
}

resource "hcloud_network_subnet" "private" {
  network_id   = hcloud_network.rapidly.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = local.subnet_cidr
}
