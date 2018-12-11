#
# Private DNS resources
#

data "aws_route53_zone" "internal" {
  zone_id = "${data.terraform_remote_state.core.private_hosted_zone_id}"
}

resource "aws_route53_record" "origin_internal" {
  zone_id = "${data.aws_route53_zone.internal.zone_id}"
  name    = "${lower(var.state)}.${replace(data.aws_route53_zone.internal.name, "/.$/", "")}"
  type    = "CNAME"
  ttl     = "10"
  records = ["${aws_instance.app_server.private_dns}"]
}

#
# Public DNS resources
#
data "aws_route53_zone" "external" {
  zone_id = "${data.terraform_remote_state.core.public_hosted_zone_id}"
}

# This allows us to place the app at either the root domain or a subdomain

locals {
  application_domain = "${var.is_subdomain ? "${lower(var.state)}.${replace(data.aws_route53_zone.external.name, "/.$/", "")}" : replace(data.aws_route53_zone.external.name, "/.$/", "")}"
}

resource "aws_route53_record" "origin" {
  zone_id = "${data.aws_route53_zone.external.zone_id}"
  name    = "origin.${local.application_domain}"
  type    = "CNAME"
  ttl     = "300"
  records = ["${aws_instance.app_server.public_dns}"]
}

resource "aws_route53_record" "app" {
  zone_id = "${data.aws_route53_zone.external.zone_id}"
  name    = "${local.application_domain}"
  type    = "A"

  alias {
    name                   = "${aws_cloudfront_distribution.cdn.domain_name}"
    zone_id                = "${aws_cloudfront_distribution.cdn.hosted_zone_id}"
    evaluate_target_health = false
  }
}
