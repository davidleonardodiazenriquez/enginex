from django.contrib.auth import views as auth_views
from django.urls import path

from core.forms import EnginexAuthenticationForm
from core.views import chat, dashboard, health, portfolio_map

urlpatterns = [
    path("", portfolio_map, name="portfolio"),
    path("assets/al-rayyana/", dashboard, name="dashboard"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="core/login.html",
            authentication_form=EnginexAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("health/", health, name="health"),
    path("api/chat/", chat, name="chat"),
]
