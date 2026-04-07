# Rapidly Render service setup
#
# Sets up a service, and the specified workers.
# Includes the environment groups

locals {
  environment = var.backend_config.environment == null ? var.environment : var.backend_config.environment
}

resource "render_env_group" "google" {
  environment_id = var.render_environment_id
  name           = "google-${var.environment}"
  env_vars = {
    RAPIDLY_GOOGLE_CLIENT_ID     = { value = var.google_secrets.client_id }
    RAPIDLY_GOOGLE_CLIENT_SECRET = { value = var.google_secrets.client_secret }
  }
}

resource "render_env_group" "openai" {
  environment_id = var.render_environment_id
  name           = "openai-${var.environment}"
  env_vars = {
    RAPIDLY_OPENAI_API_KEY = { value = var.openai_secrets.api_key }
  }
}

resource "render_env_group" "backend" {
  environment_id = var.render_environment_id
  name           = "backend-${var.environment}"
  env_vars = merge(
    {
      RAPIDLY_USER_SESSION_COOKIE_DOMAIN = { value = var.backend_config.user_session_cookie_domain }
      RAPIDLY_BASE_URL                   = { value = var.backend_config.base_url }
      RAPIDLY_DEBUG                      = { value = var.backend_config.debug }
      RAPIDLY_EMAIL_SENDER               = { value = var.backend_config.email_sender }
      RAPIDLY_EMAIL_FROM_NAME            = { value = var.backend_config.email_from_name }
      RAPIDLY_EMAIL_FROM_DOMAIN          = { value = var.backend_config.email_from_domain }
      RAPIDLY_ENV                        = { value = local.environment }
      RAPIDLY_FRONTEND_BASE_URL          = { value = var.backend_config.frontend_base_url }
      RAPIDLY_JWKS                       = { value = var.backend_config.jwks_path }
      RAPIDLY_LOG_LEVEL                  = { value = var.backend_config.log_level }
      RAPIDLY_TESTING                    = { value = var.backend_config.testing }
      RAPIDLY_STRIPE_PUBLISHABLE_KEY     = { value = var.backend_secrets.stripe_publishable_key }
      RAPIDLY_CURRENT_JWK_KID            = { value = var.backend_secrets.current_jwk_kid }
      RAPIDLY_DISCORD_BOT_TOKEN          = { value = var.backend_secrets.discord_bot_token }
      RAPIDLY_DISCORD_CLIENT_ID          = { value = var.backend_secrets.discord_client_id }
      RAPIDLY_DISCORD_CLIENT_SECRET      = { value = var.backend_secrets.discord_client_secret }
      RAPIDLY_DISCORD_PROXY_URL          = { value = var.backend_secrets.discord_proxy_url }
      RAPIDLY_RESEND_API_KEY             = { value = var.backend_secrets.resend_api_key }
      RAPIDLY_LOGO_DEV_PUBLISHABLE_KEY   = { value = var.backend_secrets.logo_dev_publishable_key }
      RAPIDLY_SECRET                     = { value = var.backend_secrets.secret }
      RAPIDLY_SENTRY_DSN                 = { value = var.backend_secrets.sentry_dsn }
    },
    var.backend_config.user_session_cookie_key != "" ? {
      RAPIDLY_USER_SESSION_COOKIE_KEY = { value = var.backend_config.user_session_cookie_key }
    } : {},
  )

  secret_files = {
    "jwks.json" = {
      content = var.backend_secrets.jwks
    }
  }
}

resource "render_env_group" "backend_production" {
  count          = var.environment == "production" ? 1 : 0
  environment_id = var.render_environment_id
  name           = "backend-production-only"
  env_vars = {
    RAPIDLY_ADMIN_HOST              = { value = var.backend_config.admin_host }
    RAPIDLY_POSTHOG_PROJECT_API_KEY = { value = var.backend_secrets.posthog_project_api_key }
    RAPIDLY_APP_REVIEW_EMAIL        = { value = var.backend_secrets.app_review_email }
    RAPIDLY_APP_REVIEW_OTP_CODE     = { value = var.backend_secrets.app_review_otp_code }
  }
}

resource "render_env_group" "aws_s3" {
  environment_id = var.render_environment_id
  name           = "aws-s3-${var.environment}"
  env_vars = {
    RAPIDLY_AWS_REGION                  = { value = var.aws_s3_config.region }
    RAPIDLY_AWS_SIGNATURE_VERSION       = { value = var.aws_s3_config.signature_version }
    RAPIDLY_S3_FILES_BUCKET_NAME        = { value = "rapidly-${var.environment}-files" }
    RAPIDLY_S3_FILES_PRESIGN_TTL        = { value = var.aws_s3_config.files_presign_ttl }
    RAPIDLY_S3_FILES_PUBLIC_BUCKET_NAME = { value = var.aws_s3_config.files_public_bucket_name }
    RAPIDLY_AWS_ACCESS_KEY_ID           = { value = var.aws_s3_secrets.access_key_id }
    RAPIDLY_AWS_SECRET_ACCESS_KEY       = { value = var.aws_s3_secrets.secret_access_key }
  }
}

