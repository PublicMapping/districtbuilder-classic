#!/bin/bash -x
patch  /projects/publicmapping/trunk/django/publicmapping/templates/index.html <  index.html.patch
patch  /projects/publicmapping/trunk/django/publicmapping/static/js/register.js<  register.js.patch
patch  /projects/publicmapping/trunk/django/publicmapping/templates/account.html <  account.html.patch
cp /projects/publicmapping/trunk/django/publicmapping/static/js/register.js /projects/publicmapping/trunk/django/publicmapping/site-media/js/register.js
cp /projects/publicmapping/trunk/django/publicmapping/static/js/register.js /projects/publicmapping/trunk/django/publicmapping/static-media/js/register.js

