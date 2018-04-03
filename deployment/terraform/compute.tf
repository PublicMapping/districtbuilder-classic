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

data "template_file" "ansible_variables" {
  template = "${file("templates/main.yml.tpl")}"

  vars {
    image_version      = "${var.districtbuilder_image_version}"
    web_app_password   = "${var.districtbuilder_web_app_password}"
    admin_user         = "${var.districtbuilder_admin_user}"
    admin_email        = "${var.districtbuilder_admin_email}"
    admin_password     = "${var.districtbuilder_admin_password}"
    database_name      = "${var.districtbuilder_database_name}"
    database_user      = "${data.terraform_remote_state.core.rds_username}"
    database_password  = "${data.terraform_remote_state.core.rds_password}"
    redis_password     = "${var.districtbuilder_redis_password}"
    geoserver_password = "${var.districtbuilder_geoserver_password}"
    mailer_host        = "${var.districtbuilder_mailer_host}"
    mailer_user        = "${var.districtbuilder_mailer_user}"
    mailer_password    = "${var.districtbuilder_mailer_password}"
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
  vpc_security_group_ids               = ["${data.terraform_remote_state.core.app_server_security_group_id}"]

  tags {
    Name        = "AppServer"
    Project     = "${var.project}"
    Environment = "${var.environment}"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo yum update -y",
      "sudo yum groupinstall -y 'Development Tools'",
      "sudo yum install -y libffi-devel",
      "curl 'https://bootstrap.pypa.io/get-pip.py' -o '/tmp/get-pip.py'",
      "sudo python /tmp/get-pip.py",
      "sudo /usr/local/bin/pip install ansible==2.4.*",
      "sudo mkdir -p /opt/district-builder/scripts",
      "sudo mkdir -p /opt/district-builder/deployment/ansible/roles",
      "sudo chown -R ec2-user:ec2-user /opt/district-builder",
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
}

resource "null_resource" "provision_app_server" {
  triggers {
    uuid = "${uuid()}"
  }

  provisioner "file" {
    source      = "${path.root}/../user-data"
    destination = "/opt/district-builder/"

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

  provisioner "file" {
    source      = "${path.root}/../scripts"
    destination = "/opt/district-builder"

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

  provisioner "file" {
    source      = "${path.root}/../ansible/roles/district-builder.app-server"
    destination = "/opt/district-builder/deployment/ansible/roles"

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

  provisioner "file" {
    source      = "${path.root}/../ansible/district-builder-app-server.yml"
    destination = "/opt/district-builder/deployment/ansible/district-builder-app-server.yml"

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

  provisioner "file" {
    content     = "${data.template_file.ansible_variables.rendered}"
    destination = "/opt/district-builder/deployment/ansible/roles/district-builder.app-server/defaults/main.yml"

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
      "cd /opt/district-builder",
      "ansible-galaxy install azavea.python-security -p deployment/ansible/roles",
      "ansible-playbook deployment/ansible/district-builder-app-server.yml",
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
    "data.template_file.ansible_variables",
    "aws_instance.app_server",
  ]
}
