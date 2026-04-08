# Rapidly infrastructure — terraform import blocks
#
# Uncomment and fill in the Hetzner resource IDs to adopt the existing
# manually-provisioned production stack instead of creating a parallel one.
#
# Usage:
#   1. Run `dev/fetch-hetzner-ids.sh` with your HCLOUD_TOKEN to print all
#      Hetzner resource IDs for this project.
#   2. Replace each "<REPLACE_...>" placeholder below with the real ID.
#   3. Run `terraform plan` — expect drift between the HCL and reality.
#   4. Fix the HCL to match the live state, or accept the planned changes.
#   5. Once `terraform plan` says "No changes", terraform manages these
#      resources and future changes flow through `terraform apply`.
#
# After a successful import, you can delete or comment out this file —
# the import blocks are only needed once.

# ── Network ────────────────────────────────────────────────────────────
#
# import {
#   to = hcloud_network.rapidly
#   id = "<REPLACE_NETWORK_ID>"   # integer, e.g. "12345678"
# }
#
# import {
#   to = hcloud_network_subnet.private
#   id = "<REPLACE_NETWORK_ID>-10.0.1.0/24"   # format: "{network_id}-{subnet_cidr}"
# }

# ── SSH Key ────────────────────────────────────────────────────────────
#
# import {
#   to = hcloud_ssh_key.deploy
#   id = "<REPLACE_SSH_KEY_ID>"   # integer
# }

# ── Firewalls ──────────────────────────────────────────────────────────
#
# import {
#   to = hcloud_firewall.app
#   id = "<REPLACE_FIREWALL_APP_ID>"   # integer
# }
#
# import {
#   to = hcloud_firewall.database
#   id = "<REPLACE_FIREWALL_DB_ID>"   # integer
# }
#
# import {
#   to = hcloud_firewall.cache
#   id = "<REPLACE_FIREWALL_CACHE_ID>"   # integer
# }

# ── Servers ────────────────────────────────────────────────────────────
#
# import {
#   to = hcloud_server.app
#   id = "<REPLACE_SERVER_APP_ID>"   # integer
# }
#
# import {
#   to = hcloud_server.database
#   id = "<REPLACE_SERVER_DB_ID>"   # integer
# }
#
# import {
#   to = hcloud_server.cache
#   id = "<REPLACE_SERVER_CACHE_ID>"   # integer
# }

# ── Volume + Attachment ────────────────────────────────────────────────
#
# import {
#   to = hcloud_volume.pgdata
#   id = "<REPLACE_VOLUME_ID>"   # integer
# }
#
# import {
#   to = hcloud_volume_attachment.pgdata
#   id = "<REPLACE_VOLUME_ID>"   # same integer as the volume
# }
