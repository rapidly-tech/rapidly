# Rapidly infrastructure — SSH key registered with Hetzner Cloud.

resource "hcloud_ssh_key" "deploy" {
  name       = "rapidly-key"
  public_key = var.ssh_public_key
  labels     = local.base_labels
}
