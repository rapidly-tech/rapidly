terraform {
  cloud {
    organization = "rapidly-tech"
    workspaces {
      name = "rapidly"
    }
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.92"
    }

    render = {
      source  = "render-oss/render"
      version = "1.8.0"
    }

    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.13"
    }
  }

  required_version = ">= 1.2"
}
