resource "aws_security_group" "app_server" {
  vpc_id = "${module.vpc.id}"

  name = "sgAppServer"

  tags {
    Environment = "${var.environment}"
    Project     = "${var.project}"
    State       = "${var.state_name}"
  }
}

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

resource "aws_instance" "app_server" {
  ami = "${data.aws_ami.ecs_ami.id}"

  instance_initiated_shutdown_behavior = "stop"
  instance_type                        = "${var.app_server_instance_type}"
  key_name                             = "${var.aws_key_name}"
  monitoring                           = true
  availability_zone                    = "${var.app_server_availability_zone}"
  subnet_id                            = "${module.vpc.private_subnet_ids[0]}"
  vpc_security_group_ids               = ["${aws_security_group.app_server.id}"]

  tags {
    Project     = "${var.project}"
    Environment = "${var.environment}"
    State       = "${var.state_name}"
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

      bastion_host        = "${module.vpc.bastion_hostname}"
      bastion_user        = "ubuntu"
      bastion_private_key = "${file(pathexpand("~/.ssh/district-builder.pem"))}"
    }
  }
}

resource "null_resource" "provision_app_server" {
  depends_on = [
    "data.template_file.ansible_variables",
    "aws_instance.app_server",
    "aws_security_group_rule.bastion_ssh_ingress",
  ]

  triggers {
    uuid = "${uuid()}"
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-cex"]
    command     = "aws ec2 wait instance-running --instance-ids=${aws_instance.app_server.id} --region=${var.aws_region}"
  }

  provisioner "file" {
    source      = "${path.root}/../user-data"
    destination = "/opt/district-builder/"

    connection {
      type        = "ssh"
      host        = "${aws_instance.app_server.private_ip}"
      user        = "ec2-user"
      private_key = "${file(pathexpand("~/.ssh/district-builder.pem"))}"

      bastion_host        = "${module.vpc.bastion_hostname}"
      bastion_user        = "ubuntu"
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

      bastion_host        = "${module.vpc.bastion_hostname}"
      bastion_user        = "ubuntu"
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

      bastion_host        = "${module.vpc.bastion_hostname}"
      bastion_user        = "ubuntu"
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

      bastion_host        = "${module.vpc.bastion_hostname}"
      bastion_user        = "ubuntu"
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

      bastion_host        = "${module.vpc.bastion_hostname}"
      bastion_user        = "ubuntu"
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

      bastion_host        = "${module.vpc.bastion_hostname}"
      bastion_user        = "ubuntu"
      bastion_private_key = "${file(pathexpand("~/.ssh/district-builder.pem"))}"
    }
  }
}

resource "aws_security_group" "app_server_alb" {
  vpc_id = "${module.vpc.id}"

  name = "sgALBAppServer"

  tags {
    Environment = "${var.environment}"
    Project     = "${var.project}"
    State       = "${var.state_name}"
  }
}

resource "aws_alb" "app_server" {
  name = "alb${var.environment}AppServer"

  security_groups = [
    "${aws_security_group.app_server_alb.id}",
  ]

  subnets = ["${module.vpc.public_subnet_ids}"]

  tags {
    Name        = "albAppServer"
    Project     = "${var.project}"
    Environment = "${var.environment}"
    State       = "${var.state_name}"
  }
}

resource "aws_alb_target_group" "app_server_http" {
  name = "tg${var.environment}HTTPAppServer"

  health_check {
    healthy_threshold   = "3"
    interval            = "60"
    matcher             = "200"
    protocol            = "HTTP"
    timeout             = "3"
    path                = "/"
    unhealthy_threshold = "2"
  }

  port     = "8080"
  protocol = "HTTP"
  vpc_id   = "${module.vpc.id}"

  tags {
    Name        = "tg${var.environment}HTTPAppServer"
    Project     = "${var.project}"
    Environment = "${var.environment}"
    State       = "${var.state_name}"
  }
}

resource "aws_alb_target_group_attachment" "app_server" {
  target_group_arn = "${aws_alb_target_group.app_server_http.arn}"
  target_id        = "${aws_instance.app_server.id}"
  port             = 8080
}

resource "aws_alb_listener" "api_server_http" {
  load_balancer_arn = "${aws_alb.app_server.id}"
  port              = "80"
  protocol          = "HTTP"

  default_action {
    target_group_arn = "${aws_alb_target_group.app_server_http.id}"
    type             = "forward"
  }
}

resource "aws_alb_listener" "api_server_https" {
  load_balancer_arn = "${aws_alb.app_server.id}"
  port              = "443"
  protocol          = "HTTPS"

  certificate_arn = "${var.ssl_certificate_arn}"

  default_action {
    target_group_arn = "${aws_alb_target_group.app_server_http.id}"
    type             = "forward"
  }
}
