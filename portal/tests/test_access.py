import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from portal.models import Bot, BotGrant

User = get_user_model()


class PortalAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(username="alice", password="test-password-123")
        cls.bob = User.objects.create_user(username="bob", password="test-password-123")
        cls.admin = User.objects.create_superuser(username="admin", password="test-password-123")
        cls.bot_a = Bot.objects.create(
            name="Alice Bot", dify_app_id=uuid.uuid4(), web_app_code="alice-code", is_active=True,
        )
        cls.bot_b = Bot.objects.create(
            name="Bob Bot", dify_app_id=uuid.uuid4(), web_app_code="bob-code", is_active=True,
        )
        BotGrant.objects.create(user=cls.alice, bot=cls.bot_a)
        BotGrant.objects.create(user=cls.bob, bot=cls.bot_b)

    def detail_url(self, bot):
        return reverse("portal:bot-detail", args=[bot.pk])

    def test_health_check_does_not_require_login(self):
        response = self.client.get(reverse("portal:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_anonymous_cannot_view_list_or_detail(self):
        for url in [reverse("portal:bot-list"), self.detail_url(self.bot_a)]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login") + "?next="))

    def test_users_see_only_their_granted_bots(self):
        for user, allowed, denied in [(self.alice, self.bot_a, self.bot_b), (self.bob, self.bot_b, self.bot_a)]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("portal:bot-list"))
                self.assertContains(response, allowed.name)
                self.assertNotContains(response, denied.name)
                self.assertEqual(self.client.get(self.detail_url(allowed)).status_code, 200)
                self.assertEqual(self.client.get(self.detail_url(denied)).status_code, 404)

    def test_admin_has_no_implicit_bot_access(self):
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse("portal:bot-list")), self.bot_a.name)
        self.assertEqual(self.client.get(self.detail_url(self.bot_a)).status_code, 404)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_regular_user_cannot_enter_admin(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_staff_without_permissions_cannot_manage_grants(self):
        self.alice.is_staff = True
        self.alice.save(update_fields=["is_staff"])
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("admin:portal_botgrant_changelist")).status_code, 403)

    def test_admin_can_create_bot_grant(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin:portal_botgrant_add"), {
            "user": str(self.alice.pk), "bot": str(self.bot_b.pk), "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BotGrant.objects.filter(user=self.alice, bot=self.bot_b).exists())

    def test_view_permission_does_not_allow_grant_creation(self):
        self.alice.is_staff = True
        self.alice.save(update_fields=["is_staff"])
        self.alice.user_permissions.add(Permission.objects.get(codename="view_botgrant"))
        self.client.force_login(self.alice)
        response = self.client.post(reverse("admin:portal_botgrant_add"), {
            "user": str(self.alice.pk), "bot": str(self.bot_b.pk),
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(BotGrant.objects.filter(user=self.alice, bot=self.bot_b).exists())

    def test_revocation_applies_to_next_portal_request(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.detail_url(self.bot_a)).status_code, 200)
        BotGrant.objects.filter(user=self.alice, bot=self.bot_a).delete()
        self.assertEqual(self.client.get(self.detail_url(self.bot_a)).status_code, 404)
        self.assertNotContains(self.client.get(reverse("portal:bot-list")), self.bot_a.name)

    def test_disabled_bot_is_not_accessible(self):
        self.client.force_login(self.alice)
        self.bot_a.is_active = False
        self.bot_a.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.detail_url(self.bot_a)).status_code, 404)
        self.assertNotContains(self.client.get(reverse("portal:bot-list")), self.bot_a.name)

    def test_disabling_user_invalidates_portal_access(self):
        self.client.force_login(self.alice)
        self.alice.is_active = False
        self.alice.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.detail_url(self.bot_a)).status_code, 302)
        self.assertFalse(self.client.login(username="alice", password="test-password-123"))

    def test_client_supplied_identity_does_not_change_access(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.detail_url(self.bot_b), {
            "username": "bob", "user_id": str(self.bob.pk), "app_id": str(self.bot_a.dify_app_id),
        })
        self.assertEqual(response.status_code, 404)

    def test_bot_data_is_escaped_and_native_url_is_not_exposed(self):
        self.bot_a.description = "<script>alert('xss')</script>"
        self.bot_a.save(update_fields=["description"])
        self.client.force_login(self.alice)
        response = self.client.get(self.detail_url(self.bot_a))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>")
        self.assertNotContains(response, self.bot_a.web_app_code)
        self.assertNotContains(response, str(self.bot_a.dify_app_id))

    def test_authorized_pages_are_not_cached(self):
        self.client.force_login(self.alice)
        for url in [reverse("portal:bot-list"), self.detail_url(self.bot_a)]:
            self.assertIn("no-store", self.client.get(url)["Cache-Control"])

    def test_duplicate_grant_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BotGrant.objects.create(user=self.alice, bot=self.bot_a)

    def test_username_change_preserves_identity_and_grants(self):
        original_id = self.alice.pk
        self.alice.username = "alice-renamed"
        self.alice.save(update_fields=["username"])
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.pk, original_id)
        self.assertIsInstance(original_id, uuid.UUID)
        self.assertTrue(BotGrant.objects.filter(user_id=original_id, bot=self.bot_a).exists())


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="test-password-123")
        self.client = Client(enforce_csrf_checks=True)

    def csrf_token(self, url):
        self.client.get(url)
        return self.client.cookies["portal_csrftoken"].value

    def login(self, **extra):
        token = self.csrf_token(reverse("login"))
        return self.client.post(reverse("login"), {
            "username": "alice", "password": "test-password-123", "csrfmiddlewaretoken": token, **extra,
        })

    def test_login_requires_csrf(self):
        response = self.client.post(reverse("login"), {"username": "alice", "password": "test-password-123"})
        self.assertEqual(response.status_code, 403)

    def test_login_with_csrf_succeeds(self):
        self.assertRedirects(self.login(), reverse("portal:bot-list"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertNotEqual(self.user.password, "test-password-123")
        self.assertTrue(self.user.check_password("test-password-123"))

    def test_login_rejects_wrong_password(self):
        response = self.login(password="wrong")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_cannot_redirect_to_external_site(self):
        self.assertRedirects(self.login(next="https://attacker.example/"), reverse("portal:bot-list"))

    def test_logout_requires_post_and_csrf(self):
        self.login()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 403)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_invalidates_saved_session(self):
        self.login()
        old_session = self.client.cookies["portal_sessionid"].value
        response = self.client.post(reverse("logout"), {
            "csrfmiddlewaretoken": self.client.cookies["portal_csrftoken"].value,
        })
        self.assertRedirects(response, reverse("login"))
        self.client.cookies["portal_sessionid"] = old_session
        self.assertEqual(self.client.get(reverse("portal:bot-list")).status_code, 302)
