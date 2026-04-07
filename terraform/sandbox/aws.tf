# =============================================================================
# Application Access (IAM user policies)
# =============================================================================

module "application_access_sandbox" {
  source   = "../modules/application_access"
  username = "rapidly-sandbox-files"
  buckets = {
    files        = { name = "rapidly-sandbox-files", description = "Policy used by our SANDBOX app for downloadable files. Keep permissions to a bare minimum." }
    public_files = { name = "rapidly-public-sandbox-files", description = "Policy used by our SANDBOX app for public uploads -products medias and such-. Keep permissions to a bare minimum." }
  }
}

# =============================================================================
# Image Resizer Lambda@Edge
# =============================================================================

data "aws_s3_bucket" "lambda_artifacts" {
  provider = aws.us_east_1
  bucket   = "rapidly-lambda-artifacts"
}

data "aws_s3_object" "image_resizer_package" {
  provider = aws.us_east_1
  bucket   = data.aws_s3_bucket.lambda_artifacts.id
  key      = "image-resizer/package.zip"
}

module "image_resizer" {
  source = "../modules/lambda_edge_resizer"
  providers = {
    aws = aws.us_east_1
  }

  function_name     = "rapidly-sandbox-image-resizer"
  s3_bucket         = data.aws_s3_bucket.lambda_artifacts.id
  s3_key            = data.aws_s3_object.image_resizer_package.key
  s3_object_version = data.aws_s3_object.image_resizer_package.version_id
  source_bucket_arn = module.s3_buckets.public_files_bucket_arn
}

# =============================================================================
# CloudFront Distribution (Sandbox Public Assets)
# =============================================================================

module "cloudfront_sandbox_assets" {
  source = "../modules/cloudfront_distribution"
  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  name                           = "rapidly-sandbox-public-files"
  domain                         = "sandbox-uploads.rapidly.tech"
  cloudflare_zone_id             = "22bcd1b07ec25452aab472486bc8df94"
  s3_bucket_id                   = module.s3_buckets.public_files_bucket_id
  s3_bucket_regional_domain_name = module.s3_buckets.public_files_bucket_regional_domain_name
  s3_bucket_arn                  = module.s3_buckets.public_files_bucket_arn
  cors_allowed_origins           = ["https://sandbox.rapidly.tech"]

  lambda_function_associations = [
    {
      event_type = "origin-request"
      lambda_arn = module.image_resizer.qualified_arn
    },
  ]
}

# =============================================================================
# CloudFront Distribution (Sandbox CDN)
# =============================================================================

module "cloudfront_sandbox_cdn" {
  source = "../modules/cloudfront_distribution"
  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  name                           = "rapidly-sandbox-cdn"
  domain                         = "sandbox-cdn.rapidly.tech"
  cloudflare_zone_id             = "22bcd1b07ec25452aab472486bc8df94"
  s3_bucket_id                   = module.s3_buckets.public_assets_bucket_id
  s3_bucket_regional_domain_name = module.s3_buckets.public_assets_bucket_regional_domain_name
  s3_bucket_arn                  = module.s3_buckets.public_assets_bucket_arn
  cors_allowed_origins           = ["https://sandbox.rapidly.tech"]
}
