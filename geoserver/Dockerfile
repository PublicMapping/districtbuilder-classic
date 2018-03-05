# A GeoServer installation
FROM openjdk:8-jre-slim

ENV GEOSERVER_VERSION 2.11.2
ENV GEOSERVER_ZIP_URL https://s3.amazonaws.com/district-builder-global-artifacts-us-east-1/deps/geoserver-${GEOSERVER_VERSION}-bin.zip

ENV GEOSERVER_DIR /usr/share
ENV GEOSERVER_EXT_DIR $GEOSERVER_DIR/geoserver-$GEOSERVER_VERSION/webapps/geoserver/WEB-INF/lib
ENV PATH /usr/share/geoserver-$GEOSERVER_VERSION/bin:$PATH
ENV JAVA_HOME /usr/lib/jvm/java-1.8.0-openjdk-amd64
ENV GEOSERVER_HOME $GEOSERVER_DIR/geoserver-$GEOSERVER_VERSION/

RUN apt-get update && \
  apt-get install -y -qq ca-certificates openssl unzip wget curl && \
  update-ca-certificates && \
  wget -O $GEOSERVER_DIR/geoserver.zip $GEOSERVER_ZIP_URL && \
  unzip -qq $GEOSERVER_DIR/geoserver.zip -d $GEOSERVER_DIR && \
  rm $GEOSERVER_DIR/geoserver.zip

ENV GEOSERVER_DATA_DIR /data

VOLUME $GEOSERVER_DATA_DIR

COPY ./jetty.xml $GEOSERVER_DIR/etc/jetty.xml
COPY ./geoserver-startup.sh $GEOSERVER_HOME/bin/geoserver-startup.sh
COPY ./change_admin_password.sh $GEOSERVER_HOME/bin/change_admin_password.sh

WORKDIR $GEOSERVER_HOME

CMD ["sh", "bin/geoserver-startup.sh"]
