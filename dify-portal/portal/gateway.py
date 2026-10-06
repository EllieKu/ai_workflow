"""Restricted text-chat gateway for the official Dify 1.17.1 Web App.

The original Dify listener MUST be private. This module is not a general proxy:
unreviewed routes, file operations and non-text chat inputs fail closed.
"""

import base64
import hashlib
import json
import re
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe

from .models import BotGrant, DifyIdentity, DifyPassport

UUID_PATH = r"[0-9a-fA-F-]{36}"
API_ROUTES = [
    (r"(?:site|parameters|meta|conversations|messages)", {"GET"}),
    (r"chat-messages", {"POST"}),
    (rf"conversations/{UUID_PATH}", {"DELETE"}),
    (rf"conversations/{UUID_PATH}/name", {"POST"}),
    (rf"conversations/{UUID_PATH}/(?:pin|unpin)", {"PATCH"}),
    (rf"messages/{UUID_PATH}/feedbacks", {"POST"}),
    (rf"messages/{UUID_PATH}/suggested-questions", {"GET"}),
    # Dify 1.17.1's graph stop command is not gated by the legacy owner
    # check's result. Keep stop blocked until task ownership is verified.
]


class GatewayUnavailable(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_upstream(path, *, method="GET", data=None, headers=None, timeout=None):
    """Use only the configured origin, no environment proxy or redirects."""
    origin = urlsplit(settings.DIFY_UPSTREAM_URL)
    if (origin.scheme not in {"http", "https"} or not origin.netloc
            or origin.username or origin.password or origin.query or origin.fragment
            or origin.path not in {"", "/"}):
        raise GatewayUnavailable()
    if not path.startswith("/") or path.startswith("//") or "\r" in path or "\n" in path:
        raise GatewayUnavailable()
    request = Request(
        settings.DIFY_UPSTREAM_URL.rstrip("/") + path,
        data=data, method=method,
        headers={"Accept-Encoding": "identity", **(headers or {})},
    )
    try:
        return build_opener(ProxyHandler({}), NoRedirect()).open(
            request, timeout=timeout or settings.DIFY_GATEWAY_TIMEOUT,
        )
    except HTTPError as response:
        if 300 <= response.code < 400:
            response.close()
            raise GatewayUnavailable() from None
        return response
    except (URLError, OSError, ValueError):
        raise GatewayUnavailable() from None


def session_digest(request):
    return salted_hmac("portal.dify.session", request.session.session_key or "", algorithm="sha256").hexdigest()


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def grant_for(request, code):
    return get_object_or_404(
        BotGrant.objects.select_related("bot"),
        user=request.user, bot__web_app_code=code, bot__is_active=True,
    )


def require_enabled():
    if not settings.DIFY_GATEWAY_ENABLED:
        raise Http404


def passport_for(request, grant, token=None):
    if token is None:
        token = request.headers.get("X-App-Passport", "")
    if not token or len(token) > 8192:
        return None
    return DifyPassport.objects.filter(
        grant=grant, identity__user=request.user, identity__bot=grant.bot,
        identity__app_id=grant.bot.dify_app_id, identity__app_code=grant.bot.web_app_code,
        token_digest=token_digest(token), session_digest=session_digest(request),
        expires_at__gt=timezone.now(),
    ).first()


def _auth_response(status):
    response = HttpResponse(status=status)
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@require_safe
def authorize_nginx(request):
    """Authorize an Nginx auth_request without relaying the original body."""
    require_enabled()
    expected_secret = settings.DIFY_AUTH_REQUEST_SECRET
    supplied_secret = request.headers.get("X-Portal-Auth-Secret", "")
    if not expected_secret or not constant_time_compare(supplied_secret, expected_secret):
        return _auth_response(403)
    if not request.user.is_authenticated or not request.user.is_active:
        return _auth_response(401)

    original_uri = request.headers.get("X-Original-URI", "")
    original_method = request.headers.get("X-Original-Method", "").upper()
    if (not original_uri or len(original_uri) > 4096 or "\r" in original_uri
            or "\n" in original_uri or original_method not in {"GET", "HEAD", "POST", "PATCH", "DELETE"}):
        return _auth_response(403)
    parsed = urlsplit(original_uri)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return _auth_response(403)

    if original_method not in {"GET", "HEAD"}:
        origin = request.headers.get("X-Original-Origin", "")
        expected_origin = (
            request.headers.get("X-Original-Scheme", "") + "://"
            + request.headers.get("X-Original-Host", "")
        )
        if not origin or origin != expected_origin:
            return _auth_response(403)

    try:
        chat_match = re.fullmatch(r"/chat/([A-Za-z0-9_-]{1,128})/?", parsed.path)
        if chat_match and original_method in {"GET", "HEAD"}:
            grant_for(request, chat_match.group(1))
            return _auth_response(204)

        if not parsed.path.startswith("/api/"):
            return _auth_response(403)
        path = parsed.path.removeprefix("/api/").rstrip("/")
        if path == "system-features" and original_method in {"GET", "HEAD"}:
            return _auth_response(204)

        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        code = request.headers.get("X-Original-App-Code", "")
        query_key = "appCode" if path == "webapp/access-mode" else "app_code"
        query_codes = [value for key, value in query_pairs if key == query_key]
        if len(query_codes) > 1:
            return _auth_response(403)
        query_code = query_codes[0] if query_codes else None
        if code and query_code and code != query_code:
            return _auth_response(403)
        code = code or query_code or ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", code):
            return _auth_response(403)
        grant = grant_for(request, code)

        if path == "webapp/access-mode" and original_method in {"GET", "HEAD"}:
            return _auth_response(204)
        if path in {"passport", "login/status"}:
            # Public Nginx routes proxy these small responses to Django.
            return _auth_response(403)
        if not any(re.fullmatch(pattern, path) and original_method in methods for pattern, methods in API_ROUTES):
            return _auth_response(403)

        original_passport = request.headers.get("X-Original-App-Passport", "")
        if passport_for(request, grant, original_passport) is None:
            return _auth_response(401)
        return _auth_response(204)
    except Http404:
        return _auth_response(403)


def issue_passport(request, grant):
    # SQLite IMMEDIATE serializes initial EndUser resolution across workers.
    # Native EndUser lacks a unique app/session constraint, so do not allow
    # concurrent first-time issuance. The outbound call is bounded to 5 seconds.
    # Only issuance holds this transaction; chat and SSE never do.
    with transaction.atomic():
        identity, _ = DifyIdentity.objects.get_or_create(
            user=request.user, bot=grant.bot,
            app_id=grant.bot.dify_app_id, app_code=grant.bot.web_app_code,
        )
        with open_upstream(
            "/api/passport?" + urlencode({"user_id": str(identity.session_id)}),
            headers={"X-App-Code": grant.bot.web_app_code}, timeout=5,
        ) as upstream:
            if upstream.status != 200:
                raise GatewayUnavailable()
            try:
                body = json.loads(upstream.read(65537))
                if not isinstance(body, dict):
                    raise ValueError()
                token = body["access_token"]
                if not isinstance(token, str) or len(token) > 8192:
                    raise ValueError()
                parts = token.split(".")
                if len(parts) != 3 or not all(parts):
                    raise ValueError()
                encoded = parts[1]
                claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                # This is a consistency check on a response obtained directly
                # from our trusted upstream, NOT validation of client JWTs.
                if (not isinstance(claims, dict)
                        or claims.get("app_id") != str(grant.bot.dify_app_id)
                        or claims.get("app_code") != grant.bot.web_app_code):
                    raise ValueError()
                end_user_id = claims.get("end_user_id")
                if not isinstance(end_user_id, str):
                    raise ValueError()
                UUID(end_user_id)
            except (ValueError, KeyError, IndexError, TypeError):
                raise GatewayUnavailable() from None
        DifyPassport.objects.update_or_create(
            grant=grant, identity=identity, session_digest=session_digest(request),
            token_digest=token_digest(token),
            defaults={"expires_at": min(request.session.get_expiry_date(), timezone.now() + timedelta(hours=8))},
        )
    return JsonResponse({"access_token": token})


def relay(upstream):
    def chunks():
        try:
            while chunk := upstream.read1(16384):
                yield chunk
        finally:
            upstream.close()

    response = StreamingHttpResponse(
        chunks(), status=upstream.status,
        content_type=upstream.headers.get("Content-Type", "application/octet-stream"),
    )
    # Close even when the client disconnects before iteration starts.
    response._resource_closers.append(upstream.close)
    response["X-Accel-Buffering"] = "no"
    # Deliberately do not relay cookies, redirects, cache or CORS headers.
    return response


@never_cache
@login_required
@require_safe
def chat_page(request, code):
    require_enabled()
    grant_for(request, code)
    try:
        return relay(open_upstream("/chat/" + code))
    except GatewayUnavailable:
        return HttpResponse("聊天服務暫時無法連線。", status=502)


@never_cache
@login_required
@require_safe
def static_asset(request, asset):
    require_enabled()
    if not re.fullmatch(r"[A-Za-z0-9_./@()+~-]+", asset) or ".." in asset:
        raise Http404
    try:
        return relay(open_upstream("/_next/static/" + asset))
    except GatewayUnavailable:
        return HttpResponse(status=502)


@never_cache
@csrf_exempt
def api(request, path):
    """Native Dify JS uses its own CSRF cookie. Require exact Origin for writes
    plus a passport registered to this Portal session, instead of bypassing CSRF
    for the rest of Portal. No Cookie/Authorization is forwarded upstream.
    """
    require_enabled()
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({"code": "unauthorized", "message": "請先登入 Portal。"}, status=401)
    if request.method not in {"GET", "POST", "PATCH", "DELETE"}:
        return HttpResponse(status=405)
    if request.method != "GET":
        if request.headers.get("Origin") != f"{request.scheme}://{request.get_host()}":
            raise PermissionDenied

    try:
        if path == "system-features" and request.method == "GET":
            return relay(open_upstream("/api/system-features"))
        code = request.headers.get("X-App-Code", "")
        query_code = request.GET.get("appCode") if path == "webapp/access-mode" else request.GET.get("app_code")
        if code and query_code and code != query_code:
            raise PermissionDenied
        code = code or query_code
        if not code or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", code):
            raise PermissionDenied
        grant = grant_for(request, code)
        if request.method == "GET" and path == "webapp/access-mode":
            # Use only the server-side Bot code, never a client appId override.
            return relay(open_upstream("/api/webapp/access-mode?" + urlencode({"appCode": code})))
        if request.method == "GET" and path == "passport":
            return issue_passport(request, grant)
        passport = passport_for(request, grant)
        if request.method == "GET" and path == "login/status":
            return JsonResponse({"logged_in": True, "app_logged_in": passport is not None})
        if passport is None:
            return JsonResponse({"code": "unauthorized", "message": "請重新開啟聊天。"}, status=401)
        if not any(re.fullmatch(pattern, path) and request.method in methods for pattern, methods in API_ROUTES):
            return JsonResponse({"message": "此功能尚未開放。"}, status=403)
        data = None
        headers = {"X-App-Code": code, "X-App-Passport": request.headers["X-App-Passport"]}
        if request.method != "GET":
            if ((request.body and request.content_type != "application/json")
                    or len(request.body) > 1024 * 1024):
                return HttpResponse(status=400)
            try:
                body = json.loads(request.body or b"{}")
            except ValueError:
                return HttpResponse(status=400)
            if not isinstance(body, dict):
                return HttpResponse(status=400)
            if path == "chat-messages":
                # First slice supports text-only bots. Never proxy file payloads.
                inputs = body.get("inputs", {})
                if (body.get("files") or not isinstance(inputs, dict)
                        or any(not isinstance(v, (str, int, float, bool, type(None))) for v in inputs.values())):
                    return JsonResponse({"message": "目前僅支援文字輸入。"}, status=400)
                body = {k: v for k, v in body.items() if k in {
                    "inputs", "query", "response_mode", "conversation_id", "parent_message_id", "auto_generate_name",
                }}
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        query = request.GET.copy()
        for key in ("user_id", "app_id", "appId", "appCode", "app_code"):
            query.pop(key, None)
        target = "/api/" + path + ("?" + query.urlencode() if query else "")
        return relay(open_upstream(target, method=request.method, data=data, headers=headers))
    except GatewayUnavailable:
        return JsonResponse({"message": "聊天服務暫時無法連線。"}, status=502)
