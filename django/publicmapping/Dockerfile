FROM quay.io/azavea/django:1.11-python2.7-slim

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN apt-get update && apt-get install -y \
    git gcc wget unzip
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

WORKDIR /usr/src/app

RUN cp config/config.dist.xml config/config.xml

ENTRYPOINT ["/usr/local/bin/gunicorn"]
