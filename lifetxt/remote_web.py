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
from .remote_historical import read_historical_resource
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
from .clock_skew import ClockSkewError, clock_audit_evidence, require_acceptable_clock
from .remote_contracts_v6 import remote_client_time_header, remote_clock_required
from .remote_backup_operations import BackupRunStore

_INSTALLED = False
_LOGIN_PATH = "/api/remote/v1/browser/login"
_BROWSER_SESSION_PATH = "/api/remote/v1/browser/session"
_LOGOUT_PATH = "/api/remote/v1/browser/logout"
_BACKUP_RUN_PATH = "/api/remote/v1/operations/backup-runs"

# Every mutating Remote v1 route is classified here. Operational/session
# controls do not mutate authoritative life.txt data and therefore must not
# enter the Web revision migration contract. Authoritative ticket mutations
# keep their own exact If-Match/CAS contract in remote_ticket_writes.py.
REMOTE_MUTATING_ROUTE_REVISION_CLASSIFICATION = {
    _LOGIN_PATH: "operational",
    _LOGOUT_PATH: "operational",
    "/api/remote/v1/write-check": "operational",
    _BACKUP_RUN_PATH: "operational",
    "/api/remote/v1/ticket-mutations": "authoritative",
}
_REMOTE_NON_REVISION_WRITE_PATHS = frozenset(
    path
    for path, classification in REMOTE_MUTATING_ROUTE_REVISION_CLASSIFICATION.items()
    if classification == "operational"
)
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
body{font-family:system-ui,sans-serif;max-width:980px;margin:3rem auto;padding:0 1rem;color:#202124}fieldset{border:1px solid #bbb;border-radius:.5rem;padding:1rem}input,button{font:inherit;padding:.55rem}.row{display:flex;gap:.5rem;flex-wrap:wrap}pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem;border-radius:.5rem;min-height:8rem}.muted{color:#666}.hidden{display:none}.operation{margin:1rem 0;padding:1rem;border:1px solid #bbb;border-radius:.5rem}.operation button{min-height:44px}@media(max-width:480px){body{margin:1rem auto}.row button{width:100%%}}</style></head>
<body><h1>lifetxt Remote Safe Mode</h1><p class="muted">Authenticated Remote session. Tokens are exchanged once and are not stored by this page.</p>
<fieldset id="login"><legend>Sign in</legend><div class="row"><input id="token" type="password" autocomplete="current-password" placeholder="Bearer token"><button id="sign-in">Sign in</button></div></fieldset>
<div id="session" class="hidden"><div class="row"><button id="refresh">Refresh snapshot</button><button id="logout">Sign out</button></div><p id="identity"></p><section id="backup-operation" class="operation hidden" aria-labelledby="backup-title"><h2 id="backup-title">Backup</h2><p>A run may create a local backup, upload it off-host, and prune backups according to configured retention.</p><button id="run-backup">Run backup now</button><p id="backup-status" role="status" aria-live="polite"></p></section><pre id="output"></pre></div>
<script nonce="%s">
(()=>{let csrf=null,poll=null,operationKey=null;const version={'X-Lifetxt-Remote-Version':'2'};const $=id=>document.getElementById(id);
async function json(url,opt={}){opt.headers=Object.assign({'Accept':'application/json'},version,opt.headers||{});const r=await fetch(url,opt);const v=await r.json().catch(()=>({error:'INVALID_RESPONSE'}));if(!r.ok)throw new Error(v.error+': '+(v.message||r.status));return v}
function renderOperation(v){$('backup-status').textContent='Status: '+v.status+'; local: '+v.local.status+'; remote: '+v.remote.status;if(v.status==='admitted'||v.status==='running'){poll=setTimeout(()=>json(v.status_url).then(renderOperation).catch(showBackupError),1000)}else{const wait=Math.max(0,Number(v.cooldown_seconds)||0);$('backup-status').textContent+='; next run available after '+wait+' seconds';setTimeout(()=>{operationKey=null;$('run-backup').disabled=false;$('backup-status').textContent='Ready'},wait*1000)}}
function showBackupError(e){$('backup-status').textContent=String(e);$('run-backup').disabled=false}
async function load(){const [v,s,c]=await Promise.all([json('/api/remote/v1/snapshot'),json('/api/remote/v1/session'),json('/api/remote/v1/capabilities')]);$('identity').textContent=s.principal.id+' ('+s.principal.role+')';$('output').textContent=JSON.stringify(v,null,2);const op=c.operations&&c.operations.backup_run;const allowed=s.principal.scopes.includes('backup:run')&&op&&op.available;$('backup-operation').classList.toggle('hidden',!allowed);$('login').classList.add('hidden');$('session').classList.remove('hidden')}
async function resume(){try{const s=await json('/api/remote/v1/browser/session');csrf=s.csrf_token;$('identity').textContent=s.principal.id+' ('+s.principal.role+')';await load()}catch(_){}}
$('sign-in').onclick=async()=>{try{const token=$('token').value;const s=await json('/api/remote/v1/browser/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});$('token').value='';csrf=s.csrf_token;$('identity').textContent=s.principal.id+' ('+s.principal.role+')';await load()}catch(e){$('output').textContent=String(e)}};
$('refresh').onclick=()=>load().catch(e=>$('output').textContent=String(e));
$('run-backup').onclick=async()=>{if(!operationKey&&!confirm('Run the configured backup now? This may create locally, upload off-host, and prune according to retention.'))return;$('run-backup').disabled=true;$('backup-status').textContent='Submitting…';operationKey=operationKey||(crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random());try{const v=await json('/api/remote/v1/operations/backup-runs',{method:'POST',headers:{'X-CSRF-Token':csrf,'Idempotency-Key':operationKey,'Origin':location.origin}});renderOperation(v)}catch(e){showBackupError(e)}};
$('logout').onclick=async()=>{try{await json('/api/remote/v1/browser/logout',{method:'POST',headers:{'X-CSRF-Token':csrf,'Origin':location.origin}})}finally{if(poll)clearTimeout(poll);csrf=null;operationKey=null;$('backup-operation').classList.add('hidden');$('session').classList.add('hidden');$('login').classList.remove('hidden');$('output').textContent=''}};
resume();})();</script></body></html>""" % (html.escape(nonce), html.escape(nonce))


def install_remote_web():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import surface_runtime, webapp

    surface_runtime._WEB_NO_REVISION_PATHS = frozenset(
        set(surface_runtime._WEB_NO_REVISION_PATHS)
        | set(_REMOTE_NON_REVISION_WRITE_PATHS)
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
        backup_run_store = BackupRunStore()
        app.state.remote_backup_run_store = backup_run_store

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
            clock_evidence = None
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

                    if (
                        not app.state.read_only
                        and remote_clock_required(app.state.config)
                        and request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
                    ):
                        header = remote_client_time_header(app.state.config)
                        value = request.headers.get(header)
                        if not value:
                            clock_evidence = clock_audit_evidence(
                                value, app.state.config, outcome="CLIENT_TIME_REQUIRED"
                            )
                            raise RemoteAccessError(
                                "CLIENT_TIME_REQUIRED",
                                "%s is required for remote writes." % header,
                                428,
                            )
                        try:
                            clock = require_acceptable_clock(
                                value, config=app.state.config
                            )
                        except (ClockSkewError, ValueError) as exc:
                            clock_evidence = clock_audit_evidence(
                                value, app.state.config, outcome="CLOCK_SKEW"
                            )
                            raise RemoteAccessError("CLOCK_SKEW", str(exc), 409)
                        clock_evidence = clock_audit_evidence(
                            value, app.state.config, clock, "allowed"
                        )
                        request.state.remote_clock = clock

                response = await call_next(request)
            