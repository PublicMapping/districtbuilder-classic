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

variable "is_subdomain" {}