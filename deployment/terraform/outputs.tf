output "public_hosted_zone_nameservers" {
  value = "${aws_route53_zone.external.name_servers}"
}

output "app_server_alb_fqdn" {
  value = "${aws_route53_record.app_server_alb.fqdn}"
}

output "bastion_fqdn" {
  value = "${aws_route53_record.bastion.fqdn}"
}
