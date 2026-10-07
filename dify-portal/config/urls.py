from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from portal.views import PortalPasswordChangeView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/change/", PortalPasswordChangeView.as_view(), name="password_change"),
    path("", include("portal.urls")),
]
