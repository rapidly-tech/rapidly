# Rapidly infrastructure — PostgreSQL server with persistent volume.
#
# Postgres is reachable from the app server only over the private network
# (no public port is opened by the database firewall). The data directory
# lives on a separate Hetzner Cloud volume so the server can be rebuilt
# without losing state.

locals {
  database_user_data = <<-EOT
    #cloud-config
    package_update: true
    package_upgrade: true
    packages:
      - ca-certificates
      - curl
      - gnupg
      - xfsprogs
    runcmd:
      - install -m 0755 -d /etc/apt/keyrings
      - curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
      - chmod a+r /etc/apt/keyrings/docker.asc
      - echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
      - apt-get update
      - apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
      - systemctl enable --now docker
      - install -d -m 0700 -o root -g root /var/lib/postgresql
  EOT
}

resource "hcloud_volume" "pgdata" {
  name              = "rapidly-${var.environment}-pgdata"
  size              = var.database_volume_size
  location          = var.location
  format            = "xfs"
  delete_protection = true
  labels            = merge(local.base_labels, { role = "database" })
}

resource "hcloud_server" "database" {
  name        = "rapidly-${var.environment}-database"
  server_type = var.database_server_type
  image       = var.image
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.deploy.id]
  user_data   = local.database_user_data
  labels      = merge(local.base_labels, { role = "database" })

  firewall_ids = [hcloud_firewall.database.id]

  # Defense in depth: Postgres data lives on the volume, but Hetzner backups
  # also snapshot the root disk in case the cloud-init bootstrap drifts.
  backups            = true
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

resource "hcloud_volume_attachment" "pgdata" {
  volume_id = hcloud_volume.pgdata.id
  server_id = hcloud_server.database.id
  automount = true
}
