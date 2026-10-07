from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Bot
from .forms import PortalPasswordChangeForm


class PortalPasswordChangeView(PasswordChangeView):
    form_class = PortalPasswordChangeForm
    template_name = "portal/password_change_form.html"
    success_url = reverse_lazy("portal:bot-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["password_change_required"] = self.request.user.must_change_password
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=["must_change_password"])
        return response


@never_cache
@require_safe
def health(request):
    return HttpResponse("ok", content_type="text/plain")


@never_cache
@login_required
@require_safe
def bot_list(request):
    return render(request, "portal/bot_list.html", {
        "bots": Bot.objects.available_to(request.user), "chat_enabled": settings.DIFY_GATEWAY_ENABLED,
    })
