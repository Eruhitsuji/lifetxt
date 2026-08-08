"""FastAPI surface for authenticated Remote Safe Mode."""

from __future__ import unicode_literals

import html
import json
import os
import secrets
from collections import OrderedDict

from .remote_access import (
    REMOTE_PROTOCOL_CURRENT,
    RateLimiter,
    RemoteAccessError,
    append_audit,
    audit_event,
    authenticate,
    authenticate_token,
    capability,
    error_payload,
    negotiate_protocol,
    principal_registry,
    protocol_response_headers,
    public_principal,
    redact_remote_value,
    request_id,
    require_exact_revision,
    require_https,
    require_scope,
    trusted_peer,
    validate_remote_storage,
)
from .remote_backend import read_resource, resource_catalog, snapshot, source_revision
from .remote_sessions import (
    BrowserSessionStore,
    browser_enabled,
    cookie_name,
    cookie_security,
    require_csrf,
    require_origin,
    session_payload,
    validate_session_configuration,
    validate_single_worker_deployment,
)

_INSTALLED = False
_LOGIN_PATH = "/api/remote/v1/browser/login"
_BROWSER_SESSION_PATH = "/api/remote/v1/browser/session"
_LOGOUT_PATH = "/api/remote/v1/browser/logout"
_REMOTE_PREFIX = "/api/remote/v1/"


