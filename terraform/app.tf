# Rapidly infrastructure — application server.
#
# Hosts the Docker compose stack defined in
# deploy/hetzner/docker-compose.production.yml: Next.js frontend, FastAPI
# backend, dramatiq workers and the scheduler. The Cloudflare Tunnel
# (cloudflared) is installed by the deploy workflow and provides public
# ingress, so this server does not expose any HTTP ports directly.

locals {
  app_user_data = <<-EOT
    #cloud-config
    package_update: true
    package_upgrade: true
    packages:
      - ca-certificates
      - curl
      - gnupg
      - ufw
    write_files:
      - path: /etc/sysctl.d/99-rapidly.conf
        content: |
          net.core.somaxconn = 4096
          net.ipv4.tcp_max_syn_backlog = 4096
          vm.overcommit_memory = 1
    runcmd:
      - install -m 0755 -d /etc/apt/keyrings
      - curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
      - chmod a+r /etc/apt/keyrings/docker.asc
      - echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
      - apt-get update
      - apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
      - systemctl enable --now docker
      - install -d -m 0755 -o root -g root /opt/rapidly
      - sysctl --system
  EOT
}

resource "hcloud_server" "app" {
  name        = "rapidly-${var.environment}-app"
  server_type = var.app_server_type
  image       = var.image
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.deploy.id]
  user_data   = local.app_user_data
  labels      = merge(local.base_labels, { role = "app" })

  firewall_ids = [hcloud_firewall.app.id]

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
