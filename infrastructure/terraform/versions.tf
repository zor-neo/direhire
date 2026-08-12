terraform {
  backend "s3" {
    # Partial config — supply bucket, key, region via -backend-config at init.
    use_lockfile = true
  }

  required_version = ">= 1.10, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

