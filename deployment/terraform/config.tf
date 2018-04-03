provider "aws" {
  version = "~> 1.12.0"
  region  = "${var.aws_region}"
}

provider "template" {
  version = "~> 1.0.0"
}

provider "local" {
  version = "~> 1.1.0"
}

provider "null" {
  version = "~> 1.0.0"
}

terraform {
  backend "s3" {
    region  = "us-east-1"
    encrypt = "true"
  }
}
