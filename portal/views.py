from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Bot


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


@never_cache
@login_required
@require_safe
def bot_detail(request, bot_id):
    # Recheck the grant on every request, including direct URL access.
    bot = get_object_or_404(Bot.objects.available_to(request.user), pk=bot_id)
    return render(request, "portal/bot_detail.html", {"bot": bot, "chat_enabled": settings.DIFY_GATEWAY_ENABLED})
