"""Geoserver health check."""

import requests

from config import SpatialUtils
from django.conf import settings


def check_geoserver():
    """Check status of all geoserver services."""
    auth_headers = SpatialUtils.create_auth_headers(
        'admin',
        settings.MAP_SERVER_PASS,
        accepts='application/json')

    geoserver_status_url = 'http://%s:%s/geoserver/rest/about/status.json' % (
        settings.MAP_SERVER,
        settings.MAP_SERVER_PORT)

    geoserver_status = requests.get(
        geoserver_status_url,
        headers=auth_headers).json()['about']['status']

    # Health check should fail if all services aren't available.
    assert len(filter(lambda x: not x['isAvailable'],
               geoserver_status)) == 0
    return {'geoserver': {"ok": True}}
