FROM quay.io/azavea/django:1.11-python2.7-slim

RUN mkdir -p /usr/src/app
RUN mkdir -p /opt/sld

RUN mkdir -p /opt/reports

# Create reporter user that can write to reports directory
# This user is used to run `celery worker` for reporting
# as it is not recommended to run Celery services as root.
RUN useradd -m reporter
RUN chown reporter: /opt/reports

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    git gcc wget unzip

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

RUN python -m district_builder_config.generate_settings \
  config/config.xsd \
  config/config.xml \
  publicmapping/config_settings.py

WORKDIR /usr/src/app
