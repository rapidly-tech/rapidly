
# =============================================================================
# Registry Credential
# =============================================================================

resource "render_registry_credential" "ghcr" {
  name       = "Registry Credentials for GHCR"
  registry   = "GITHUB"
  username   = var.ghcr_username
  auth_token = var.ghcr_auth_token
}

# =============================================================================
# Remote references that are managed by a different state.
# ============================================================================

data "tfe_outputs" "production" {
  organization = "rapidly-tech"
  workspace    = "rapidly"
}

data "render_postgres" "db" {
  id = data.tfe_outputs.production.values.postgres_id
}

data "render_redis" "redis" {
  id = data.tfe_outputs.production.values.redis_id
}

# =============================================================================
# Locals
# =============================================================================

locals {
  # Database connection info (derived from postgres resource)
  # db_host          = render_postgres.db.id
  db_internal_host = data.render_postgres.db.id
  db_port          = "5432"
  # db_name          = data.render_postgres.db.database_name
  db_user     = data.render_postgres.db.database_user
  db_password = data.render_postgres.db.connection_info.password

  # Read replica connection info
  read_replica = [for r in data.render_postgres.db.read_replicas : r if r.name == "rapidly-read"][0]

  # Redis connection info
  redis_host = data.render_redis.redis.id
  redis_port = "6379"
}

# =============================================================================
# Sandbox
# =============================================================================

# =============================================================================
# Service image data sources
#
# We read the current image digest from Render to avoid stale state in
# Terraform causing "unable to fetch image" errors on service updates.
#
# The service IDs are hardcoded because referencing module outputs would
# create a cyclic dependency (module -> data source -> module).
#
# First-time setup: create the services first without the data sources
# (use a default tag like "latest"), then add the data sources with the
# service IDs from `terraform state show`.
# =============================================================================

locals {
  sandbox_service_ids = {
    api                    = "srv-crkocgbtq21c73ddsdbg"
    worker-sandbox         = "srv-d089jj7diees73934kgg"
    worker-sandbox-webhook = "srv-d62q7vh4tr6s73fk44ng"
  }
}

data "render_web_service" "sandbox_api" {
  id = local.sandbox_service_ids["api"]
}

data "render_web_service" "sandbox_worker" {
  for_each = { for k, v in local.sandbox_service_ids : k => v if k != "api" }
  id       = each.value
}

# =============================================================================
# Sandbox
# =============================================================================

module "sandbox" {
  source = "../modules/render_service"

  environment            = "sandbox"
  render_environment_id  = data.tfe_outputs.production.values.sandbox_environment_id
  registry_credential_id = render_registry_credential.ghcr.id

  postgres_config = {
    host          = local.db_internal_host
    port          = local.db_port
    user          = local.db_user
    password      = local.db_password
    read_host     = local.read_replica.id
    read_port     = local.db_port
    read_user     = local.db_user
    read_password = local.db_password
  }

  redis_config = {
    host = local.redis_host
    port = local.redis_port
  }

  api_service_config = {
    allowed_hosts          = "[\"sandbox.rapidly.tech\"]"
    cors_origins           = "[\"https://sandbox.rapidly.tech\", \"https://github.com\", \"https://docs.rapidly.tech\"]"
    custom_domains         = [{ name = "sandbox-api.rapidly.tech" }]
    image_url              = data.render_web_service.sandbox_api.runtime_source.image.image_url
    image_digest           = data.render_web_service.sandbox_api.runtime_source.image.digest
    web_concurrency        = "2"
    forwarded_allow_ips    = "*"
    database_pool_size     = "20"
    postgres_database      = "rapidly_sandbox"
    postgres_read_database = "rapidly_sandbox"
    redis_db               = "1"
    plan                   = "standard"
  }

  workers = {
    worker-sandbox = {
      start_command      = "uv run dramatiq rapidly.worker.run -p 4 -t 8 -f rapidly.worker.scheduler:start --queues high_priority medium_priority low_priority"
      image_url          = data.render_web_service.sandbox_worker["worker-sandbox"].runtime_source.image.image_url
      image_digest       = data.render_web_service.sandbox_worker["worker-sandbox"].runtime_source.image.digest
      dramatiq_prom_port = "10000"
    }
    worker-sandbox-webhook = {
      start_command      = "uv run dramatiq rapidly.worker.run -p 1 -t 16 --queues webhooks"
      image_url          = data.render_web_service.sandbox_worker["worker-sandbox-webhook"].runtime_source.image.image_url
      image_digest       = data.render_web_service.sandbox_worker["worker-sandbox-webhook"].runtime_source.image.digest
      dramatiq_prom_port = "10001"
      database_pool_size = "16"
    }
  }

