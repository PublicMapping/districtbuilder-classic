# This README deals with an internal AWS deployment process. For more general instructions, see `Deployment` in the project [README](../README.markdown)

# Amazon Web Services Deployment

Amazon Web Services deployment is driven by [Terraform](https://terraform.io/), [Ansible](https://www.ansible.com/), and the [AWS Command Line Interface (CLI)](http://aws.amazon.com/cli/).

**The commands in this section should be run from within the VM.**

## Table of Contents

* [Deployment](#deployment)
    * [Pre-Deployment Configuration](#pre-deployment-configuration)
    * [SSH Keys](#ssh-keys)
    * [DB_SETTINGS_BUCKET](#db_settings_bucket)
    * [User Data](#user-data)
    * [`scripts/infra`](#scriptsinfra)
    * [Loading Shapefile data](#loading-shapefile-data)

## Deployment

### Pre Deployment Configuration

#### SSH Keys

You'll need to generate an SSH Keypair using the AWS EC2 console. Download the private key, and store it at `~/.ssh/district-builder.pem`.

#### `DB_SETTINGS_BUCKET`

Before running `scripts/infra`, create an AWS S3 bucket to house the terraform remote state and configuration file. Make note of the bucket name, it will be the value of the `DB_SETTINGS_BUCKET` environment variable later on.

You'll also need to create a `terraform.tfvars` file, which contains the configuration parameters for your infrastructure and application. You can see the available configuration options in [`sample.tfvars`](./terraform/sample.tfvars). Modify this file to suit your needs, and store it on S3 at `s3://${DB_SETTINGS_BUCKET}/terraform/terraform.tfvars`. Note that Application server configuration such as admin usernames and passwords are prefixed with `districtbuilder_` (i.e. `districtbuilder_admin_user`).

#### User Data

You will also upload your own DistrictBuilder `config.xml` and shapefile zip to the App Server as a part of provisioning. Simply add a DistrictBuilder `config.xml` file and `districtbuilder_data.zip` in the [`user-data`](./user-data/) folder, and the provisioner will upload them to the server for you. 

#### `scripts/infra`
Once the settings bucket and User Data are configured, you can run the deployment. To deploy the DistrictBuilder core services (VPC, EC2, RDS, etc.) resources, use the `infra` wrapper script to lookup the remote state of the infrastructure and assemble a plan for work to be done. You can run `scripts/infra` inside of the `terraform` Docker container defined in `docker-compose.ci.yml`, which contains all of the necessary software dependencies for deployments.

First, obtain your account's AWS API keypair, and add them to your environment. Then, set `DB_SETTINGS_BUCKET` and `IMAGE_VERSION`, and run `scripts/infra`:


```bash
$ export AWS_ACCESS_KEY_ID="****************F2DQ"
$ export AWS_ACCESS_KEY_ID="****************TLJ/"
$ export DB_SETTINGS_BUCKET="districtbuilder-staging-config-us-east-1"
# IMAGE_VERSION can be a git SHA, or version tag
$ export IMAGE_VERSION=123456"
$ docker-compose -f docker-compose.ci.yml run --rm terraform ./scripts/infra plan
```

Once the plan has been assembled, and you agree with the changes, apply it:

```bash
$ docker-compose -f docker-compose.ci.yml run --rm terraform ./scripts/infra apply
```

This will attempt to apply the infrastructure plan assembled in the previous step using Amazon's APIs, run Ansible to configure the App Server with User Data, and run migrations. In order to change specific attributes of the infrastructure, inspect the contents of the environment's configuration file in Amazon S3.

#### Loading Shapefile data
To load data, ssh into the App Server through the bastion, and run `/opt/district-builder/scripts/load_configured_data`.

```bash
# start ssh-agent, and add your ssh private key
$ eval $(ssh-agent)
$ ssh-add ~/.ssh/district-builder.pem

# SSH into the bastion host
$ ssh -A ubuntu@bastion.example.com

# SSh into the app-server from the bastion
ubuntu@bastion.example.com $ ssh ec2-user@app-server.internal.example.com

# Run scripts
$ ec2-user@app-server $ cd /opt/district-builder
$ ec2-user@app-server:/opt/district-builder $ ./scripts/load_configured_data
```

#### Administering Geoserver
To administer Geoserver in staging, you may experience a port re-routing issue. For example, after logging in to

https://va.districtbuilder.azavea.com/geoserver/web/

you will be perpetually re-routed to port 8080 and will have to remove the port from the URL to load the next page.

As a workaround, you can instead access

http://origin.va.districtbuilder.azavea.com:8080/geoserver

This is the origin for CloudFront and does not have the re-routing issue.
