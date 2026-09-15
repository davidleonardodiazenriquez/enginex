"""Automatic workspace sessions when demo access is explicitly enabled."""

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.http import HttpResponse


class DemoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        excluded = request.path_info in {"/health/", "/admin"} or request.path_info.startswith("/admin/")
        enabled = settings.DEMO_AUTO_LOGIN or (settings.DEBUG and settings.LOCAL_DEMO_AUTO_LOGIN)
        request.demo_access = enabled and not excluded
        if request.demo_access and not request.user.is_authenticated:
            try:
                user = get_user_model().objects.get(username="demo", is_active=True, is_staff=False, is_superuser=False)
            except get_user_model().DoesNotExist:
                return HttpResponse("The workspace account is unavailable. Restore or enable the account.", status=503)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_response(request)
