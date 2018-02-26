#!/bin/bash
# -----------------------------------------------------------------------------
# Attempt to reset the admin user's password.
#
# By default, the admin username is 'admin` and the password is 'geoserver'.
# This nees to be reset to provide some minimum level of security.
# -----------------------------------------------------------------------------

echo "Attempting to set a new admin password..."
echo "Note that this assumes the current password is the default ('geoserver')"

curl -X PUT http://localhost:${WEB_APP_PORT}/geoserver/rest/security/self/password \
  -u admin:geoserver \
  -H "accept: application/json" \
  -H "content-type: application/json" \
  -d "{\"newPassword\": \"${MAP_SERVER_ADMIN_PASSWORD}\"}"

