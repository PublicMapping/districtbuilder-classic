resource "aws_db_subnet_group" "default" {
  name        = "${var.rds_database_identifier}"
  description = "Private subnets for the RDS instances"
  subnet_ids  = ["${module.vpc.private_subnet_ids}"]

  tags {
    Name        = "dbsngDatabaseServer"
    Project     = "${var.project}"
    Environment = "${var.environment}"
    State       = "${var.state_name}"
  }
}

resource "aws_db_parameter_group" "default" {
  name        = "${var.rds_database_identifier}"
  description = "Parameter group for the RDS instances"
  family      = "${var.rds_parameter_group_family}"

  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name         = "log_lock_waits"
    value        = "1"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "log_temp_files"
    value        = "500"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "log_autovacuum_min_duration"
    value        = "250"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "track_activity_query_size"
    value        = "2048"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "pg_stat_statements.track"
    value        = "ALL"
    apply_method = "pending-reboot"
  }

  tags {
    Name        = "dbpgDatabaseServer"
    Project     = "${var.project}"
    Environment = "${var.environment}"
    State       = "${var.state_name}"
  }
}

module "database" {
  source                     = "github.com/azavea/terraform-aws-postgresql-rds?ref=2.1.0"
  vpc_id                     = "${module.vpc.id}"
  allocated_storage          = "${var.rds_allocated_storage}"
  engine_version             = "${var.rds_engine_version}"
  instance_type              = "${var.rds_instance_type}"
  storage_type               = "${var.rds_storage_type}"
  database_identifier        = "${var.rds_database_identifier}"
  database_name              = "${var.rds_database_name}"
  database_username          = "${var.rds_database_username}"
  database_password          = "${var.rds_database_password}"
  backup_retention_period    = "${var.rds_backup_retention_period}"
  backup_window              = "${var.rds_backup_window}"
  maintenance_window         = "${var.rds_maintenance_window}"
  auto_minor_version_upgrade = "${var.rds_auto_minor_version_upgrade}"
  final_snapshot_identifier  = "${format("rds-final-snapshot-%s-%s", replace(lower(var.project), " ", "-"), var.environment)}"
  skip_final_snapshot        = "${var.rds_skip_final_snapshot}"
  copy_tags_to_snapshot      = "${var.rds_copy_tags_to_snapshot}"
  multi_availability_zone    = "${var.rds_multi_az}"
  storage_encrypted          = "${var.rds_storage_encrypted}"
  subnet_group               = "${aws_db_subnet_group.default.name}"
  parameter_group            = "${aws_db_parameter_group.default.name}"

  alarm_cpu_threshold         = "75"
  alarm_disk_queue_threshold  = "10"
  alarm_free_disk_threshold   = "5000000000"
  alarm_free_memory_threshold = "128000000"
  alarm_actions               = ["${aws_sns_topic.global.arn}"]

  project     = "${var.project}"
  environment = "${var.environment}"
}