resource "render_env_group" "github" {
  environment_id = var.render_environment_id
  name           = "github-${var.environment}"
  env_vars = {
    RAPIDLY_GITHUB_CLIENT_ID     = { value = var.github_secrets.client_id }
    RAPIDLY_GITHUB_CLIENT_SECRET = { value = var.github_secrets.client_secret }
  }
}

resource "render_env_group" "stripe" {
  environment_id = var.render_environment_id
  name           = "stripe-${var.environment}"
  env_vars = {
    RAPIDLY_STRIPE_CONNECT_WEBHOOK_SECRET = { value = var.stripe_secrets.connect_webhook_secret }
    RAPIDLY_STRIPE_SECRET_KEY             = { value = var.stripe_secrets.secret_key }
    RAPIDLY_STRIPE_WEBHOOK_SECRET         = { value = var.stripe_secrets.webhook_secret }
  }
}

resource "render_env_group" "logfire" {
  count          = var.logfire_config != null ? 1 : 0
  environment_id = var.render_environment_id
  name           = "logfire-${var.environment}"
  env_vars = {
    RAPIDLY_LOGFIRE_TOKEN = { value = var.logfire_config.token }
  }
}


resource "render_env_group" "apple" {
  environment_id = var.render_environment_id
  name           = "apple-${var.environment}"
  env_vars = {
    RAPIDLY_APPLE_CLIENT_ID = { value = var.apple_secrets.client_id }
    RAPIDLY_APPLE_TEAM_ID   = { value = var.apple_secrets.team_id }
    RAPIDLY_APPLE_KEY_ID    = { value = var.apple_secrets.key_id }
    RAPIDLY_APPLE_KEY_VALUE = { value = var.apple_secrets.key_value }
  }
}

resource "render_env_group" "prometheus" {
  count          = var.prometheus_config != null ? 1 : 0
  environment_id = var.render_environment_id
  name           = "prometheus-${var.environment}"
  env_vars = {
    RAPIDLY_PROMETHEUS_REMOTE_WRITE_URL      = { value = "${var.prometheus_config.url}/api/prom/push" }
    RAPIDLY_PROMETHEUS_REMOTE_WRITE_USERNAME  = { value = var.prometheus_config.username }
    RAPIDLY_PROMETHEUS_REMOTE_WRITE_PASSWORD  = { value = var.prometheus_config.password }
    RAPIDLY_PROMETHEUS_REMOTE_WRITE_INTERVAL  = { value = var.prometheus_config.interval }
  }
}

resource "render_env_group" "tinybird" {
  count          = var.tinybird_config != null ? 1 : 0
  environment_id = var.render_environment_id
  name           = "tinybird-${var.environment}"
  env_vars = {
    RAPIDLY_TINYBIRD_API_URL             = { value = var.tinybird_config.api_url }
    RAPIDLY_TINYBIRD_CLICKHOUSE_URL      = { value = var.tinybird_config.clickhouse_url }
    RAPIDLY_TINYBIRD_API_TOKEN           = { value = var.tinybird_config.api_token }
    RAPIDLY_TINYBIRD_CLICKHOUSE_USERNAME = { value = var.tinybird_config.clickhouse_username }
    RAPIDLY_TINYBIRD_CLICKHOUSE_TOKEN    = { value = var.tinybird_config.clickhouse_token }
    RAPIDLY_TINYBIRD_WORKSPACE           = { value = var.tinybird_config.workspace }
    RAPIDLY_TINYBIRD_EVENTS_WRITE        = { value = var.tinybird_config.events_write }
    RAPIDLY_TINYBIRD_EVENTS_READ         = { value = var.tinybird_config.events_read }
  }
}

# Services


