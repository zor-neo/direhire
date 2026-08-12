provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "direhire"
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "direhire"
    }
  }
}

