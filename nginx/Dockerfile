FROM nginx:1.12

ARG WEB_APP_PORT

COPY nginx/default.template /etc/nginx/conf.d/default.template
COPY django/publicmapping/static/ /opt/static/

RUN envsubst < /etc/nginx/conf.d/default.template \
        > /etc/nginx/conf.d/default.conf \
    && rm /etc/nginx/conf.d/default.template \
    && chown -R nginx:nginx /opt/static
