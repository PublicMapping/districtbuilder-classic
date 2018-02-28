#!/bin/bash
# -----------------------------------------------------------------------------
# Attempt to reset the admin user's password.
#
# By default, the admin username is 'admin' and the password is 'geoserver'.
# This needs to be reset to provide some minimum level of security.
# -----------------------------------------------------------------------------

echo "Attempting to set a new Geoserver admin password..."
echo "Note that this assumes the current password is the default ('geoserver')"

# Sometimes geoserver is not ready to receive API calls for whatever reason.
# Retrying seems to do the trick.
for i in {1..5}; do
  curl --silent -X PUT http://localhost:${WEB_APP_PORT}/geoserver/rest/security/self/password \
    -u admin:geoserver \
    -H "accept: application/json" \
    -H "content-type: application/json" \
    -d "{\"newPassword\": \"${MAP_SERVER_ADMIN_PASSWORD}\"}"

  if [ 0 -eq $? ]; then
    echo 'Request to update password made successfully!'
    exit 0
  else
    echo 'Request to update password failed. Retrying...'
    sleep 10
  fi;
done

echo 'Request to update password failed permanently.'
exit 1
