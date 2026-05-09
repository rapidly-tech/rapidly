#!/usr/bin/env bash
# Rapidly infrastructure — install Tailscale on a Render instance.
# Downloads and unpacks the Tailscale binary, then creates the required
# runtime directories so Tailscale can run as a sidecar on Render.
set -x
TAILSCALE_VERSION=${TAILSCALE_VERSION:-1.94.2}
TS_FILE=tailscale_${TAILSCALE_VERSION}_amd64.tgz
wget -q "https://pkgs.tailscale.com/stable/${TS_FILE}" && tar xzf "${TS_FILE}" --strip-components=1
cp -r tailscale tailscaled /render/

mkdir -p /var/run/tailscale /var/cache/tailscale /var/lib/tailscale
