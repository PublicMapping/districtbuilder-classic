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

variable "districtbuilder_database_name" {}

variable "districtbuilder_web_app_password" {}

variable "districtbuilder_admin_user" {}

variable "districtbuilder_admin_email" {}

variable "districtbuilder_admin_password" {}

variable "districtbuilder_redis_password" {}

variable "districtbuilder_geoserver_password" {}

variable "districtbuilder_mailer_host" {}

variable "districtbuilder_mailer_user" {}

variable "districtbuilder_mailer_password" {}
