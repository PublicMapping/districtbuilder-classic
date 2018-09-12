# This README deals with an internal AWS deployment process. For more general instructions, see `Deployment` in the project [README](../README.markdown)

# Amazon Web Services Deployment

Amazon Web Services deployment is driven by [Terraform](https://terraform.io/), [Docker](https://www.docker.com/), and the [AWS Command Line Interface (CLI)](http://aws.amazon.com/cli/).

**The commands in this section should be run from within the VM.**

## Table of Contents

* [Deployment](#deployment)
    * [Pre-Deployment Configuration](#pre-deployment-configuration)
    * [SSH Keys](#ssh-keys)
    * [DB_SETTINGS_BUCKET](#db_settings_bucket)
    * [User Data](#user-data)
    * [`scripts/infra`](#scriptsinfra)
    * [Loading Shapefile data](#loading-shapefile-data)
    * [Fixing Staging](#fixing-staging)

## Deployment

### Pre Deployment Configuration

#### SSH Keys

You'll need to download the `district-builder-pa` SSH Keypair from the fileshare, and store it at `~/.ssh/district-builder-pa.pem`.

#### `DB_SETTINGS_BUCKET`

`DB_SETTINGS_BUCKET` stores Terraform remote state, the `.tfvars` file (which contains the configuration parameters for your infrastructure) and a `.env` file used by `docker-compose` to set environment variables in app containers. To view or change any of these files, check on S3 at `s3://${DB_SETTINGS_BUCKET}/terraform/${DB_STATE}/`, where `DB_STATE` is a lowercase, 2-letter abbreviation for the state associated with your DistrictBuilder instance (i.e. `pa`, `va`).

#### User Data

You will upload your own DistrictBuilder `config.xml` and shapefile zip to the App Server as a part of provisioning. Simply add a DistrictBuilder `config.xml` file and `districtbuilder_data.zip` in the [`user-data`](./user-data/) folder, and the provisioner will upload them to the server for you. 

#### `scripts/infra`
Once the settings bucket and User Data are configured, you can run the deployment. To deploy the infrastructure for a DistrictBuilder instance (EC2, Route53 records, etc.) resources, use the `infra` wrapper script to lookup the remote state of the infrastructure and assemble a plan for work to be done. You can run `scripts/infra` inside of the `terraform` Docker container defined in `docker-compose.ci.yml`, which contains all of the necessary software dependencies for deployments.

First, obtain your account's AWS API keypair, and configure your `district-builder-pa` AWS profile. Then, set `DB_SETTINGS_BUCKET` and `IMAGE_VERSION`, and run `scripts/infra`:


```bash
$ aws --profile district-builder-pa configure
AWS Access Key ID [None]: ****************BWCA 
AWS Secret Access Key [None]: ****************hlS4 
Default region name [None]: us-east-1 
Default output format [None]:
$ export AWS_PROFILE=district-builder-pa
$ export DB_SETTINGS_BUCKET="district-builder-dtl-staging-config-us-east-1"
# IMAGE_VERSION can be a git SHA, or version tag
$ export IMAGE_VERSION=123456"
$ docker-compose -f docker-compose.ci.yml -f docker-compose.ci.override.yml run --rm terraform ./scripts/infra plan
```

Once the plan has been assembled, and you agree with the changes, apply it:

```bash
$ docker-compose -f docker-compose.ci.yml -f docker-compose.ci.override.yml run --rm terraform ./scripts/infra apply
```

This will attempt to apply the infrastructure plan assembled in the previous step using Amazon's APIs and use `docker-compose` to configure the App Server with User Data, build container images, start services and run migrations. In order to change specific attributes of the infrastructure, inspect the contents of the environment's `tfvars` file in Amazon S3. To modify application variables, change `.env`.

#### Loading Shapefile data
To load data, configure the deployment machine to communicate with the Docker Daemon on the App server, then run `./scripts/load_configured_data --production`.

```bash
# Download docker client certificates from S3 and install them
$ aws --profile district-builder s3 cp s3://${DB_SETTINGS_BUCKET}/docker_certs/client/client.zip

# Download .env file from S3
$ aws --profile district-builder s3 cp s3://${DB_SETTINGS_BUCKET}/terraform/${DB_STATE}/.env .

$ unzip -d /path/to/docker/certs client.zip
# Enable Docker over TLS

$ export DOCKER_HOST=origin.${DB_STATE}.districtbuilder.azavea.com:2476
$ export DOCKER_TLS_VERIFY=1
$ export DOCKER_CERT_PATH=/path/to/docker/certs
# Set application version
$ export GIT_COMMIT=1234567
$ ./scripts/load_configured_data --production
```

### Fixing Staging
Depending on the configuration changes, staging will sometimes get into a bad state after deployment as we do not handle all types of config changes perfectly. As a result, you may need to "wipe the slate clean" in staging to see your changes. You can do this by ssh-ing into the staging app server, downloading the appropriate script, and running it, like so (**NOTE: the database will be dropped and recreated!**):

```bash
$ ssh-add ~/.ssh/district-builder-pa.pem
...
$ ssh -A ec2-user@bastion.staging.pa.districtbuilder.azavea.com
...
$ ssh ec2-user@pa.districtbuilder.internal
...
$ docker exec -ti districtbuilder-django bash
...
# Remove existing copy of script (if it exists)
$ rm recreate_staging_from_scratch
# Download latest copy of script
$ wget https://raw.githubusercontent.com/azavea/district-builder-dtl-pa/develop/scripts/recreate_staging_from_scratch
# Run script
$ bash recreate_staging_from_scratch
# Remove script
$ rm recreate_staging_from_scratch
```

#### Fixing Pink Tiles

Make sure the `pmp` workspace exists:

1. Log into Geoserver (`http://origin.<domain>:8080/geoserver`). The admin username is `admin` and the password is available as an environment variable (`$MAP_SERVER_ADMIN_PASSWORD`) on the app server within the `districtbuilder-django` container (`docker exec -ti districtbuilder-django bash` and then `echo $MAP_SERVER_ADMIN_PASSWORD`).
1. Create new `pmp` workspace if it doesn't exit (Name = `pmp`, Namespace URI = `https://github.com/PublicMapping/`)
1. Reconfigure geoserver (`./manage.py setup config/config.xml -G` within the `districtbuilder-django` container)

#### Duplicate Records

Reporting being broken and the leaderboard saying "No display configured" is caused by duplicate records in the database. The easiest fix is to drop and recreate the database.