  google_secrets = {
    client_id     = var.google_client_id_sandbox
    client_secret = var.google_client_secret_sandbox
  }

  openai_secrets = {
    api_key = var.openai_api_key_sandbox
  }

  backend_config = {
    base_url                   = "https://sandbox-api.rapidly.tech"
    user_session_cookie_domain = "rapidly.tech"
    user_session_cookie_key    = "rapidly_sandbox_session"
    debug                      = "0"
    email_sender               = "resend"
    email_from_name            = "[SANDBOX] Rapidly"
    email_from_domain          = "notifications.sandbox.rapidly.tech"
    frontend_base_url          = "https://sandbox.rapidly.tech"
    jwks_path                  = "/etc/secrets/jwks.json"
    log_level                  = "INFO"
    testing                    = "0"
  }

  backend_secrets = {
    stripe_publishable_key   = var.stripe_publishable_key_sandbox
    current_jwk_kid          = var.backend_current_jwk_kid_sandbox
    discord_bot_token        = var.backend_discord_bot_token_sandbox
    discord_client_id        = var.backend_discord_client_id_sandbox
    discord_client_secret    = var.backend_discord_client_secret_sandbox
    discord_proxy_url        = var.backend_discord_proxy_url
    resend_api_key           = var.backend_resend_api_key_sandbox
    logo_dev_publishable_key = var.backend_logo_dev_publishable_key_sandbox
    secret                   = var.backend_secret_sandbox
    sentry_dsn               = var.backend_sentry_dsn_sandbox
    jwks                     = var.backend_jwks_sandbox
  }

  aws_s3_config = {
    region                   = "us-east-2"
    signature_version        = "v4"
    files_presign_ttl        = "3600"
    files_public_bucket_name = "rapidly-public-sandbox-files"
  }

  aws_s3_secrets = {
    access_key_id     = var.aws_access_key_id_sandbox
    secret_access_key = var.aws_secret_access_key_sandbox
  }

  github_secrets = {
    client_id     = var.github_client_id_sandbox
    client_secret = var.github_client_secret_sandbox
  }

  stripe_secrets = {
    connect_webhook_secret = var.stripe_connect_webhook_secret_sandbox
    secret_key             = var.stripe_secret_key_sandbox
    webhook_secret         = var.stripe_webhook_secret_sandbox
  }

  apple_secrets = {
    client_id = var.apple_client_id
    team_id   = var.apple_team_id
    key_id    = var.apple_key_id
    key_value = var.apple_key_value
  }

  logfire_config = {
    token = var.logfire_token
  }

  prometheus_config = {
    url      = var.grafana_cloud_prometheus_url
    username = var.grafana_cloud_prometheus_username
    password = var.grafana_cloud_prometheus_password
  }

  tinybird_config = {
    api_url             = "https://api.us-east.aws.tinybird.co"
    clickhouse_url      = "https://clickhouse.us-east.aws.tinybird.co"
    api_token           = var.tinybird_api_token
    clickhouse_username = var.tinybird_clickhouse_username
    clickhouse_token    = var.tinybird_clickhouse_token
    workspace           = var.tinybird_workspace
    events_write        = var.tinybird_events_write
    events_read         = var.tinybird_events_read
  }

  depends_on = [render_registry_credential.ghcr, data.render_postgres.db, data.render_redis.redis]
}

# =============================================================================
# Cloudflare DNS
# =============================================================================
import {
  to = cloudflare_dns_record.api
  id = "22bcd1b07ec25452aab472486bc8df94/f8b90a8fea314be71490f0b4805807cf"
}

resource "cloudflare_dns_record" "api" {
  zone_id = "22bcd1b07ec25452aab472486bc8df94"
  name    = "sandbox-api.rapidly.tech"
  type    = "CNAME"
  content = replace(module.sandbox.api_service_url, "https://", "")
  proxied = true
  ttl     = 1
}
