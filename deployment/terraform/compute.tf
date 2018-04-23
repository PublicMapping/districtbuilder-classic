#
# EC2 resources
#
data "aws_ami" "ecs_ami" {
  most_recent = true

  filter {
    name   = "name"
    values = ["amzn-ami-*-amazon-ecs-optimized"]
  }

  filter {
    name   = "owner-alias"
    values = ["amazon"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "template_file" "user_data" {
  template = "${file("templates/cloud-config.tpl")}"

  vars {
    zip_file_uri = "districtbuilder-${lower(var.environment)}-config-${var.aws_region}/docker_certs/server/${lower(var.state)}.zip"
  }
}

resource "aws_instance" "app_server" {
  ami = "${data.aws_ami.ecs_ami.id}"

  iam_instance_profile                 = "${data.terraform_remote_state.core.app_server_instance_profile}"
  instance_initiated_shutdown_behavior = "stop"
  instance_type                        = "${var.app_server_instance_type}"
  key_name                             = "${data.terraform_remote_state.core.app_server_key_name}"
  monitoring                           = true
  subnet_id                            = "${data.terraform_remote_state.core.public_subnet_ids[0]}"
  vpc_security_group_ids               = ["${data.terraform_remote_state.core.app_server_security_group_ids}"]
  user_data                            = "${data.template_file.user_data.rendered}"

  tags {
    Name        = "AppServer"
    Project     = "${var.project}"
    Environment = "${var.environment}"
  }
}

resource "null_resource" "provision_app_server" {
  triggers {
    uuid = "${uuid()}"
  }

  provisioner "file" {
    source      = "${path.root}/../user-data"
    destination = "/home/ec2-user/"

    connection {
      type        = "ssh"
      host        = "${aws_instance.app_server.private_ip}"
      user        = "ec2-user"
      private_key = "${file(pathexpand("~/.ssh/district-builder.pem"))}"

      bastion_host        = "${data.terraform_remote_state.core.bastion_hostname}"
      bastion_user        = "ec2-user"
      bastion_private_key = "${file(pathexpand("~/.ssh/district-builder.pem"))}"
    }
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mkdir -p /opt/district-builder/user-data",
      "sudo mv /home/ec2-user/user-data /opt/district-builder",
      "sudo chown -R ec2-user:ec2-user /opt/district-builder/",
      "touch /opt/district-builder/user-data/config_settings.py",
    ]

    connection {
      type        = "ssh"
      host        = "${aws_instance.app_server.private_ip}"
      user        = "ec2-user"
      private_key = "${file(pathexpand("~/.ssh/district-builder.pem"))}"

      bastion_host        = "${data.terraform_remote_state.core.bastion_hostname}"
      bastion_user        = "ec2-user"
      bastion_private_key = "${file(pathexpand("~/.ssh/district-builder.pem"))}"
    }
  }

  depends_on = [
    "aws_instance.app_server",
  ]
}
