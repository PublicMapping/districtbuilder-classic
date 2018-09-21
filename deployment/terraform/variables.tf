variable "project" {
  default = "District Builder"
}

variable "state" {}

variable "environment" {
  default = "Staging"
}

variable "aws_region" {
  default = "us-east-1"
}

variable "app_server_instance_type" {
  default = "t2.small"
}

variable "ssl_certificate_arn" {}

variable "cdn_price_class" {
  default = "PriceClass_100"
}

variable "remote_state_bucket_prefix" {
  default = "districtbuilder"
}

variable "is_subdomain" {}

variable "ssh_identity_file_path" {
  default = "~/.ssh/district-builder-pa.pem"
}

variable "cloudfront_aliases" {
  description = "List of CNAMES that will refer to this project"
  default     = []
}
