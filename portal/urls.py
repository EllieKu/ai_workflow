from django.urls import path

from . import gateway, views

app_name = "portal"
urlpatterns = [
    path("_internal/dify-auth", gateway.authorize_nginx, name="dify-auth"),
    path("", views.bot_list, name="bot-list"),
    path("bots/<uuid:bot_id>/", views.bot_detail, name="bot-detail"),
    path("chat/<slug:code>", gateway.chat_page, name="chat"),
    path("api/<path:path>", gateway.api, name="dify-api"),
    path("_next/static/<path:asset>", gateway.static_asset, name="dify-static"),
]
