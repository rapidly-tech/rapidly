# Rapidly infrastructure — Redis cache and dramatiq broker.
#
# Reachable from the app server only over the private network. Redis state
# is intentionally ephemeral, so no persistent volume is attached.

locals {
  cache_user_data = <<-EOT
    #cloud-config
    package_update: true
    package_upgrade: true
    packages:
      - ca-certificates
      - curl
      - gnupg
    runcmd:
      - install -m 0755 -d /etc/apt/keyrings
      - curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
      - chmod a+r /etc/apt/keyrings/docker.asc
      - echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
      - apt-get update
      - apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
      - systemctl enable --now docker
  EOT
}

resource "hcloud_server" "cache" {
  name        = "rapidly-${var.environment}-cache"
  server_type = var.cache_server_type
  image       = var.image
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.deploy.id]
  user_data   = local.cache_user_data
  labels      = merge(local.base_labels, { role = "cache" })

  firewall_ids = [hcloud_firewall.cache.id]

  delete_protection  = local.protect_servers
  rebuild_protection = local.protect_servers

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  network {
    network_id = hcloud_network.rapidly.id
  }

  depends_on = [hcloud_network_subnet.private]
}
