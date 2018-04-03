data "terraform_remote_state" "core" {
  backend = "s3"

  config {
    region = "${var.aws_region}"
    bucket = "districtbuilder-${lower(var.environment)}-config-${var.aws_region}"
    key    = "terraform/core/state"
  }
}
