#!/bin/bash -x
patch  /projects/PublicMapping/DistrictBuilder/django/publicmapping/templates/index.html <  index.html.patch
patch  /projects/PublicMapping/DistrictBuilder/django/publicmapping/static/js/register.js<  register.js.patch
patch  /projects/PublicMapping/DistrictBuilder/django/publicmapping/templates/account.html <  account.html.patch
cp /projects/PublicMapping/DistrictBuilder/django/publicmapping/static/js/register.js /projects/PublicMapping/DistrictBuilder/django/publicmapping/site-media/js/register.js
cp /projects/PublicMapping/DistrictBuilder/django/publicmapping/static/js/register.js /projects/PublicMapping/DistrictBuilder/django/publicmapping/static-media/js/register.js