def _remote(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def _expected_origin(request, config):
    host = request.headers.get("host") or request.url.netloc
    scheme = request.url.scheme
    client_host = request.client.host if request.client else None
    if trusted_peer(config, client_host):
        forwarded = request.headers.get("x-forwarded-proto")
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded:
            scheme = forwarded.split(",")[0].strip()
        if forwarded_host:
            host = forwarded_host.split(",")[0].strip()
    return "%s://%s" % (scheme, host)


def _audit_safely(config, event):
    try:
        append_audit(config, event)
    except Exception:
        # Audit storage hardening remains a separate roadmap item. Read access
        # must not leak a local storage failure or crash the server response.
        return False
    return True


def _require_v2(request):
    if int(getattr(request.state, "remote_protocol", 1)) < 2:
        raise RemoteAccessError(
            "REMOTE_VERSION_REQUIRED",
            "This route requires Remote protocol version 2.",
            426,
            {"required": 2},
        )


def _remote_page(nonce):
    # The token exists only in the password input until the login request is
    # complete. It is never placed in localStorage/sessionStorage/cookies.
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>lifetxt Remote Safe Mode</title>
<style nonce="%s">
body{font-family:system-ui,sans-serif;max-width:980px;margin:3rem auto;padding:0 1rem;color:#202124}fieldset{border:1px solid #bbb;border-radius:.5rem;padding:1rem}input,button{font:inherit;padding:.55rem}.row{display:flex;gap:.5rem;flex-wrap:wrap}pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem;border-radius:.5rem;min-height:8rem}.muted{color:#666}.hidden{display:none}</style></head>
<body><h1>lifetxt Remote Safe Mode</h1><p class="muted">Authenticated, read-only browser session. Tokens are exchanged once and are not stored by this page.</p>
<fieldset id="login"><legend>Sign in</legend><div class="row"><input id="token" type="password" autocomplete="current-password" placeholder="Bearer token"><button id="sign-in">Sign in</button></div></fieldset>
<div id="session" class="hidden"><div class="row"><button id="refresh">Refresh snapshot</button><button id="logout">Sign out</button></div><p id="identity"></p><pre id="output"></pre></div>
<script nonce="%s">
(()=>{let csrf=null;const version={'X-Lifetxt-Remote-Version':'2'};const $=id=>document.getElementById(id);
async function json(url,opt={}){opt.headers=Object.assign({'Accept':'application/json'},version,opt.headers||{});const r=await fetch(url,opt);const v=await r.json().catch(()=>({error:'INVALID_RESPONSE'}));if(!r.ok)throw new Error(v.error+': '+(v.message||r.status));return v}
async function load(){const v=await json('/api/remote/v1/snapshot');$('identity').textContent='Signed in';$('output').textContent=JSON.stringify(v,null,2);$('login').classList.add('hidden');$('session').classList.remove('hidden')}
async function resume(){try{const s=await json('/api/remote/v1/browser/session');csrf=s.csrf_token;$('identity').textContent=s.principal.id+' ('+s.principal.role+')';await load()}catch(_){}}
$('sign-in').onclick=async()=>{try{const token=$('token').value;const s=await json('/api/remote/v1/browser/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});$('token').value='';csrf=s.csrf_token;$('identity').textContent=s.principal.id+' ('+s.principal.role+')';await load()}catch(e){$('output').textContent=String(e)}};
$('refresh').onclick=()=>load().catch(e=>$('output').textContent=String(e));
$('logout').onclick=async()=>{try{await json('/api/remote/v1/browser/logout',{method:'POST',headers:{'X-CSRF-Token':csrf}})}finally{csrf=null;$('session').classList.add('hidden');$('login').classList.remove('hidden');$('output').textContent=''}};
resume();})();</script></body></html>""" % (html.escape(nonce), html.escape(nonce))


def install_remote_web():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import surface_runtime, webapp

    surface_runtime._WEB_NO_REVISION_PATHS = frozenset(
        set(surface_runtime._WEB_NO_REVISION_PATHS)
        | {"/api/remote/v1/write-check", _LOGIN_PATH, _LOGOUT_PATH}
    )
    original = webapp.create_app

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        from fastapi import Body, Query, Request
        from fastapi.responses import HTMLResponse, JSONResponse

        app = original(
            paths=paths, writable_path=writable_path, config=config, read_only=read_only
        )
        app.state.remote_enabled = bool(_remote(app.state.config).get("enabled"))
        if app.state.remote_enabled:
            validate_session_configuration(app.state.config)
            validate_single_worker_deployment(app.state.config)
            validate_remote_storage(app.state.config, app.state.paths, writable_path)
        app.state.remote_session_store = BrowserSessionStore()
        principal_limiter = RateLimiter()
        login_limiter = RateLimiter()

        @app.middleware("http")
        async def remote_guard(request: Request, call_next):
            path = request.url.path
            is_api = path.startswith(_REMOTE_PREFIX)
            is_page = path == "/remote"
            if not is_api and not is_page:
                return await call_next(request)

            rid = request_id(request.headers)
            host = request.client.host if request.client else None
            negotiated = 1
            principal = None
            auth_method = None
            session = None
            try:
                require_https(
                    request.headers, host, app.state.config, request.url.scheme
                )
                if is_page:
                    if not browser_enabled(app.state.config):
                        raise RemoteAccessError(
                            "REMOTE_BROWSER_DISABLED",
                            "Remote browser UI is disabled.",
                            404,
                        )
                    response = await call_next(request)
                    response.headers["Cache-Control"] = "no-store"
                    response.headers["X-Frame-Options"] = "DENY"
                    return response

                negotiated = negotiate_protocol(request.headers)
                request.state.remote_protocol = negotiated
                request.state.remote_request_id = rid

                if path == _LOGIN_PATH:
                    if not browser_enabled(app.state.config):
                        raise RemoteAccessError(
                            "REMOTE_BROWSER_DISABLED",
                            "Remote browser UI is disabled.",
                            404,
                        )
                    login_limiter.check(
                        "login:%s" % host,
                        int(
                            _remote(app.state.config).get(
                                "browser_login_rate_limit_per_minute"
                            )
                            or 10
                        ),
                    )
                    require_origin(
                        request.headers.get("origin"),
                        _expected_origin(request, app.state.config),
                        app.state.config,
                    )
                else:
                    remote = _remote(app.state.config)
                    proxy_header = str(
                        remote.get("proxy_principal_header") or "X-Lifetxt-Principal"
                    )
                    has_explicit_auth = bool(
                        request.headers.get("authorization")
                        or request.headers.get(proxy_header)
                    )
                    session_id = request.cookies.get(cookie_name(app.state.config))
                    if has_explicit_auth:
                        principal, auth_method = authenticate(
                            request.headers, host, app.state.config
                        )
                    elif session_id:
                        session = app.state.remote_session_store.resolve(
                            session_id, app.state.config
                        )
                        current = principal_registry(app.state.config).get(
                            session.get("principal", {}).get("id")
                        )
                        if not current or current.get("disabled"):
                            app.state.remote_session_store.revoke(session_id)
                            raise RemoteAccessError(
                                "SESSION_REVOKED",
                                "The browser session principal no longer exists or is disabled.",
                                401,
                            )
                        principal = current
                        auth_method = "browser-session"
                        session["principal"] = dict(current)
                        require_csrf(
                            session,
                            request.headers,
                            request.method,
                            request.headers.get("origin"),
                            _expected_origin(request, app.state.config),
                            app.state.config,
                        )
                    else:
                        principal, auth_method = authenticate(
                            request.headers, host, app.state.config
                        )

                    principal_limiter.check(
                        principal["id"], int(remote.get("rate_limit_per_minute") or 120)
                    )
                    request.state.remote_principal = principal
                    request.state.remote_auth_method = auth_method
                    request.state.remote_session = session

                response = await call_next(request)
                for key, value in protocol_response_headers(
                    app.state.config, negotiated
                ).items():
                    response.headers[key] = value
                response.headers["X-Request-ID"] = rid
                audit_principal = getattr(request.state, "remote_principal", principal)
                _audit_safely(
                    app.state.config,
                    audit_event(
                        audit_principal,
                        request.method + " " + path,
                        response.status_code,
                        rid,
                        host,
                        {"authentication": auth_method, "protocol": negotiated},
                    ),
                )
                return response
            except RemoteAccessError as exc:
                _audit_safely(
                    app.state.config,
                    audit_event(
                        principal,
                        request.method + " " + path,
                        exc.code,
                        rid,
                        host,
                        {"protocol": negotiated},
                    ),
                )
                headers = {"X-Request-ID": rid}
                error_version = (
                    exc.detail.get("current", negotiated) if exc.detail else negotiated
                )
                if error_version not in (1, REMOTE_PROTOCOL_CURRENT):
                    error_version = REMOTE_PROTOCOL_CURRENT
                headers.update(
                    protocol_response_headers(app.state.config, error_version)
                )
                if exc.status == 401:
                    headers["WWW-Authenticate"] = "Bearer"
                return JSONResponse(
                    status_code=exc.status,
                    content=error_payload(exc, rid),
                    headers=headers,
                )

        def principal(request):
            return request.state.remote_principal

        @app.get("/remote", response_class=HTMLResponse)
        def remote_page():
            nonce = secrets.token_urlsafe(18)
            response = HTMLResponse(_remote_page(nonce))
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'nonce-%s'; style-src 'nonce-%s'; "
                "connect-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
            ) % (nonce, nonce)
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        @app.get("/api/remote/v1/capabilities")
        def remote_capabilities(request: Request):
            require_scope(principal(request), "read")
            return capability(app.state.config, request.state.remote_protocol)

        @app.get("/api/remote/v1/session")
        def remote_session(request: Request):
            current = principal(request)
            require_scope(current, "read")
            result = OrderedDict(
                (
                    ("schema", "remote-session-v1.schema.json"),
                    ("principal", public_principal(current)),
                    ("authentication", request.state.remote_auth_method),
                    ("request_id", request.state.remote_request_id),
                    ("protocol_version", request.state.remote_protocol),
                )
            )
            if request.state.remote_session:
                result["browser_session"] = session_payload(
                    request.state.remote_session, include_csrf=False
                )
            return result

        @app.get("/api/remote/v1/snapshot")
        def remote_snapshot(request: Request):
            current = principal(request)
            require_scope(current, "read")
            value = snapshot(app.state.paths, app.state.config, current)
            value["read_only"] = True
            return value

        @app.get("/api/remote/v1/tickets")
        def remote_tickets(request: Request):
            current = principal(request)
            require_scope(current, "read")
            value = read_resource(
                "tickets",
                app.state.paths,
                app.state.config,
                current,
                request.query_params,
            )
            return {
                "revision": value["revision"],
                "tickets": value["data"].get("tickets", []),
                "diagnostics": value["diagnostics"],
            }

        @app.get("/api/remote/v1/projects")
        def remote_projects(request: Request):
            current = principal(request)
            require_scope(current, "read")
            value = read_resource(
                "projects",
                app.state.paths,
                app.state.config,
                current,
                request.query_params,
            )
            return {
                "revision": value["revision"],
                "projects": value["data"].get("projects", []),
                "summary": value["data"].get("summary", {}),
            }

        @app.get("/api/remote/v1/resources")
        def remote_resources(request: Request):
            _require_v2(request)
            current = principal(request)
            require_scope(current, "read")
            return {
                "resources": resource_catalog(),
                "revision": source_revision(app.state.paths),
            }

        @app.get("/api/remote/v1/resources/{resource_name}")
        def remote_resource(resource_name: str, request: Request):
            _require_v2(request)
            current = principal(request)
            require_scope(current, "read")
            return read_resource(
                resource_name,
                app.state.paths,
                app.state.config,
                current,
                request.query_params,
            )

        @app.get("/api/remote/v1/diagnostics")
        def remote_diagnostics(request: Request):
            _require_v2(request)
            current = principal(request)
            require_scope(current, "read")
            remote = _remote(app.state.config)
            checks = [
                {"name": "remote-enabled", "ok": bool(remote.get("enabled"))},
                {"name": "https-policy", "ok": True},
                {
                    "name": "principal-registry",
                    "ok": bool(principal_registry(app.state.config)),
                },
                {
                    "name": "source-count",
                    "ok": bool(app.state.paths),
                    "value": len(app.state.paths),
                },
                {
                    "name": "browser-session",
                    "ok": True,
                    "enabled": browser_enabled(app.state.config),
                    "active": app.state.remote_session_store.count(),
                },
                {
                    "name": "authoritative-remote-writes",
                    "ok": False,
                    "admission_only": True,
                },
            ]
            warnings = []
            if remote.get("browser_ui") and not remote.get("allowed_origins"):
                warnings.append(
                    "Browser sessions accept only the computed same origin; configure allowed_origins for additional origins."
                )
            if not remote.get("audit_log"):
                warnings.append("Remote audit_log is not configured.")
            return {
                "schema": "remote-diagnostics-v1.schema.json",
                "ok": all(
                    row["ok"]
                    for row in checks
                    if row["name"] != "authoritative-remote-writes"
                ),
                "protocol": {
                    "negotiated": request.state.remote_protocol,
                    "current": REMOTE_PROTOCOL_CURRENT,
                },
                "checks": checks,
                "warnings": warnings,
                "request_id": request.state.remote_request_id,
            }

        @app.post(_LOGIN_PATH)
        def browser_login(request: Request, payload=Body(default={})):
            _require_v2(request)
            token = str((payload or {}).get("token") or "")
            current, _method = authenticate_token(token, app.state.config)
            old_session_id = request.cookies.get(cookie_name(app.state.config))
            if old_session_id:
                app.state.remote_session_store.revoke(old_session_id)
            session = app.state.remote_session_store.create(
                current,
                "browser-session",
                app.state.config,
                client_host=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            request.state.remote_principal = current
            request.state.remote_auth_method = "browser-login"
            request.state.remote_session = session
            response = JSONResponse(session_payload(session, include_csrf=True))
            options = cookie_security(request, app.state.config)
            key = options.pop("key")
            response.set_cookie(key, session["session_id"], **options)
            response.headers["Cache-Control"] = "no-store"
            return response

        @app.get(_BROWSER_SESSION_PATH)
        def browser_session(request: Request):
            _require_v2(request)
            if not request.state.remote_session:
                raise RemoteAccessError(
                    "BROWSER_SESSION_REQUIRED",
                    "This endpoint requires browser-session authentication.",
                    401,
                )
            require_scope(principal(request), "read")
            response = JSONResponse(
                session_payload(request.state.remote_session, include_csrf=True)
            )
            response.headers["Cache-Control"] = "no-store"
            return response

        @app.post(_LOGOUT_PATH)
        def browser_logout(request: Request):
            _require_v2(request)
            session_id = request.cookies.get(cookie_name(app.state.config))
            revoked = app.state.remote_session_store.revoke(session_id)
            response = JSONResponse({"ok": True, "revoked": revoked})
            response.delete_cookie(cookie_name(app.state.config), path="/api/remote/")
            response.headers["Cache-Control"] = "no-store"
            return response

        @app.post("/api/remote/v1/write-check")
        def remote_write_check(request: Request, payload=Body(default={})):
            current_principal = principal(request)
            require_scope(current_principal, "write")
            current_revision = source_revision(app.state.paths)
            require_exact_revision(request.headers, current_revision)
            return {
                "ok": True,
                "revision": current_revision,
                "operation": str((payload or {}).get("operation") or "write-check"),
                "principal": current_principal["id"],
                "authoritative_mutation": False,
            }

        @app.get("/api/remote/v1/audit")
        def remote_audit(request: Request, limit: int = Query(200, ge=1, le=1000)):
            current = principal(request)
            require_scope(current, "audit")
            path = _remote(app.state.config).get("audit_log")
            rows = []
            if path and os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    for line in handle.readlines()[-limit:]:
                        try:
                            rows.append(redact_remote_value(json.loads(line)))
                        except ValueError:
                            pass
            return {"events": rows, "count": len(rows)}

        return app

    webapp.create_app = create_app
    _INSTALLED = True
