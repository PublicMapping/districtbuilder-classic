FROM nginx:1.12

ARG WEB_APP_PORT

COPY nginx/default.template /etc/nginx/conf.d/default.template
COPY django/publicmapping/static/ /opt/static/

# Whitelist all environment variables that can be replaced in the nginx config
# template (the way `envsubst` works you can't escape characters to avoid
# substitution, only whitelist the variables you want to substitute). That way
# we are free to use nginx variables such as $host without them being
# substituted when the template is built.
RUN envsubst '$WEB_APP_PORT' < /etc/nginx/conf.d/default.template \
        > /etc/nginx/conf.d/default.conf \
    && rm /etc/nginx/conf.d/default.template

RUN chown -R nginx:nginx /opt/static
