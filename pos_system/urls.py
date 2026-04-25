from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponse
from django.urls import include, path


urlpatterns = [
    path("health/", lambda request: HttpResponse("ok", content_type="text/plain"), name="health"),
    path("admin/", admin.site.urls),
    path("", include("cafeteria.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
