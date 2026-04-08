# Rapidly infrastructure — SSH key registered with Hetzner Cloud.
#
# The matching private key is stored as the HETZNER_SSH_KEY GitHub Actions
# secret and used by .github/workflows/deploy-hetzner.yml to roll out new
# Docker images.

resource "hcloud_ssh_key" "deploy" {
  name       = "rapidly-${var.environment}-deploy"
  public_key = var.ssh_public_key
  labels     = local.base_labels
}
