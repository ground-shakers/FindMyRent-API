terraform {
  backend "s3" {
    bucket         = "findmyrent-terraform-state"
    key            = "findmyrent/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "findmyrent-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  required_version = ">= 1.6.0"
}

provider "aws" {
  region = var.aws_region
}