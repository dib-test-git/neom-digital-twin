terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }

  backend "s3" {
    bucket         = "neom-tfstate-the-line"
    key            = "digital-twin/${terraform.workspace}.tfstate"
    region         = "me-central-1"
    dynamodb_table = "neom-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "the-line-digital-twin"
      Owner     = "neom-platform-data"
      ManagedBy = "terraform"
      Workspace = terraform.workspace
    }
  }
}

variable "region" {
  type    = string
  default = "me-central-1"
}

variable "azs" {
  type    = list(string)
  default = ["me-central-1a", "me-central-1b", "me-central-1c"]
}

locals {
  is_prod = startswith(terraform.workspace, "prod-")
}
