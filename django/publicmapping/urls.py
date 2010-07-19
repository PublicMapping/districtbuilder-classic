from django.conf.urls.defaults import *
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^publicmapping/', include('publicmapping.foo.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    (r'^site-media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT }),
    (r'^accounts/register/$', 'publicmapping.views.userregister'),
    (r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'index.html'}),
    (r'^accounts/logout/$', 'publicmapping.views.userlogout'),
    (r'^districtmapping/$', 'publicmapping.redistricting.views.editplan', { 'planid': 0 }),
    (r'^districtmapping/plan/(?P<planid>\d*)$', 'publicmapping.views.plan'),
    (r'^$', 'publicmapping.views.index'),
    (r'^proxy$', 'publicmapping.views.proxy'),
    (r'^districtmapping/plan/create/$', 'publicmapping.redistricting.views.createplan'),
    (r'^districtmapping/plan/choose/$', 'publicmapping.redistricting.views.chooseplan'),
    (r'^districtmapping/plan/(?P<planid>\d*)/edit/$', 'publicmapping.redistricting.views.editplan'),
    (r'^districtmapping/plan/(?P<planid>\d*)/copy/$', 'publicmapping.redistricting.views.copyplan'),
    (r'^districtmapping/plan/(?P<planid>\d*)/district/(?P<districtid>\d*)/add', 'publicmapping.redistricting.views.addtodistrict'),
    (r'^districtmapping/plan/(?P<planid>\d*)/geounits/delete', 'publicmapping.redistricting.views.deletefromplan'),
    (r'^districtmapping/plan/(?P<planid>\d*)/demographics', 'publicmapping.redistricting.views.getdemographics'),
    (r'^districtmapping/plan/(?P<planid>\d*)/geography', 'publicmapping.redistricting.views.getgeography'),)
