# Rapidly infrastructure — private network shared by every Hetzner server.
#
# All inter-service traffic (frontend ↔ api ↔ postgres ↔ redis) flows over
# this network, so the application processes can bind to private IPs and the
# firewalls below can drop public traffic.

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
  subnet_cidr  = "10.0.1.0/24"

  # Production gets stricter safeguards: terraform cannot destroy or rebuild
  # protected servers without first flipping these flags off explicitly.
  protect_servers = var.environment == "production"
}

resource "hcloud_network" "rapidly" {
  name     = "rapidly-${var.environment}"
  ip_range = local.network_cidr
  labels   = local.base_labels
}

resource "hcloud_network_subnet" "private" {
  network_id   = hcloud_network.rapidly.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = local.subnet_cidr
}
