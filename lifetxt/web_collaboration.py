"""Per-principal authorization for the ordinary browser Web UI.

This adapter deliberately activates only when the selected named workspace
has collaboration enabled. It reuses Remote principals and browser sessions,
but keeps the standard-Web cookie separate so the Remote cookie remains
scoped to its existing API surface.
"""

from __future__ import unicode_literals

from urllib.parse import quote

from .collaboration import (
    collaboration_enabled,
    require_workspace_permission,
    selected_workspace_name,
)
from .remote_access import (
    RateLimiter,
    RemoteAccessError,
    authenticate_token,
    csrf_header,
    principal_registry,
    require_scope,
    require_https,
)
from .remote_sessions import (
    cookie_security,
    require_csrf,
    require_origin,
    session_payload,
    validate_session_configuration,
)

WEB_SESSION_COOKIE = "lifetxt_web_session"
WEB_LOGIN_PAGE = "/web-login"
WEB_LOGIN_PATH = "/api/web/v1/browser/login"
WEB_SESSION_PATH = "/api/web/v1/browser/session"
WEB_LOGOUT_PATH = "/api/web/v1/browser/logout"

_PAGE_PATHS = frozenset(("/", "/capture", "/planner", "/state"))
_STATIC_PAGE_PATHS = frozenset(
    (
        "/manifest.webmanifest",
        "/planner.webmanifest",
        "/state.webmanifest",
    )
)
_READ_ONLY_POST_PATHS = frozenset(
    (
        "/api/check-line",
        "/api/items/preview",
        "/api/items/parse",
        "/api/personal-context/preview",
        "/api/shorthand/parse",
        "/api/quick/resolve",
    )
)
_ADMIN_ONLY_PATHS = frozenset(
    (
        "/api/config",
        "/api/health",
        "/api/backup/status",
        "/api/transactions/preflight",
    )
)
_ADMIN_ONLY_PREFIXES = (
    "/api/git/",
    "/api/procedures",
    "/api/procedure-runs",
    "/procedures",
)

# These endpoints represent one server user's private context/session rather
# than shared workspace records. Until lifetxt has per-principal storage for
# these domains, workspace membership alone must not expose them to coworkers.
_PRIVATE_DOMAIN_PREFIXES = (
    "/api/personal-context",
    "/api/notifications",
    "/api/messages",
    "/api/timer",
    "/api/work-session",
)


