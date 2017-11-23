# -*- coding: utf-8 -*-

from django.conf.urls import include, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib import admin

admin.autodiscover()

urlpatterns =  [
     url(r'^', include(admin.site.urls))
]

urlpatterns += staticfiles_urlpatterns()
