# Rapidly infrastructure — production environment variable declarations
# Secrets and configuration inputs for the Rapidly production deployment
# =============================================================================
# Variables
# =============================================================================

variable "ghcr_auth_token" {
  description = "GitHub Container Registry auth token (Personal Access Token with read:packages scope)"
  type        = string
  sensitive   = true
}

variable "ghcr_username" {
  description = "GitHub username for GHCR authentication"
  type        = string
  sensitive   = true
}

# Google
variable "google_client_id_production" {
  description = "Google Client ID for production"
  type        = string
  sensitive   = true
}

variable "google_client_secret_production" {
  description = "Google Client Secret for production"
  type        = string
  sensitive   = true
}

# OpenAI
variable "openai_api_key_production" {
  description = "OpenAI API Key for production"
  type        = string
  sensitive   = true
}


# Backend - Production
variable "backend_current_jwk_kid_production" {
  description = "Current JWK KID for production"
  type        = string
  sensitive   = true
}

variable "backend_discord_bot_token_production" {
  description = "Discord Bot Token for production"
  type        = string
  sensitive   = true
}

variable "backend_discord_client_id_production" {
  description = "Discord Client ID for production"
  type        = string
  sensitive   = true
}

variable "backend_discord_client_secret_production" {
  description = "Discord Client Secret for production"
  type        = string
  sensitive   = true
}

variable "backend_discord_proxy_url" {
  description = "Discord Proxy URL"
  type        = string
  sensitive   = true
}

variable "backend_posthog_project_api_key_production" {
  description = "PostHog Project API Key for production"
  type        = string
  sensitive   = true
}

variable "backend_logo_dev_publishable_key_production" {
  description = "Logo.dev Publishable Key for production"
  type        = string
  sensitive   = true
}

variable "backend_secret_production" {
  description = "Backend Secret for production"
  type        = string
  sensitive   = true
}

variable "backend_sentry_dsn_production" {
  description = "Sentry DSN for production"
  type        = string
  sensitive   = true
}

variable "backend_jwks_production" {
  description = "Backend JWKS content for production"
  type        = string
  sensitive   = true
}

# AWS S3 - Production
variable "aws_access_key_id_production" {
  description = "AWS Access Key ID for production"
  type        = string
  sensitive   = true
}

variable "aws_secret_access_key_production" {
  description = "AWS Secret Access Key for production"
  type        = string
  sensitive   = true
}

# GitHub - Production
variable "github_client_id_production" {
  description = "GitHub Client ID for production"
  type        = string
  sensitive   = true
}

variable "github_client_secret_production" {
  description = "GitHub Client Secret for production"
  type        = string
  sensitive   = true
}

# Stripe - Production
variable "stripe_connect_webhook_secret_production" {
  description = "Stripe Connect Webhook Secret for production"
  type        = string
  sensitive   = true
}

variable "stripe_secret_key_production" {
  description = "Stripe Secret Key for production"
  type        = string
  sensitive   = true
}

variable "stripe_publishable_key_production" {
  description = "Stripe Publishable Key for production"
  type        = string
  sensitive   = true
}

variable "stripe_webhook_secret_production" {
  description = "Stripe Webhook Secret for production"
  type        = string
  sensitive   = true
}

# Logfire
variable "logfire_token" {
  description = "Logfire Token"
  type        = string
  sensitive   = true
}

# Apple (shared across environments)
variable "apple_client_id" {
  description = "Apple Client ID"
  type        = string
  sensitive   = true
}

variable "apple_team_id" {
  description = "Apple Team ID"
  type        = string
  sensitive   = true
}

variable "apple_key_id" {
  description = "Apple Key ID"
  type        = string
  sensitive   = true
}

variable "apple_key_value" {
  description = "Apple Key Value"
  type        = string
  sensitive   = true
}

# App Review
variable "backend_app_review_email" {
  description = "App Review Email for testing"
  type        = string
  sensitive   = true
}

variable "backend_app_review_otp_code" {
  description = "App Review OTP Code for testing"
  type        = string
  sensitive   = true
}

# Grafana Cloud Prometheus (shared across environments)
variable "grafana_cloud_prometheus_url" {
  description = "Grafana Cloud Prometheus base URL"
  type        = string
  sensitive   = true
}

variable "grafana_cloud_prometheus_username" {
  description = "Grafana Cloud Prometheus username (numeric stack ID)"
  type        = string
  sensitive   = true
}

variable "grafana_cloud_prometheus_password" {
  description = "Grafana Cloud Prometheus write API key"
  type        = string
  sensitive   = true
}

# Tinybird
variable "tinybird_api_token" {
  description = "Tinybird API Token"
  type        = string
  sensitive   = true
}

variable "tinybird_clickhouse_username" {
  description = "Tinybird ClickHouse Username"
  type        = string
  sensitive   = true
}

variable "tinybird_clickhouse_token" {
  description = "Tinybird ClickHouse Token"
  type        = string
  sensitive   = true
}

variable "tinybird_workspace" {
  description = "Tinybird Workspace name"
  type        = string
}

variable "tinybird_events_write" {
  description = "Tinybird Events Write enabled"
  type        = bool
  default     = false
}

variable "tinybird_events_read" {
  description = "Tinybird Events Read enabled"
  type        = bool
  default     = false
}

# Tailscale
variable "tailscale_authkey" {
  description = "Tailscale auth key for the subnet router"
  type        = string
  sensitive   = true
}
