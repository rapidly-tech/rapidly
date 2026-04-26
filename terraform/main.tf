# Rapidly infrastructure — Hetzner Cloud provider configuration
#
# Production infrastructure for rapidly.tech runs on Hetzner Cloud. The
# application code is shipped as Docker images from GHCR and rolled out by
# .github/workflows/deploy-hetzner.yml using the docker-compose stack in
# deploy/hetzner/docker-compose.production.yml.
#
# DNS is managed in Cloudflare and ingress is fronted by a Cloudflare Tunnel
# (cloudflared) running on the app server, so no public HTTP ports are
# exposed by these resources.

provider "hcloud" {
  token = var.hcloud_token
}
