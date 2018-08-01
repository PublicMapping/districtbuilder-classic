data "terraform_remote_state" "core" {
  backend = "s3"

  config {
    region = "${var.aws_region}"
    bucket = "${var.remote_state_bucket_prefix}-${lower(var.environment)}-config-${var.aws_region}"
    key    = "terraform/core/state"
  }
}
