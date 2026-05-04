# Rapidly infrastructure — Redis cache and dramatiq broker.

resource "hcloud_server" "cache" {
  name         = "rapidly-redis"
  server_type  = var.cache_server_type
  image        = var.image
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.deploy.id]
  labels       = merge(local.base_labels, { role = "cache" })
  firewall_ids = [hcloud_firewall.cache.id]

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  network {
    ip         = "10.0.0.4"
    network_id = hcloud_network.rapidly.id
  }

  depends_on = [hcloud_network_subnet.private]

  lifecycle {
    ignore_changes = [user_data, image, ssh_keys, network]
  }
}
