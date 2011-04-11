from django.conf.urls.defaults import *

from views import loadbard, getreport, index

urlpatterns = patterns('',
    # Example:
    # (r'^reporting/', include('reporting.foo.urls')),

    (r'^$', index),
    (r'^loadbard/', loadbard),
    (r'^getreport/$', getreport),
)
