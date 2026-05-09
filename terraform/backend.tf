# Rapidly infrastructure — remote state on Cloudflare R2.
#
# Bucket name and endpoint are passed via -backend-config at init time
# (from GitHub Actions secrets), so nothing sensitive is hardcoded here.

terraform {
  backend "s3" {
    key    = "terraform-state/production.tfstate"
    region = "us-east-1"

    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}
