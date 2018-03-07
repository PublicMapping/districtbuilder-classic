data "aws_ami" "ubuntu_ami" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm/ubuntu-trusty-14.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  owners = ["099720109477"]
}

#
# VPC Resources
#
module "vpc" {
  source = "github.com/azavea/terraform-aws-vpc?ref=4.0.0"

  name                       = "${format("vpc%s%s",replace(var.project, " ",""), var.environment)}"
  region                     = "${var.aws_region}"
  key_name                   = "${var.aws_key_name}"
  cidr_block                 = "${var.vpc_cidr_block}"
  external_access_cidr_block = "${var.external_access_cidr_block}"
  private_subnet_cidr_blocks = "${var.vpc_private_subnet_cidr_blocks}"
  public_subnet_cidr_blocks  = "${var.vpc_public_subnet_cidr_blocks}"
  availability_zones         = "${var.aws_availability_zones}"
  bastion_ami                = "${data.aws_ami.ubuntu_ami.id}"
  bastion_instance_type      = "${var.bastion_instance_type}"
  project                    = "${var.project}"
  environment                = "${var.environment}"
}
