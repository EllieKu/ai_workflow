import base64
import io
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from portal.gateway import GatewayUnavailable
from portal.models import Bot, BotGrant, DifyIdentity, DifyPassport


class Upstream(io.BytesIO):
    def __init__(self, body=b"{}", status=200, content_type="application/json"):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Type": content_type, "Set-Cookie": "upstream=secret"}


@override_settings(DIFY_GATEWAY_ENABLED=True, DIFY_AUTH_REQUEST_SECRET="nginx-test-secret")
class GatewayTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(username="alice", password="test-password")
        self.bob = get_user_model().objects.create_user(username="bob", password="test-password")
        self.bot = Bot.objects.create(
            name="Bot", dify_app_id=uuid.uuid4(), web_app_code="test-code", is_active=True,
        )
        self.grant = BotGrant.objects.create(user=self.alice, bot=self.bot)
        BotGrant.objects.create(user=self.bob, bot=self.bot)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)

    def native_token(self, bot=None):
        bot = bot or self.bot
        payload = base64.urlsafe_b64encode(json.dumps({
            "app_id": str(bot.dify_app_id), "app_code": bot.web_app_code, "end_user_id": str(uuid.uuid4()),
        }).encode()).decode().rstrip("=")
        return "test-header." + payload + ".test-signature"

    def issue(self, client=None, token=None):
        token = token or self.native_token()
        with patch("portal.gateway.open_upstream", return_value=Upstream(json.dumps({"access_token": token}).encode())):
            response = (client or self.client).get("/api/passport", HTTP_X_APP_CODE=self.bot.web_app_code)
        self.assertEqual(response.status_code, 200)
        return token

    def api(self, path="site", token="missing", **kwargs):
        return self.client.get("/api/" + path, HTTP_X_APP_CODE=self.bot.web_app_code, HTTP_X_APP_PASSPORT=token, **kwargs)

    def authorize(self, uri, method="GET", token="", code="test-code", **extra):
        return self.client.get(
            "/_internal/dify-auth",
            HTTP_X_PORTAL_AUTH_SECRET="nginx-test-secret",
            HTTP_X_ORIGINAL_URI=uri,
            HTTP_X_ORIGINAL_METHOD=method,
            HTTP_X_ORIGINAL_APP_CODE=code,
            HTTP_X_ORIGINAL_APP_PASSPORT=token,
            **extra,
        )

    def test_nginx_auth_requires_shared_secret_and_login(self):
        self.assertEqual(self.client.get(
            "/_internal/dify-auth",
            HTTP_X_ORIGINAL_URI="/chat/test-code",
            HTTP_X_ORIGINAL_METHOD="GET",
        ).status_code, 403)
        self.client.logout()
        self.assertEqual(self.authorize("/chat/test-code").status_code, 401)

    def test_nginx_auth_allows_only_granted_chat_page(self):
        self.assertEqual(self.authorize("/chat/test-code").status_code, 204)
        self.assertEqual(self.authorize("/chat/not-granted").status_code, 403)

    def test_nginx_auth_rejects_ambiguous_app_code(self):
        self.assertEqual(self.authorize(
            "/api/webapp/access-mode?appCode=test-code&appCode=other",
        ).status_code, 403)

    def test_nginx_auth_binds_api_to_registered_passport_and_session(self):
        token = self.issue()
        self.assertEqual(self.authorize("/api/site", token=token).status_code, 204)
        self.assertEqual(self.authorize("/api/site", token=self.native_token()).status_code, 401)
        self.client.force_login(self.bob)
        self.assertEqual(self.authorize("/api/site", token=token).status_code, 401)

    def test_nginx_auth_rechecks_grant_and_allowlist(self):
        token = self.issue()
        self.assertEqual(self.authorize("/api/chat-messages/task/stop", "POST", token,
                                        HTTP_X_ORIGINAL_ORIGIN="http://testserver",
                                        HTTP_X_ORIGINAL_SCHEME="http",
                                        HTTP_X_ORIGINAL_HOST="testserver").status_code, 403)
        self.grant.delete()
        self.assertEqual(self.authorize("/api/site", token=token).status_code, 403)

    def test_nginx_auth_requires_exact_origin_for_writes(self):
        token = self.issue()
        common = {
            "HTTP_X_ORIGINAL_SCHEME": "https",
            "HTTP_X_ORIGINAL_HOST": "portal.example.com",
        }
        self.assertEqual(self.authorize(
            "/api/chat-messages", "POST", token,
            HTTP_X_ORIGINAL_ORIGIN="https://portal.example.com", **common,
        ).status_code, 204)
        self.assertEqual(self.authorize(
            "/api/chat-messages", "POST", token,
            HTTP_X_ORIGINAL_ORIGIN="https://attacker.example", **common,
        ).status_code, 403)

    def test_gateway_disabled_by_default_configuration(self):
        with override_settings(DIFY_GATEWAY_ENABLED=False), patch("portal.gateway.open_upstream") as upstream:
            self.assertEqual(self.api().status_code, 404)
            self.assertEqual(self.client.get("/chat/test-code").status_code, 404)
            upstream.assert_not_called()

    def test_anonymous_cannot_get_passport(self):
        self.client.logout()
        with patch("portal.gateway.open_upstream") as upstream:
            self.assertEqual(self.api("passport").status_code, 401)
            upstream.assert_not_called()

    def test_unauthorized_bot_never_reaches_upstream(self):
        self.grant.delete()
        with patch("portal.gateway.open_upstream") as upstream:
            self.assertEqual(self.api("passport").status_code, 404)
            self.assertEqual(self.client.get("/chat/test-code").status_code, 404)
            upstream.assert_not_called()

    def test_passport_ignores_browser_identity_and_stores_only_digest(self):
        token = self.native_token()
        with patch("portal.gateway.open_upstream", return_value=Upstream(json.dumps({"access_token": token}).encode())) as upstream:
            response = self.api("passport?user_id=victim&app_id=wrong", token="foreign")
        self.assertEqual(response.status_code, 200)
        identity = DifyIdentity.objects.get()
        self.assertIn(str(identity.session_id), upstream.call_args.args[0])
        self.assertNotIn("victim", upstream.call_args.args[0])
        self.assertEqual(upstream.call_args.kwargs["headers"], {"X-App-Code": self.bot.web_app_code})
        self.assertEqual(len(DifyPassport.objects.get().token_digest), 64)
        self.assertNotEqual(DifyPassport.objects.get().token_digest, token)
        self.assertIn("no-store", response["Cache-Control"])

    def test_wrong_upstream_app_id_is_rejected(self):
        wrong = Bot(name="wrong", dify_app_id=uuid.uuid4(), web_app_code="wrong")
        with patch("portal.gateway.open_upstream", return_value=Upstream(json.dumps({"access_token": self.native_token(wrong)}).encode())):
            self.assertEqual(self.api("passport").status_code, 502)
        self.assertFalse(DifyPassport.objects.exists())

    def test_malformed_upstream_passport_fails_closed(self):
        claims = {
            "app_id": str(self.bot.dify_app_id), "app_code": self.bot.web_app_code,
        }
        invalid_claims = [None, [], "text", claims, {**claims, "end_user_id": []},
                          {**claims, "end_user_id": "invalid-uuid"}]
        bodies = [None, [], {}, {"access_token": "invalid"}, {"access_token": 123}]
        for value in invalid_claims:
            encoded = base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
            bodies.append({"access_token": "header." + encoded + ".signature"})
        for body in bodies:
            with self.subTest(body=body), patch(
                "portal.gateway.open_upstream", return_value=Upstream(json.dumps(body).encode()),
            ):
                self.assertEqual(self.api("passport").status_code, 502)
                self.assertFalse(DifyPassport.objects.exists())
                self.assertFalse(DifyIdentity.objects.exists())

    def test_other_authorized_bot_cannot_reuse_passport(self):
        token = self.issue()
        other_bot = Bot.objects.create(
            name="Other", dify_app_id=uuid.uuid4(), web_app_code="other-code", is_active=True,
        )
        BotGrant.objects.create(user=self.alice, bot=other_bot)
        with patch("portal.gateway.open_upstream") as upstream:
            response = self.client.get(
                "/api/site", HTTP_X_APP_CODE=other_bot.web_app_code, HTTP_X_APP_PASSPORT=token,
            )
            self.assertEqual(response.status_code, 401)
            upstream.assert_not_called()

    def test_stop_task_blocked_until_owner_verification_is_implemented(self):
        token = self.issue()
        with patch("portal.gateway.open_upstream") as upstream:
            response = self.client.post(
                f"/api/chat-messages/{uuid.uuid4()}/stop", {}, content_type="application/json",
                HTTP_X_APP_CODE=self.bot.web_app_code, HTTP_X_APP_PASSPORT=token,
                HTTP_ORIGIN="http://testserver",
            )
            self.assertEqual(response.status_code, 403)
            upstream.assert_not_called()

    def test_issued_token_allows_requests_but_does_not_forward_cookies(self):
        token = self.issue()
        upstream_response = Upstream(b'{"name":"Test"}')
        with patch("portal.gateway.open_upstream", return_value=upstream_response) as upstream:
            response = self.api(token=token, HTTP_AUTHORIZATION="Bearer other")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b'{"name":"Test"}')
        self.assertEqual(upstream.call_args.kwargs["headers"], {
            "X-App-Code": self.bot.web_app_code, "X-App-Passport": token,
        })
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertTrue(upstream_response.closed)

    def test_native_token_without_portal_registration_is_rejected(self):
        with patch("portal.gateway.open_upstream") as upstream:
            self.assertEqual(self.api(token=self.native_token()).status_code, 401)
            upstream.assert_not_called()

    def test_other_user_cannot_reuse_passport_for_same_bot(self):
        token = self.issue()
        self.client.force_login(self.bob)
        with patch("portal.gateway.open_upstream") as upstream:
            self.assertEqual(self.api(token=token).status_code, 401)
            upstream.assert_not_called()

    def test_new_login_cannot_reuse_old_registered_passport(self):
        token = self.issue()
        other = Client()
        other.force_login(self.alice)
        self.assertEqual(other.get("/api/site", HTTP_X_APP_CODE="test-code", HTTP_X_APP_PASSPORT=token).status_code, 401)

    def test_revoke_then_regrant_does_not_restore_old_passport(self):
        token = self.issue()
        self.grant.delete()
        self.assertEqual(self.api(token=token).status_code, 404)
        BotGrant.objects.create(user=self.alice, bot=self.bot)
        self.assertEqual(self.api(token=token).status_code, 401)

    def test_bot_rebinding_invalidates_passport(self):
        token = self.issue()
        self.bot.dify_app_id = uuid.uuid4()
        self.bot.save()
        self.assertEqual(self.api(token=token).status_code, 401)

    def test_disabled_bot_or_account_cannot_use_passport(self):
        token = self.issue()
        self.bot.is_active = False
        self.bot.save()
        self.assertEqual(self.api(token=token).status_code, 404)
        self.alice.is_active = False
        self.alice.save()
        self.assertEqual(self.api(token=token).status_code, 401)

    def test_expired_passport_is_rejected(self):
        token = self.issue()
        DifyPassport.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.api(token=token).status_code, 401)

    def test_header_and_query_app_mismatch_rejected(self):
        self.assertEqual(self.api("webapp/access-mode?appCode=other").status_code, 403)

    def test_access_mode_uses_validated_code_not_client_app_id(self):
        with patch("portal.gateway.open_upstream", return_value=Upstream()) as upstream:
            response = self.api("webapp/access-mode?appId=victim&appCode=test-code")
            response.close()
        self.assertEqual(upstream.call_args.args[0], "/api/webapp/access-mode?appCode=test-code")

    def test_unreviewed_api_routes_fail_closed(self):
        token = self.issue()
        for path in ["files/upload", "remote-files/upload", "workflows/run", "audio-to-text", "logout", "../console/api/apps"]:
            with self.subTest(path=path), patch("portal.gateway.open_upstream") as upstream:
                self.assertEqual(self.api(path, token=token).status_code, 403)
                upstream.assert_not_called()

    def test_files_and_service_api_are_not_proxied(self):
        for path in ["/files/fake/file-preview", "/v1/chat-messages", "/mcp/test", "/console/api/apps"]:
            self.assertEqual(self.client.get(path).status_code, 404)

    def post_chat(self, token, origin="http://testserver", **body):
        return self.client.post(
            "/api/chat-messages", {"inputs": {}, "query": "Hello", "response_mode": "streaming", **body},
            content_type="application/json", HTTP_X_APP_CODE="test-code", HTTP_X_APP_PASSPORT=token,
            HTTP_ORIGIN=origin,
        )

    def test_write_requires_exact_origin_even_with_passport(self):
        token = self.issue()
        for origin in ["", "null", "http://attacker.example", "https://testserver"]:
            with self.subTest(origin=origin), patch("portal.gateway.open_upstream") as upstream:
                self.assertEqual(self.post_chat(token, origin=origin).status_code, 403)
                upstream.assert_not_called()

    def test_chat_stream_relay(self):
        token = self.issue()
        with patch("portal.gateway.open_upstream", return_value=Upstream(b'data: {"answer":"hello"}\n\n', content_type="text/event-stream")) as upstream:
            response = self.post_chat(token, user_id="victim", app_id="other")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'"answer":"hello"', b"".join(response.streaming_content))
            self.assertEqual(response["X-Accel-Buffering"], "no")
        forwarded = json.loads(upstream.call_args.kwargs["data"])
        self.assertNotIn("user_id", forwarded)
        self.assertNotIn("app_id", forwarded)

    def test_file_payload_is_rejected(self):
        token = self.issue()
        with patch("portal.gateway.open_upstream") as upstream:
            self.assertEqual(self.post_chat(token, files=[{"upload_file_id": "other"}]).status_code, 400)
            self.assertEqual(self.post_chat(token, inputs={"file": {"upload_file_id": "other"}}).status_code, 400)
            upstream.assert_not_called()

    def test_upstream_failure_is_generic(self):
        with patch("portal.gateway.open_upstream", side_effect=GatewayUnavailable("secret")):
            response = self.api("passport")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(b"secret", response.content)

    def test_chat_page_requires_grant_and_has_no_upstream_cookie(self):
        with patch("portal.gateway.open_upstream", return_value=Upstream(b"<html></html>", content_type="text/html")):
            response = self.client.get("/chat/test-code")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"<html></html>")
            self.assertNotIn("Set-Cookie", response.headers)

    def test_static_path_traversal_is_blocked(self):
        with patch("portal.gateway.open_upstream") as upstream:
            self.assertEqual(self.client.get("/_next/static/../server.js").status_code, 404)
            upstream.assert_not_called()

    def test_repeated_issuance_keeps_opaque_identity(self):
        self.issue()
        original = DifyIdentity.objects.get().session_id
        self.issue()
        self.assertEqual(DifyIdentity.objects.count(), 1)
        self.assertEqual(DifyIdentity.objects.get().session_id, original)
