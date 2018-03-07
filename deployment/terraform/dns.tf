#
# Public DNS resources
#

resource "aws_route53_zone" "external" {
  name = "${var.route53_public_zone_name}"
}

resource "aws_route53_record" "bastion" {
  zone_id = "${aws_route53_zone.external.zone_id}"
  name    = "bastion.${var.route53_public_zone_name}"
  type    = "CNAME"
  ttl     = "300"

  records = ["${module.vpc.bastion_hostname}"]
}

resource "aws_route53_record" "app_server_alb" {
  zone_id = "${aws_route53_zone.external.zone_id}"
  name    = "app.${var.route53_public_zone_name}"
  type    = "A"

  alias {
    name                   = "${lower(aws_alb.app_server.dns_name)}"
    zone_id                = "${aws_alb.app_server.zone_id}"
    evaluate_target_health = true
  }
}

resource "aws_route53_zone" "internal" {
  name   = "${var.route53_private_zone_name}"
  vpc_id = "${module.vpc.id}"
}

#
# Private DNS resources
#

resource "aws_route53_record" "app_server" {
  zone_id = "${aws_route53_zone.internal.zone_id}"
  name    = "app-server.${var.route53_private_zone_name}"
  type    = "A"
  ttl     = "10"

  records = ["${aws_instance.app_server.private_ip}"]
}

resource "aws_route53_record" "database" {
  zone_id = "${aws_route53_zone.internal.zone_id}"
  name    = "postgres.${var.route53_private_zone_name}"
  type    = "CNAME"
  ttl     = "10"

  records = ["${module.database.hostname}"]
}
