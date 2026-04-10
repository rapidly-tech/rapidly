# Rapidly infrastructure — PostgreSQL server.

resource "hcloud_server" "database" {
  name         = "rapidly-db"
  server_type  = var.database_server_type
  image        = var.image
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.deploy.id]
  labels       = merge(local.base_labels, { role = "database" })
  firewall_ids = [hcloud_firewall.database.id]
  backups      = true

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  network {
    ip         = "10.0.0.3"
    network_id = hcloud_network.rapidly.id
  }

  depends_on = [hcloud_network_subnet.private]

  lifecycle {
    ignore_changes = [user_data, image, ssh_keys, network]
  }
}
