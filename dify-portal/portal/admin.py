from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Bot, BotGrant, User


@admin.register(User)
class PortalUserAdmin(UserAdmin):
    readonly_fields = ("id", "must_change_password")
    fieldsets = UserAdmin.fieldsets + (("Portal 身分", {"fields": ("id", "must_change_password")}),)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.must_change_password = True
        super().save_model(request, obj, form, change)

    def user_change_password(self, request, id, form_url=""):
        response = super().user_change_password(request, id, form_url)
        if request.method == "POST" and response.status_code in {301, 302, 303, 307, 308}:
            self.model.objects.filter(pk=id).update(must_change_password=True)
        return response


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ("name", "dify_app_id", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "dify_app_id", "web_app_code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BotGrant)
class BotGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "bot", "created_at")
    list_select_related = ("user", "bot")
    search_fields = ("user__username", "bot__name")
    autocomplete_fields = ("user", "bot")
    readonly_fields = ("created_at",)
