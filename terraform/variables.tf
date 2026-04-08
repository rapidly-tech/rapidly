# Rapidly infrastructure — input variables

variable "hcloud_token" {
  description = "Hetzner Cloud API token with read+write scope. Set via HCP Terraform Cloud workspace variables and mark as sensitive."
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Deployment environment name (production, sandbox, test). Used as a label and name suffix on all resources."
  type        = string

  validation {
    condition     = contains(["production", "sandbox", "test"], var.environment)
    error_message = "environment must be one of: production, sandbox, test."
  }
}

variable "location" {
  description = "Hetzner Cloud datacenter location. See https://docs.hetzner.com/cloud/general/locations/."
  type        = string
  default     = "fsn1"
}

variable "network_zone" {
  description = "Hetzner Cloud network zone. Must contain the chosen location."
  type        = string
  default     = "eu-central"
}

variable "image" {
  description = "Base OS image to provision on every server."
  type        = string
  default     = "ubuntu-24.04"
}

variable "app_server_type" {
  description = "Hetzner Cloud server type for the application node (frontend + API + workers)."
  type        = string
  default     = "ccx23"
}

variable "database_server_type" {
  description = "Hetzner Cloud server type for the PostgreSQL node."
  type        = string
  default     = "ccx13"
}

variable "cache_server_type" {
  description = "Hetzner Cloud server type for the Redis node."
  type        = string
  default     = "cx22"
}

variable "database_volume_size" {
  description = "Size in GB of the persistent volume mounted on the PostgreSQL node."
  type        = number
  default     = 100
}

variable "ssh_public_key" {
  description = "OpenSSH-formatted public key authorised to log into every server. The matching private key is stored as the HETZNER_SSH_KEY GitHub Actions secret."
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "List of CIDR blocks permitted to open SSH (port 22) to any server. Required — no default — so every workspace must deliberately choose how exposed the SSH surface is. Use [\"0.0.0.0/0\", \"::/0\"] to allow GitHub Actions runners; restrict to a bastion or VPN CIDR for production."
  type        = list(string)

  validation {
    condition     = length(var.ssh_allowed_cidrs) > 0
    error_message = "ssh_allowed_cidrs must contain at least one CIDR block."
  }
}

variable "labels" {
  description = "Extra labels merged into the standard label set on every Hetzner resource."
  type        = map(string)
  default     = {}
}
