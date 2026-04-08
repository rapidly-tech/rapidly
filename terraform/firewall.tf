# Rapidly infrastructure — Hetzner Cloud firewalls per role.
#
# Public ingress to HTTP/HTTPS is intentionally NOT opened on the app server.
# All web traffic enters the cluster through a Cloudflare Tunnel, so only
# SSH from trusted CIDRs needs to be reachable from the public internet.
# PostgreSQL and Redis stay private — their firewalls only permit SSH.

resource "hcloud_firewall" "app" {
  name   = "rapidly-${var.environment}-app"
  labels = local.base_labels

  rule {
    description = "SSH from trusted CIDRs"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allowed_cidrs
  }

  rule {
    description = "ICMP echo (ping)"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_firewall" "database" {
  name   = "rapidly-${var.environment}-database"
  labels = local.base_labels

  rule {
    description = "SSH from trusted CIDRs"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allowed_cidrs
  }

  rule {
    description = "ICMP echo (ping)"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_firewall" "cache" {
  name   = "rapidly-${var.environment}-cache"
  labels = local.base_labels

  rule {
    description = "SSH from trusted CIDRs"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allowed_cidrs
  }

  rule {
    description = "ICMP echo (ping)"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}
