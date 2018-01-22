"""publicmapping URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url, include
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.views.i18n import JavaScriptCatalog

admin.autodiscover()

from . import views as publicmapping_views
from redistricting.urls import urlpatterns as redistricting_urls

js_info_dict = {
    'domain': 'djangojs',
    'packages': ('publicmapping', 'redistricting'),
}

urlpatterns = ([
    url(r'^$', publicmapping_views.index),
    url(r'^i18n', include('django.conf.urls.i18n')),
    url(r'^rosetta', include('rosetta.urls')),
    url(r'^jsi18n$',
        JavaScriptCatalog.as_view(
            packages=js_info_dict['packages'], domain='djangojs'),
        name='javascript-catalog'),
    url(r'^accounts/register/$', publicmapping_views.userregister),
    url(r'^accounts/login/$', auth_views.login, {
        'template_name': 'index.html'
    }),
    url(r'^accounts/logout/$', publicmapping_views.userlogout),
    url(r'^accounts/forgot/$', publicmapping_views.forgotpassword),
    url(r'^accounts/update/$', publicmapping_views.userupdate),
    url(r'^districtmapping/', include(redistricting_urls)),
    url(r'^comments/', include('django_comments.urls')),
    url(r'^proxy/', publicmapping_views.proxy),
    url(r'^session', publicmapping_views.session),
    url(r'^admin', admin.site.urls),
    url(r'^i18n/', include('django.conf.urls.i18n'))
])
