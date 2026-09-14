from django.urls import path

from core.views import health, home

urlpatterns = [
    path("", home, name="home"),
    path("health/", health, name="health"),
]
