import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """Stable identity independent of the editable username."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class BotQuerySet(models.QuerySet):
    def available_to(self, user):
        # Staff/superuser status grants administration, not Bot usage.
        if not user.is_authenticated or not user.is_active:
            return self.none()
        return self.filter(is_active=True, grants__user=user)


class Bot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("名稱", max_length=120)
    description = models.TextField("說明", blank=True)
    dify_app_id = models.UUIDField("Dify App ID", unique=True)
    web_app_code = models.CharField(
        "Web App code",
        max_length=128,
        unique=True,
        validators=[RegexValidator(r"\A[A-Za-z0-9_-]+\Z", "請輸入 Web App code，不要輸入網址。")],
    )
    is_active = models.BooleanField("啟用", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BotQuerySet.as_manager()

    class Meta:
        ordering = ["name", "id"]
        verbose_name = "Bot"
        verbose_name_plural = "Bot"

    def __str__(self):
        return self.name


class BotGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bot_grants")
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="grants")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "bot"], name="unique_user_bot_grant")]
        verbose_name = "Bot 授權"
        verbose_name_plural = "Bot 授權"

    def __str__(self):
        return f"{self.user} → {self.bot}"


class DifyIdentity(models.Model):
    """Opaque native session identity; never the Portal username."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE)
    app_id = models.UUIDField()
    app_code = models.CharField(max_length=128)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "bot", "app_id", "app_code"], name="unique_dify_identity",
        )]


class DifyPassport(models.Model):
    """Store only a credential digest, scoped to the grant and Portal login."""

    grant = models.ForeignKey(BotGrant, on_delete=models.CASCADE)
    identity = models.ForeignKey(DifyIdentity, on_delete=models.CASCADE)
    session_digest = models.CharField(max_length=64)
    token_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["grant", "identity", "session_digest", "token_digest"], name="unique_dify_passport",
        )]