def _remote(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def install_standard_web_collaboration(app, session_store, login_limiter=None):
    """Install the standard-Web login, session, CSRF, and workspace gate."""
    from fastapi import Body, Request
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

    config = app.state.config
    workspace = selected_workspace_name(config)
    if not collaboration_enabled(config, workspace):
        return
    if not _remote(config).get("enabled"):
        raise RuntimeError(
            "Workspace collaboration for the Web UI requires remote.enabled and "
            "configured Remote principals."
        )
    validate_session_configuration(config)
    app.state.standard_web_collaboration_enabled = True
    app.state.standard_web_session_store = session_store
    limiter = login_limiter or RateLimiter()
    principal_limiter = RateLimiter()

    def _expected_origin(request):
        from .web_transport import expected_origin

        value = expected_origin(request, app.state.config)
        if value is None:
            raise RemoteAccessError(
                "ORIGIN_FORBIDDEN", "The browser request origin is not allowed.", 403
            )
        return value

    def _current_membership(principal):
        return require_workspace_permission(
            app.state.config,
            principal,
            "read",
            selected_workspace_name(app.state.config),
        )

    def _resolve_cookie_session(request, check_membership=True):
        session_id = request.cookies.get(WEB_SESSION_COOKIE)
        session = session_store.resolve(session_id, app.state.config)
        principal_id = (session.get("principal") or {}).get("id")
        current = principal_registry(app.state.config).get(str(principal_id or ""))
        if (
            not current
            or current.get("disabled")
            or current.get("disclosure_mode") == "restricted-resource"
        ):
            session_store.revoke(session_id)
            raise RemoteAccessError(
                "SESSION_REVOKED", "The browser session is no longer authorized.", 401
            )
        session["principal"] = dict(current)
        membership = _current_membership(current) if check_membership else None
        return session, current, membership

    def _auth_error(request, exc):
        path = request.url.path
        if path in _PAGE_PATHS and exc.status == 401:
            target = quote(path, safe="/")
            return RedirectResponse(WEB_LOGIN_PAGE + "?next=" + target, status_code=303)
        if path in _PAGE_PATHS and exc.status == 403:
            return HTMLResponse(
                "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width\">"
                "<title>Access denied · life.txt</title><main><h1>Access denied</h1>"
                "<p>This account is not an active member of the selected workspace.</p>"
                "<a href=\"/web-login\">Sign in with another account</a></main></html>",
                status_code=403,
            )
        return JSONResponse(
            status_code=exc.status,
            content={"error": exc.code, "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"} if exc.status == 401 else None,
        )

    def _mark_private(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.get(WEB_LOGIN_PAGE, response_class=HTMLResponse)
    def web_login_page():
        if not app.state.standard_web_collaboration_enabled:
            return HTMLResponse("Not found", status_code=404)
        return _mark_private(
            HTMLResponse(
                """<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Sign in · life.txt</title><style>
body{font:16px system-ui,sans-serif;max-width:34rem;margin:10vh auto;padding:1rem;color:#27343d}
label,input,button{display:block;width:100%;box-sizing:border-box;margin:.65rem 0}
input,button{font:inherit;min-height:44px;padding:.65rem}button{cursor:pointer}
#error{color:#a00;min-height:1.5em}
</style></head><body><main><h1>Sign in to life.txt</h1>
<p>Use the token configured for your own principal. It is exchanged for a browser session and is not saved in this page.</p>
<form id=\"login\"><label for=\"token\">Principal token</label>
<input id=\"token\" name=\"token\" type=\"password\" autocomplete=\"current-password\" required>
<button type=\"submit\">Sign in</button></form><p id=\"error\" role=\"alert\"></p>
<script>
const form=document.getElementById('login'),token=document.getElementById('token'),error=document.getElementById('error');
if((navigator.language||'en').toLowerCase().startsWith('ja')){document.documentElement.lang='ja';document.title='サインイン · life.txt';document.querySelector('h1').textContent='life.txtにサインイン';document.querySelector('main>p').textContent='自分のprincipal tokenを入力してください。browser sessionへ交換され、このページには保存されません。';document.querySelector('label').textContent='Principal token';form.querySelector('button').textContent='サインイン';}
form.addEventListener('submit',async event=>{event.preventDefault();const value=token.value;token.value='';error.textContent='';
try{const response=await fetch('/api/web/v1/browser/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:value})});
const data=await response.json();if(!response.ok)throw new Error(data.message||'Sign-in failed.');
const wanted=new URLSearchParams(location.search).get('next')||'/';const allowed=['/','/planner','/capture','/state'];location.replace(allowed.includes(wanted)?wanted:'/');}
catch(problem){error.textContent=problem.message||'Sign-in failed.';}});
</script></main></body></html>""",
                status_code=200,
            )
        )

    @app.post(WEB_LOGIN_PATH)
    def web_browser_login(request: Request, payload=Body(default={} )):
        try:
            if not app.state.standard_web_collaboration_enabled:
                return JSONResponse({"error": "NOT_FOUND"}, status_code=404)
            host = request.client.host if request.client else None
            require_https(request.headers, host, app.state.config, request.url.scheme)
            limiter.check("standard-web-login:%s" % host, 10)
            require_origin(
                request.headers.get("origin"), _expected_origin(request), app.state.config
            )
            token = str((payload or {}).get("token") or "")
            if not token:
                raise RemoteAccessError("UNAUTHORIZED", "A principal token is required.", 401)
            principal, _method = authenticate_token(token, app.state.config)
            membership = _current_membership(principal)
            old_session = request.cookies.get(WEB_SESSION_COOKIE)
            if old_session:
                session_store.revoke(old_session)
            session = session_store.create(
                principal,
                "standard-web-browser-session",
                app.state.config,
                client_host=host,
                user_agent=request.headers.get("user-agent"),
            )
            response = JSONResponse(
                dict(
                    session_payload(session, include_csrf=True),
                    workspace=membership["workspace_name"],
                    role=membership["role"],
                    csrf_header=csrf_header(app.state.config),
                )
            )
            options = cookie_security(
                request,
                app.state.config,
                path="/",
                name=WEB_SESSION_COOKIE,
            )
            options.pop("key")
            response.set_cookie(WEB_SESSION_COOKIE, session["session_id"], **options)
            response.headers["Cache-Control"] = "no-store"
            return response
        except RemoteAccessError as exc:
            return JSONResponse(
                {"error": exc.code, "message": str(exc)},
                status_code=exc.status,
                headers={"WWW-Authenticate": "Bearer"} if exc.status == 401 else None,
            )

    @app.get(WEB_SESSION_PATH)
    def web_browser_session(request: Request):
        session = request.state.standard_web_session
        membership = request.state.standard_web_membership
        return _mark_private(
            JSONResponse(
                dict(
                    session_payload(session, include_csrf=True),
                    workspace=membership["workspace_name"],
                    role=membership["role"],
                    read_only=not membership["permissions"].get("write", False),
                    csrf_header=csrf_header(app.state.config),
                )
            )
        )

    @app.post(WEB_LOGOUT_PATH)
    def web_browser_logout(request: Request):
        session_id = request.cookies.get(WEB_SESSION_COOKIE)
        revoked = session_store.revoke(session_id)
        response = JSONResponse({"ok": True, "revoked": revoked})
        response.delete_cookie(WEB_SESSION_COOKIE, path="/")
        return _mark_private(response)

    @app.middleware("http")
    async def standard_web_guard(request: Request, call_next):
        if not app.state.standard_web_collaboration_enabled:
            return await call_next(request)

        path = request.url.path
        is_page = (
            path in _PAGE_PATHS
            or path in _STATIC_PAGE_PATHS
            or path.startswith("/assets/lifetxt-icon-")
        )
        is_api = path.startswith("/api/") or path == "/procedures" or path.startswith("/procedures/")
        if path == "/remote" or path.startswith("/api/remote/"):
            return await call_next(request)

        try:
            host = request.client.host if request.client else None
            require_https(request.headers, host, app.state.config, request.url.scheme)
            if path == WEB_LOGIN_PAGE or path == WEB_LOGIN_PATH:
                return _mark_private(await call_next(request))
            if path in (WEB_SESSION_PATH, WEB_LOGOUT_PATH):
                session, principal, membership = _resolve_cookie_session(
                    request, check_membership=path == WEB_SESSION_PATH
                )
                if path == WEB_LOGOUT_PATH:
                    require_csrf(
                        session,
                        request.headers,
                        request.method,
                        request.headers.get("origin"),
                        _expected_origin(request),
                        app.state.config,
                    )
                request.state.standard_web_session = session
                request.state.standard_web_principal = principal
                request.state.standard_web_membership = membership
                return _mark_private(await call_next(request))

            if is_page:
                session, principal, membership = _resolve_cookie_session(request)
                request.state.standard_web_session = session
            else:
                authorization = request.headers.get("authorization", "")
                if authorization:
                    if not authorization.startswith("Bearer "):
                        raise RemoteAccessError(
                            "UNAUTHORIZED", "A valid principal Bearer token is required.", 401
                        )
                    principal, _method = authenticate_token(
                        authorization[7:], app.state.config
                    )
                    session = None
                    membership = _current_membership(principal)
                else:
                    session, principal, membership = _resolve_cookie_session(request)
                    require_csrf(
                        session,
                        request.headers,
                        request.method,
                        request.headers.get("origin"),
                        _expected_origin(request),
                        app.state.config,
                    )
                request.state.standard_web_session = session

            request.state.standard_web_principal = principal
            request.state.standard_web_membership = membership
            request.state.standard_web_auth_bypasses_shared_api_token = True
            principal_limiter.check(
                "standard-web:%s" % principal["id"],
                int(_remote(app.state.config).get("rate_limit_per_minute") or 120),
            )

            if any(path == prefix or path.startswith(prefix + "/") for prefix in _PRIVATE_DOMAIN_PREFIXES):
                raise RemoteAccessError(
                    "WORKSPACE_DOMAIN_NOT_SHARED",
                    "This personal server domain is not available in workspace collaboration.",
                    403,
                )

            if path in _ADMIN_ONLY_PATHS or any(path.startswith(prefix) for prefix in _ADMIN_ONLY_PREFIXES):
                require_scope(principal, "admin")
            if path == "/api/transactions/preflight" and request.query_params.get("create", "").lower() in ("1", "true", "yes"):
                if session is not None:
                    require_csrf(
                        session,
                        request.headers,
                        "POST",
                        request.headers.get("origin"),
                        _expected_origin(request),
                        app.state.config,
                    )
                require_scope(principal, "admin")

            if is_api and path not in (WEB_LOGIN_PATH, WEB_SESSION_PATH, WEB_LOGOUT_PATH):
                method = request.method.upper()
                operation = "read" if method in ("GET", "HEAD", "OPTIONS") or path in _READ_ONLY_POST_PATHS else "write"
                membership = require_workspace_permission(
                    app.state.config,
                    principal,
                    operation,
                    selected_workspace_name(app.state.config),
                )
                request.state.standard_web_membership = membership
                request.state.standard_web_auth_bypasses_shared_api_token = True

            from .web_actor import activate_web_actor, reset_web_actor

            actor_token = activate_web_actor(principal.get("id"))
            try:
                response = await call_next(request)
            finally:
                reset_web_actor(actor_token)
            return _mark_private(response)
        except RemoteAccessError as exc:
            return _mark_private(_auth_error(request, exc))

