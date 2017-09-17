FROM python:2.7

RUN mkdir -p /projects/PublicMapping/DistrictBuilder
WORKDIR /projects/PublicMapping/DistrictBuilder

RUN apt-key adv --keyserver ha.pool.sks-keyservers.net --recv-keys B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8

RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ jessie-pgdg main' ${PG_MAJOR} > /etc/apt/sources.list.d/pgdg.list

RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        gettext \
        postgresql-client \
        libfreetype6-dev \
        r-base-dev \
        build-essential \
        libgeos-dev \
        default-jdk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /projects/PublicMapping/DistrictBuilder
RUN pip install --no-cache-dir \
        numpy==$(grep "numpy" requirements.txt | cut -d= -f3) \
        scipy==$(grep "scipy" requirements.txt | cut -d= -f3) \
    && pip install --no-cache-dir -r requirements.txt

RUN R CMD javareconf &&\
    Rscript -e 'install.packages("R2HTML", dependencies=TRUE, repos="http://cran.us.r-project.org")' && \
    Rscript -e 'install.packages("stringr", dependencies=TRUE, repos="http://cran.us.r-project.org")' && \
    Rscript -e 'install.packages("ineq", dependencies=TRUE, repos="http://cran.us.r-project.org")' && \
    Rscript -e 'install.packages("rgeos", repos="http://R-Forge.R-project.org", dependencies=TRUE)' && \
    Rscript -e 'install.packages("BARD", dependencies=TRUE, repos="http://cran.us.r-project.org")'

RUN useradd -G www-data --create-home --shell /bin/bash celery

RUN mkdir -p /projects/PublicMapping/data && cd /projects/PublicMapping/data && \
    wget --no-check-certificate -O VA_data.zip https://s3.amazonaws.com/districtbuilderdata/VA_data.zip && \
    mkdir -p /projects/PublicMapping/local/data && cd /projects/PublicMapping/local/data && \
    unzip /projects/PublicMapping/data/VA_data.zip

COPY . /projects/PublicMapping/DistrictBuilder

RUN wget --no-check-certificate -O /etc/init.d/celeryd \
         https://raw.githubusercontent.com/celery/celery/master/extra/generic-init.d/celeryd && \
         chmod a+x /etc/init.d/celeryd  && \
         update-rc.d celeryd defaults && \
         ./write_celeryd.sh && \
         mkdir /var/log/celery /var/run/celery && \
         chown -R celery:www-data /var/log/celery /var/run/celery/ && \
         chmod -R 2775 /var/log/celery /var/run/celery/


RUN cat docs/config.dist.xml | sed -e 's|<Database name="YOUR-DATABASE-NAME" user="publicmapping" password="YOUR-DATABASE-PASSWORD" host="OPTIONAL"/>|<Database name="postgres" user="postgres" password="postgres" host="postgres"/>|' > docs/config.xml

ENTRYPOINT ["bash"]
CMD ["start.sh"]