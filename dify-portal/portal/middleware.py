from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Keep accounts with temporary passwords outside protected Portal routes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.must_change_password and not self._is_allowed(request.path):
            if request.path.startswith("/api/"):
                response = JsonResponse(
                    {"code": "password_change_required", "message": "請先修改臨時密碼。"},
                    status=403,
                )
            elif request.path.startswith("/_internal/"):
                response = HttpResponse(status=403)
            else:
                response = redirect("password_change")
            response["Cache-Control"] = "no-store"
            return response
        return self.get_response(request)

    @staticmethod
    def _is_allowed(path):
        return (
            path in {reverse("password_change"), reverse("logout"), reverse("login"), reverse("portal:health")}
            or path.startswith("/admin/")
            or path.startswith(settings.STATIC_URL)
        )
