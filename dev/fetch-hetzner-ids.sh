#!/usr/bin/env bash
# Rapidly — dump all Hetzner Cloud resource IDs for terraform import
#
# Usage:
#   export HCLOUD_TOKEN="your-hetzner-api-token"
#   bash dev/fetch-hetzner-ids.sh
#
# The output shows every resource's integer ID, name, and metadata.
# Copy the IDs into terraform/imports.tf to adopt existing infra.
#
# Prerequisites:
#   - hcloud CLI: https://github.com/hetznercloud/cli
#     brew install hetznercloud/tap/hcloud  (macOS)
#     snap install hcloud                    (Ubuntu)
#   - HCLOUD_TOKEN env var with read scope

set -euo pipefail

if ! command -v hcloud &>/dev/null; then
  echo "Error: hcloud CLI not found. Install it first:"
  echo "  brew install hetznercloud/tap/hcloud   (macOS)"
  echo "  snap install hcloud                     (Ubuntu)"
  exit 1
fi

if [ -z "${HCLOUD_TOKEN:-}" ]; then
  echo "Error: HCLOUD_TOKEN environment variable is not set."
  echo "  export HCLOUD_TOKEN=\"your-token-here\""
  exit 1
fi

echo "=== Servers ==="
hcloud server list -o columns=id,name,status,server_type,datacenter,ipv4,created
echo

echo "=== Networks ==="
hcloud network list -o columns=id,name,ip_range
echo

echo "=== Network Subnets ==="
for net_id in $(hcloud network list -o noheader -o columns=id); do
  echo "Network $net_id subnets:"
  hcloud network describe "$net_id" -o json | jq -r '.subnets[] | "  type=\(.type) ip_range=\(.ip_range) network_zone=\(.network_zone)"'
done
echo

echo "=== SSH Keys ==="
hcloud ssh-key list -o columns=id,name,fingerprint
echo

echo "=== Firewalls ==="
hcloud firewall list -o columns=id,name
echo

echo "=== Volumes ==="
hcloud volume list -o columns=id,name,size,server,location,created
echo

echo "=== Floating IPs (if any) ==="
hcloud floating-ip list -o columns=id,type,ip,server,home_location 2>/dev/null || echo "(none or unsupported)"
echo

echo "=== Done ==="
echo
echo "Copy the integer IDs from the output above into terraform/imports.tf,"
echo "then run: cd terraform && terraform init && terraform plan"
