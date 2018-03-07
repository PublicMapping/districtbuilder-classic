variable "project" {
  default = "District Builder"
}

variable "environment" {
  default = "Staging"
}

variable "state_name" {
  description = "Name of the state for this DistrictBuilder Deployment (e.g. PA, Ohio)"
}

variable "aws_region" {
  default = "us-east-1"
}

variable "aws_key_name" {}

variable "vpc_cidr_block" {}

variable "external_access_cidr_block" {}

variable "bastion_external_access_cidr_block" {
  type = "list"
}

variable "vpc_private_subnet_cidr_blocks" {
  type = "list"
}

variable "vpc_public_subnet_cidr_blocks" {
  type = "list"
}

variable "aws_availability_zones" {
  type = "list"
}

variable "bastion_instance_type" {
  default = "t2.nano"
}

variable "rds_allocated_storage" {
  default = "128"
}

variable "rds_engine_version" {
  default = "9.5"
}

variable "rds_instance_type" {
  default = "db.t2.small"
}

variable "rds_storage_type" {
  default = "gp2"
}

variable "rds_database_identifier" {}
variable "rds_database_name" {}
variable "rds_database_username" {}
variable "rds_database_password" {}

variable "rds_parameter_group_family" {
  default = "postgres9.5"
}

variable "rds_backup_retention_period" {
  default = "30"
}

variable "rds_backup_window" {
  default = "04:00-04:30"
}

variable "rds_maintenance_window" {
  default = "sun:04:30-sun:05:30"
}

variable "rds_auto_minor_version_upgrade" {
  default = true
}

variable "rds_skip_final_snapshot" {
  default = false
}

variable "rds_copy_tags_to_snapshot" {
  default = true
}

variable "rds_multi_az" {
  default = false
}

variable "rds_storage_encrypted" {
  default = false
}

variable "app_server_instance_type" {
  default = "t2.small"
}

variable "app_server_availability_zone" {}

variable "route53_public_zone_name" {}

variable "route53_private_zone_name" {
  default = "districtbuilder.internal"
}

variable "ssl_certificate_arn" {}

variable "districtbuilder_web_app_password" {}
variable "districtbuilder_admin_user" {}
variable "districtbuilder_admin_email" {}
variable "districtbuilder_admin_password" {}
variable "districtbuilder_redis_password" {}
variable "districtbuilder_geoserver_password" {}
variable "districtbuilder_image_version" {}
variable "districtbuilder_mailer_host" {}
variable "districtbuilder_mailer_user" {}
variable "districtbuilder_mailer_password" {}
