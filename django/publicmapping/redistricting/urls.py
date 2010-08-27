from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('publicmapping.redistricting.views',
    (r'^$', 'editplan', { 'planid': 0 }),
    (r'^plan/create/$', 'createplan'),
    (r'^plan/choose/$', 'chooseplan'),
    (r'^plan/(?P<planid>\d*)/view/$', 'viewplan'),
    (r'^plan/(?P<planid>\d*)/edit/$', 'editplan'),
    (r'^plan/(?P<planid>\d*)/getreport/$', 'getreport'),
    (r'^plan/(?P<planid>\d*)/copy/$', 'copyplan'),
    (r'^plan/(?P<planid>\d*)/district/(?P<districtid>\d*)/add', 'addtodistrict'),
    (r'^plan/(?P<planid>\d*)/demographics', 'getdemographics'),
    (r'^plan/(?P<planid>\d*)/geography', 'getgeography'),
    (r'^plan/(?P<planid>\d*)/district/new', 'newdistrict'),
    (r'^plan/(?P<planid>\d*)/district/versioned', 'simple_district_versioned'),
)
