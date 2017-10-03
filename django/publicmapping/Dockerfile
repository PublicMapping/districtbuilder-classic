FROM python:2.7

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN apt-key adv --keyserver ha.pool.sks-keyservers.net --recv-keys B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8

ENV PG_MAJOR 9.5
ENV PG_VERSION 9.4+165+deb8u2

RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ jessie-pgdg main' ${PG_MAJOR} > /etc/apt/sources.list.d/pgdg.list

RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        gettext \
        postgresql-client=${PG_VERSION} \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir \
        numpy==$(grep "numpy" requirements.txt | cut -d= -f3) \
        scipy==$(grep "scipy" requirements.txt | cut -d= -f3) \
    && pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

WORKDIR /usr/src/app

RUN cp config/config.dist.xml config/config.xml \
    && python setup.py ./config/config.xsd ./config/config.xml -v2 -d

ENTRYPOINT ["gunicorn"]
