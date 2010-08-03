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
    (r'^districtmapping/', include('publicmapping.redistricting.urls')),
    (r'^$', 'publicmapping.views.index'),
    (r'^proxy$', 'publicmapping.views.proxy'),
    (r'^sld/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.SLD_ROOT }),
)
