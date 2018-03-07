#
# VPC Security Group Resources
#

#
# Bastion Security Group Resources
#
resource "aws_security_group_rule" "bastion_ssh_ingress" {
  type              = "ingress"
  from_port         = "22"
  to_port           = "22"
  protocol          = "TCP"
  cidr_blocks       = "${concat(list(var.external_access_cidr_block), var.bastion_external_access_cidr_block)}"
  security_group_id = "${module.vpc.bastion_security_group_id}"
}

resource "aws_security_group_rule" "bastion_ssh_egress" {
  type              = "egress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = ["${module.vpc.cidr_block}"]
  security_group_id = "${module.vpc.bastion_security_group_id}"
}

resource "aws_security_group_rule" "bastion_http_egress" {
  type              = "egress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = "${module.vpc.bastion_security_group_id}"
}

resource "aws_security_group_rule" "bastion_https_egress" {
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = "${module.vpc.bastion_security_group_id}"
}

resource "aws_security_group_rule" "bastion_postgresql_egress" {
  type      = "egress"
  from_port = 5432
  to_port   = 5432
  protocol  = "tcp"

  security_group_id        = "${module.vpc.bastion_security_group_id}"
  source_security_group_id = "${module.database.database_security_group_id}"
}

#
# App Server Security Group Resources
#

resource "aws_security_group_rule" "app_server_bastion_ingress" {
  type      = "ingress"
  from_port = 22
  to_port   = 22
  protocol  = "tcp"

  security_group_id        = "${aws_security_group.app_server.id}"
  source_security_group_id = "${module.vpc.bastion_security_group_id}"
}

resource "aws_security_group_rule" "app_server_app_server_alb_http_ingress" {
  type      = "ingress"
  from_port = 8080
  to_port   = 8080
  protocol  = "tcp"

  security_group_id        = "${aws_security_group.app_server.id}"
  source_security_group_id = "${aws_security_group.app_server_alb.id}"
}

resource "aws_security_group_rule" "app_server_postgresql_egress" {
  type      = "egress"
  from_port = 5432
  to_port   = 5432
  protocol  = "tcp"

  security_group_id        = "${aws_security_group.app_server.id}"
  source_security_group_id = "${module.database.database_security_group_id}"
}

resource "aws_security_group_rule" "app_server_http_egress" {
  type        = "egress"
  from_port   = 80
  to_port     = 80
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]

  security_group_id = "${aws_security_group.app_server.id}"
}

resource "aws_security_group_rule" "app_server_https_egress" {
  type        = "egress"
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]

  security_group_id = "${aws_security_group.app_server.id}"
}

#
# Database Security Group Resources
#

resource "aws_security_group_rule" "postgresql_bastion_ingress" {
  type      = "ingress"
  from_port = 5432
  to_port   = 5432
  protocol  = "tcp"

  security_group_id        = "${module.database.database_security_group_id}"
  source_security_group_id = "${module.vpc.bastion_security_group_id}"
}

resource "aws_security_group_rule" "postgresql_app_server_ingress" {
  type      = "ingress"
  from_port = 5432
  to_port   = 5432
  protocol  = "tcp"

  security_group_id        = "${module.database.database_security_group_id}"
  source_security_group_id = "${aws_security_group.app_server.id}"
}

#
# App Server Loadbalancer Security Group Resources
#

resource "aws_security_group_rule" "app_server_alb_http_ingress" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["${var.external_access_cidr_block}"]
  security_group_id = "${aws_security_group.app_server_alb.id}"
}

resource "aws_security_group_rule" "app_server_alb_https_ingress" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["${var.external_access_cidr_block}"]
  security_group_id = "${aws_security_group.app_server_alb.id}"
}

resource "aws_security_group_rule" "app_server_alb_app_server_http_ingress" {
  type      = "egress"
  from_port = 8080
  to_port   = 8080
  protocol  = "tcp"

  security_group_id        = "${aws_security_group.app_server_alb.id}"
  source_security_group_id = "${aws_security_group.app_server.id}"
}