resource "render_web_service" "api" {
  environment_id     = var.render_environment_id
  name               = "api${local.env_suffix}"
  plan               = var.api_service_config.plan
  region             = "ohio"
  health_check_path  = "/healthz"
  pre_deploy_command = "uv run task pre_deploy"

  runtime_source = {
    image = {
      image_url              = split("@", var.api_service_config.image_url)[0]
      registry_credential_id = var.registry_credential_id
      digest                 = var.api_service_config.image_digest
    }
  }

  autoscaling = var.environment == "production" ? {
    enabled = true
    min     = 1
    max     = 2
    criteria = {
      cpu = {
        enabled    = true
        percentage = 90
      }
      memory = {
        enabled    = true
        percentage = 90
      }
    }
  } : null

  custom_domains = var.api_service_config.custom_domains

  env_vars = {
    SERVICE_NAME                 = { value = "api${local.env_suffix}" }
    WEB_CONCURRENCY              = { value = var.api_service_config.web_concurrency }
    FORWARDED_ALLOW_IPS          = { value = var.api_service_config.forwarded_allow_ips }
    RAPIDLY_ALLOWED_HOSTS          = { value = var.api_service_config.allowed_hosts }
    RAPIDLY_CORS_ORIGINS           = { value = var.api_service_config.cors_origins }
    RAPIDLY_DATABASE_POOL_SIZE     = { value = var.api_service_config.database_pool_size }
    RAPIDLY_POSTGRES_DATABASE      = { value = var.api_service_config.postgres_database }
    RAPIDLY_POSTGRES_HOST          = { value = var.postgres_config.host }
    RAPIDLY_POSTGRES_PORT          = { value = var.postgres_config.port }
    RAPIDLY_POSTGRES_USER          = { value = var.postgres_config.user }
    RAPIDLY_POSTGRES_PWD           = { value = var.postgres_config.password }
    RAPIDLY_POSTGRES_READ_DATABASE = { value = var.api_service_config.postgres_read_database }
    RAPIDLY_POSTGRES_READ_HOST     = { value = var.postgres_config.read_host }
    RAPIDLY_POSTGRES_READ_PORT     = { value = var.postgres_config.read_port }
    RAPIDLY_POSTGRES_READ_USER     = { value = var.postgres_config.read_user }
    RAPIDLY_POSTGRES_READ_PWD      = { value = var.postgres_config.read_password }
    RAPIDLY_REDIS_HOST             = { value = var.redis_config.host }
    RAPIDLY_REDIS_PORT             = { value = var.redis_config.port }
    RAPIDLY_REDIS_DB               = { value = var.api_service_config.redis_db }
  }
}

resource "render_web_service" "worker" {
  for_each = var.workers

  environment_id    = var.render_environment_id
  name              = each.key
  plan              = each.value.plan
  region            = "ohio"
  health_check_path = "/"
  start_command     = each.value.start_command
  num_instances     = each.value.num_instances

  runtime_source = {
    image = {
      image_url              = split("@", each.value.image_url)[0]
      registry_credential_id = var.registry_credential_id
      digest                 = each.value.image_digest
    }
  }

  custom_domains = length(each.value.custom_domains) > 0 ? each.value.custom_domains : null

  env_vars = {
    SERVICE_NAME                 = { value = each.key }
    dramatiq_prom_port           = { value = each.value.dramatiq_prom_port }
    RAPIDLY_DATABASE_POOL_SIZE     = { value = each.value.database_pool_size }
    RAPIDLY_POSTGRES_DATABASE      = { value = var.api_service_config.postgres_database }
    RAPIDLY_POSTGRES_HOST          = { value = var.postgres_config.host }
    RAPIDLY_POSTGRES_PORT          = { value = var.postgres_config.port }
    RAPIDLY_POSTGRES_USER          = { value = var.postgres_config.user }
    RAPIDLY_POSTGRES_PWD           = { value = var.postgres_config.password }
    RAPIDLY_POSTGRES_READ_DATABASE = { value = var.api_service_config.postgres_read_database }
    RAPIDLY_POSTGRES_READ_HOST     = { value = var.postgres_config.read_host }
    RAPIDLY_POSTGRES_READ_PORT     = { value = var.postgres_config.read_port }
    RAPIDLY_POSTGRES_READ_USER     = { value = var.postgres_config.read_user }
    RAPIDLY_POSTGRES_READ_PWD      = { value = var.postgres_config.read_password }
    RAPIDLY_REDIS_HOST             = { value = var.redis_config.host }
    RAPIDLY_REDIS_PORT             = { value = var.redis_config.port }
    RAPIDLY_REDIS_DB               = { value = var.api_service_config.redis_db }
  }
}

locals {
  env_suffix      = var.environment == "production" ? "" : "-${var.environment}"
  worker_ids      = [for w in render_web_service.worker : w.id]
  all_service_ids = concat([render_web_service.api.id], local.worker_ids)
}

# Env group links
resource "render_env_group_link" "aws_s3" {
  env_group_id = render_env_group.aws_s3.id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "google" {
  env_group_id = render_env_group.google.id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "github" {
  env_group_id = render_env_group.github.id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "backend" {
  env_group_id = render_env_group.backend.id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "backend_production" {
  count        = var.environment == "production" ? 1 : 0
  env_group_id = render_env_group.backend_production[0].id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "stripe" {
  env_group_id = render_env_group.stripe.id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "logfire" {
  count        = var.logfire_config != null ? 1 : 0
  env_group_id = render_env_group.logfire[0].id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "openai" {
  env_group_id = render_env_group.openai.id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "apple" {
  env_group_id = render_env_group.apple.id
  service_ids  = [render_web_service.api.id]
}

resource "render_env_group_link" "prometheus" {
  count        = var.prometheus_config != null ? 1 : 0
  env_group_id = render_env_group.prometheus[0].id
  service_ids  = local.all_service_ids
}

resource "render_env_group_link" "tinybird" {
  count        = var.tinybird_config != null ? 1 : 0
  env_group_id = render_env_group.tinybird[0].id
  service_ids  = local.all_service_ids
}
