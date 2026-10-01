"""FastAPI surface for authenticated Remote Safe Mode."""

from __future__ import unicode_literals

import html
import hashlib
import json
import os
import secrets
from collections import OrderedDict

from .remote_access import (
    REMOTE_CAPABILITY_REVISION_HEADER,
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
_WORKSPACE_MEMBERS_PATH = "/api/remote/v1/workspace/members"

# Every mutating Remote v1 route is classified here. Operational/session
# controls do not mutate authoritative life.txt data and therefore must not
# enter the Web revision migration contract. Workspace membership writes use
# configuration CAS; ticket/item mutations keep exact If-Match/CAS contracts.
REMOTE_MUTATING_ROUTE_REVISION_CLASSIFICATION = {
    _LOGIN_PATH: "operational",
    _LOGOUT_PATH: "operational",
    "/api/remote/v1/write-check": "operational",
    _BACKUP_RUN_PATH: "operational",
    _WORKSPACE_MEMBERS_PATH: "config-cas",
    "/api/remote/v1/ticket-mutations": "authoritative",
    "/api/remote/v1/item-mutations": "authoritative",
}
_REMOTE_NON_REVISION_WRITE_PATHS = frozenset(
    path
    for path, classification in REMOTE_MUTATING_ROUTE_REVISION_CLASSIFICATION.items()
    if classification in ("operational", "config-cas")
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
    # The token exists only in the password input until login completes.
    template = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>lifetxt Remote Safe Mode</title>
<style nonce="__NONCE__">
body{font-family:system-ui,sans-serif;max-width:980px;margin:3rem auto;padding:0 1rem;color:#202124}fieldset{border:1px solid #bbb;border-radius:.5rem;padding:1rem}input,button,select{font:inherit;padding:.55rem;max-width:100%}.row{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center}.hidden{display:none}.muted{color:#555}.operation,.panel{margin:1rem 0;padding:1rem;border:1px solid #bbb;border-radius:.5rem}.operation button,.panel button,.panel select{min-height:44px}.member-list{display:grid;gap:.65rem}.member-card{display:flex;align-items:center;justify-content:space-between;gap:.75rem;flex-wrap:wrap;border:1px solid #ccc;border-radius:.4rem;padding:.75rem;min-width:0}.member-identity{min-width:0;overflow-wrap:anywhere}.member-controls{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}.member-controls button,.member-controls select{min-height:44px}form{display:flex;gap:.5rem;align-items:end;flex-wrap:wrap}label{display:grid;gap:.25rem}input,select{min-width:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;padding:1rem;border-radius:.5rem;min-height:8rem}.activity-list{padding-inline-start:1.5rem}.activity-list li{overflow-wrap:anywhere;margin:.3rem 0}:focus-visible{outline:3px solid #175cd3;outline-offset:2px}@media(max-width:560px){body{margin:1rem auto}.row button,form button{width:100%}.member-card{align-items:stretch}.member-controls{width:100%}.member-controls select,.member-controls button{flex:1}}
</style></head><body>
<h1>lifetxt Remote Safe Mode</h1><p class="muted" id="intro">Authenticated Remote session. Tokens are exchanged once and are not stored by this page.</p>
<fieldset id="login"><legend id="login-title">Sign in</legend><div class="row"><label><span id="token-label">Bearer token</span><input id="token" type="password" autocomplete="current-password"></label><button id="sign-in" type="button">Sign in</button></div></fieldset>
<div id="access-denied" class="panel hidden" role="alert"><p id="access-denied-message"></p><button id="denied-sign-out" type="button">Sign out</button></div>
<main id="session" class="hidden"><div class="row"><button id="refresh" type="button">Refresh snapshot</button><button id="notes-refresh" type="button">Ordinary Notes</button><button id="notes-next" type="button" hidden>Next Notes page</button><button id="logout" type="button">Sign out</button></div><p id="identity" role="status" aria-live="polite"></p>
<section id="members-section" class="panel hidden" aria-labelledby="members-title"><div class="row"><h2 id="members-title">Workspace members</h2><button id="members-refresh" type="button">Refresh member list</button></div><p id="member-status" role="status" aria-live="polite"></p><form id="member-add-form"><label><span id="principal-label">Principal ID</span><input id="new-principal" required autocomplete="off"></label><label><span id="role-label">Role</span><select id="new-role"><option value="owner">Owner</option><option value="editor">Editor</option><option value="viewer">Viewer</option></select></label><button id="member-add" type="submit">Add member</button></form><div id="member-list" class="member-list" aria-live="polite"></div></section>
<section id="activity-section" class="panel hidden" aria-labelledby="activity-title"><h2 id="activity-title">Recent activity</h2><p id="activity-note" class="muted">Authenticated Native History actor IDs are shown when available.</p><ol id="activity-list" class="activity-list"></ol></section>
<section id="backup-operation" class="operation hidden" aria-labelledby="backup-title"><h2 id="backup-title">Backup</h2><p id="backup-description">A run may create a local backup, upload it off-host, and prune backups according to configured retention.</p><button id="run-backup" type="button">Run backup now</button><p id="backup-status" role="status" aria-live="polite"></p></section><pre id="output"></pre></main>
<script nonce="__NONCE__">
(()=>{let csrf=null,poll=null,operationKey=null,workspaceName=null,configRevision=null,notesRevision=null,notesGeneration=0,locale=(navigator.language||'').toLowerCase().startsWith('ja')?'ja':'en';const version={'X-Lifetxt-Remote-Version':'2'};const $=id=>document.getElementById(id);
const strings={en:{intro:'Authenticated Remote session. Tokens are exchanged once and are not stored by this page.',signIn:'Sign in',token:'Bearer token',workspace:'Workspace',signedIn:'Signed in',role:'Role',owner:'Owner',editor:'Editor',viewer:'Viewer',readOnly:'Read-only access',members:'Workspace members',principal:'Principal ID',add:'Add member',remove:'Remove',notes:'Ordinary Notes',notesNext:'Next Notes page',refresh:'Refresh snapshot',signOut:'Sign out',noMembers:'No members are configured.',loadMembers:'Refresh member list',accessDenied:'Access denied to the selected workspace.',memberDenied:'You do not have permission to manage workspace members.',stale:'Membership changed elsewhere. The list was refreshed; review it before making another change.',lastOwner:'The last active owner cannot be removed or demoted.',unknown:'That principal is not configured on the server.',insufficient:'This action is not permitted.',confirmRemove:'Remove this workspace member?',confirmOwner:'Change or remove this owner? The server will reject this if it would leave no active owner.',added:'Member added.',changed:'Member role changed.',removed:'Member removed.',activity:'Recent activity',activityNote:'Authenticated Native History actor IDs are shown when available.',actorUnknown:'Unknown actor',noActivity:'No native history actor events are available.',disabled:'Disabled',backup:'Backup',backupRun:'Run backup now'},ja:{intro:'認証済みのRemote sessionです。tokenはサインイン時に一度だけ送信され、このページには保存されません。',signIn:'サインイン',token:'Bearer token',workspace:'ワークスペース',signedIn:'ログイン中',role:'ロール',owner:'Owner（管理者）',editor:'Editor（編集者）',viewer:'Viewer（閲覧者）',readOnly:'閲覧のみ',members:'ワークスペースメンバー',principal:'Principal ID',add:'メンバーを追加',remove:'削除',notes:'通常のメモ',notesNext:'次のメモページ',refresh:'snapshotを更新',signOut:'サインアウト',noMembers:'メンバーが設定されていません。',loadMembers:'メンバー一覧を更新',accessDenied:'選択中のワークスペースへのアクセスが拒否されました。',memberDenied:'メンバー管理の権限がありません。',stale:'別の変更が先に反映されました。一覧を更新しました。内容を確認してから再操作してください。',lastOwner:'最後の有効なOwnerは削除・降格できません。',unknown:'このPrincipal IDはサーバーに設定されていません。',insufficient:'この操作は許可されていません。',confirmRemove:'このワークスペースメンバーを削除しますか？',confirmOwner:'Ownerを変更または削除しますか？有効なOwnerがいなくなる操作はサーバーが拒否します。',added:'メンバーを追加しました。',changed:'メンバーのロールを変更しました。',removed:'メンバーを削除しました。',activity:'最近の操作',activityNote:'Native Historyに認証済みactor IDがある場合に表示します。',actorUnknown:'不明なactor',noActivity:'Native Historyのactorイベントはありません。',disabled:'無効',backup:'バックアップ',backupRun:'今すぐバックアップ'}};const t=key=>strings[locale][key]||strings.en[key]||key;
async function json(url,opt={}){opt.headers=Object.assign({'Accept':'application/json'},version,opt.headers||{});const r=await fetch(url,opt);const v=await r.json().catch(()=>({error:'INVALID_RESPONSE'}));if(!r.ok)throw new Error(v.error+': '+(v.message||r.status));return v}
function setRoleLine(collab,principal){if(!collab){$('identity').textContent=principal.id+' ('+principal.role+')';return}const role=t(collab.role);$('identity').textContent=t('workspace')+': '+collab.workspace_name+' · '+t('signedIn')+': '+(principal.display_name||principal.id)+' · '+t('role')+': '+role+(collab.permissions.write?'':' · '+t('readOnly'));}
function renderActivity(snapshot){const section=$('activity-section'),list=$('activity-list');list.replaceChildren();const rows=(snapshot.items||[]).filter(item=>(item.details&&item.details.record||[]).includes('item_event'));section.classList.toggle('hidden',!rows.length);rows.sort((a,b)=>String((a.details.at||[])[0]||'').localeCompare(String((b.details.at||[])[0]||''))).slice(-30).reverse().forEach(item=>{const d=item.details||{},li=document.createElement('li');const at=(d.at||[])[0]||'',actor=(d.actor||[])[0]||t('actorUnknown'),event=(d.event||[])[0]||'event',parent=(d.parent||[])[0]||'';li.textContent=[at,actor,event,parent].filter(Boolean).join(' · ');list.appendChild(li)});if(!rows.length){const li=document.createElement('li');li.textContent=t('noActivity');list.appendChild(li);section.classList.remove('hidden')}}
function errorText(error){const value=String(error);if(value.includes('WORKSPACE_CONFIG_REVISION_CONFLICT'))return t('stale');if(value.includes('WORKSPACE_LAST_OWNER_REQUIRED'))return t('lastOwner');if(value.includes('WORKSPACE_PRINCIPAL_UNKNOWN'))return t('unknown');if(value.includes('WORKSPACE_PERMISSION_DENIED')||value.includes('FORBIDDEN'))return t('insufficient');if(value.includes('WORKSPACE_ACCESS_DENIED')||value.includes('WORKSPACE_NOT_AVAILABLE'))return t('accessDenied');return t('insufficient')}
function renderMembers(rows){const list=$('member-list');list.replaceChildren();if(!rows.length){const empty=document.createElement('p');empty.textContent=t('noMembers');list.appendChild(empty);return}rows.forEach(member=>{const card=document.createElement('article');card.className='member-card';const identity=document.createElement('div');identity.className='member-identity';const label=document.createElement('strong');label.textContent=member.display_name||member.principal_id;const id=document.createElement('div');id.textContent=member.principal_id;const state=document.createElement('div');state.textContent=member.disabled?' · '+t('disabled'):'';identity.append(label,id,state);const controls=document.createElement('div');controls.className='member-controls';const select=document.createElement('select');select.setAttribute('aria-label',t('role')+' · '+member.display_name);['owner','editor','viewer'].forEach(role=>{const option=document.createElement('option');option.value=role;option.textContent=t(role);select.appendChild(option)});select.value=member.role;select.onchange=()=>changeMember('role',member,select.value);const remove=document.createElement('button');remove.type='button';remove.textContent=t('remove');remove.onclick=()=>changeMember('remove',member);controls.append(select,remove);card.append(identity,controls);list.appendChild(card)})}
async function loadMembers(){if(!workspaceName)return;const value=await json('/api/remote/v1/workspace/members?workspace='+encodeURIComponent(workspaceName));configRevision=value.config_revision;renderMembers(value.members||[])}
async function changeMember(operation,member,role){if(!configRevision){$('member-status').textContent=t('insufficient');return}if(operation==='remove'&&!confirm(t('confirmRemove')))return;if(operation==='role'&&member.role==='owner'&&role!=='owner'&&!confirm(t('confirmOwner')))return;$('member-status').textContent='…';const body={workspace:workspaceName,operation,principal_id:member.principal_id,expected_config_revision:configRevision};if(role)body.role=role;try{await json('/api/remote/v1/workspace/members',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,'Origin':location.origin},body:JSON.stringify(body)});$('member-status').textContent=t(operation==='add'?'added':operation==='remove'?'removed':'changed');await load()}catch(error){$('member-status').textContent=errorText(error);if(String(error).includes('WORKSPACE_CONFIG_REVISION_CONFLICT'))await loadMembers().catch(()=>{});if(String(error).includes('WORKSPACE_ACCESS_DENIED')){$('identity').textContent=t('accessDenied');$('members-section').classList.add('hidden');$('activity-section').classList.add('hidden');$('output').textContent=''}}}
async function addMember(event){event.preventDefault();const id=$('new-principal').value.trim(),role=$('new-role').value;if(!id)return;await changeMember('add',{principal_id:id,role:'',display_name:id},role);if($('member-status').textContent===t('added'))$('new-principal').value=''}
function renderOperation(v){$('backup-status').textContent='Status: '+v.status+'; local: '+v.local.status+'; remote: '+v.remote.status;if(v.status==='admitted'||v.status==='running'){poll=setTimeout(()=>json(v.status_url).then(renderOperation).catch(showBackupError),1000)}else{const wait=Math.max(0,Number(v.cooldown_seconds)||0);$('backup-status').textContent+='; next run available after '+wait+' seconds';setTimeout(()=>{operationKey=null;$('run-backup').disabled=false;$('backup-status').textContent='Ready'},wait*1000)}}
function showBackupError(error){$('backup-status').textContent=errorText(error);$('run-backup').disabled=false}
async function loadNotes(offset=0){const generation=++notesGeneration;$('notes-refresh').disabled=true;$('notes-next').disabled=true;try{const value=await json('/api/remote/v1/resources/notes?limit=20&offset='+offset);if(generation!==notesGeneration)return;const data=value.data||{};if(offset&&notesRevision!==data.revision){await loadNotes();return}notesRevision=data.revision;$('output').textContent=JSON.stringify(value,null,2);$('notes-next').hidden=!data.has_more;$('notes-next').dataset.offset=String(data.next_offset||0)}catch(error){if(generation===notesGeneration){$('output').textContent=errorText(error);$('notes-next').hidden=true}}finally{if(generation===notesGeneration){$('notes-refresh').disabled=false;$('notes-next').disabled=false}}}
async function load(){++notesGeneration;notesRevision=null;$('notes-next').hidden=true;$('notes-refresh').disabled=false;const [snapshot,session,capabilities]=await Promise.all([json('/api/remote/v1/snapshot'),json('/api/remote/v1/session'),json('/api/remote/v1/capabilities')]);const collab=snapshot.workspace&&snapshot.workspace.collaboration;setRoleLine(collab,session.principal);workspaceName=collab&&collab.workspace_name;$('output').textContent=JSON.stringify(snapshot,null,2);renderActivity(snapshot);const admin=capabilities.workspace_membership_admin&&capabilities.workspace_membership_admin.available;$('members-section').classList.toggle('hidden',!admin);if(admin)await loadMembers();const op=capabilities.operations&&capabilities.operations.backup_run;const allowed=session.principal.scopes.includes('backup:run')&&op&&op.available;$('backup-operation').classList.toggle('hidden',!allowed);$('login').classList.add('hidden');$('access-denied').classList.add('hidden');$('session').classList.remove('hidden')}
async function signOut(){++notesGeneration;notesRevision=null;$('notes-next').hidden=true;try{await json('/api/remote/v1/browser/logout',{method:'POST',headers:{'X-CSRF-Token':csrf,'Origin':location.origin}})}finally{if(poll)clearTimeout(poll);csrf=null;operationKey=null;workspaceName=null;configRevision=null;$('members-section').classList.add('hidden');$('activity-section').classList.add('hidden');$('backup-operation').classList.add('hidden');$('session').classList.add('hidden');$('access-denied').classList.add('hidden');$('login').classList.remove('hidden');$('output').textContent=''}}
async function resume(){try{const session=await json('/api/remote/v1/browser/session');csrf=session.csrf_token;await load()}catch(error){if(String(error).includes('WORKSPACE_ACCESS_DENIED')||String(error).includes('WORKSPACE_NOT_AVAILABLE')){$('login').classList.add('hidden');$('access-denied-message').textContent=t('accessDenied');$('denied-sign-out').textContent=t('signOut');$('access-denied').classList.remove('hidden')}}}
$('sign-in').onclick=async()=>{try{const token=$('token').value;const session=await json('/api/remote/v1/browser/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});$('token').value='';csrf=session.csrf_token;await load()}catch(error){$('output').textContent=errorText(error);if(String(error).includes('WORKSPACE_ACCESS_DENIED')||String(error).includes('WORKSPACE_NOT_AVAILABLE')){$('login').classList.add('hidden');$('access-denied-message').textContent=t('accessDenied');$('denied-sign-out').textContent=t('signOut');$('access-denied').classList.remove('hidden')}}};
$('notes-refresh').onclick=()=>loadNotes();$('notes-next').onclick=()=>loadNotes(Number($('notes-next').dataset.offset));
$('refresh').onclick=()=>load().catch(error=>{$('output').textContent=errorText(error);if(String(error).includes('WORKSPACE_ACCESS_DENIED')){$('identity').textContent=t('accessDenied');$('members-section').classList.add('hidden');$('activity-section').classList.add('hidden')}});$('members-refresh').onclick=()=>loadMembers().catch(error=>$('member-status').textContent=errorText(error));$('member-add-form').onsubmit=addMember;
$('run-backup').onclick=async()=>{if(!operationKey&&!confirm('Run the configured backup now? This may create locally, upload off-host, and prune according to retention.'))return;$('run-backup').disabled=true;$('backup-status').textContent='Submitting…';operationKey=operationKey||(crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random());try{const value=await json('/api/remote/v1/operations/backup-runs',{method:'POST',headers:{'X-CSRF-Token':csrf,'Idempotency-Key':operationKey,'Origin':location.origin}});renderOperation(value)}catch(error){showBackupError(error)}};
$('logout').onclick=signOut;$('denied-sign-out').onclick=signOut;
document.documentElement.lang=locale==='ja'?'ja':'en';$('intro').textContent=t('intro');$('login-title').textContent=t('signIn');$('token-label').textContent=t('token');$('sign-in').textContent=t('signIn');$('refresh').textContent=t('refresh');$('notes-refresh').textContent=t('notes');$('notes-next').textContent=t('notesNext');$('logout').textContent=t('signOut');$('denied-sign-out').textContent=t('signOut');$('members-title').textContent=t('members');$('members-refresh').textContent=t('loadMembers');$('principal-label').textContent=t('principal');$('role-label').textContent=t('role');$('member-add').textContent=t('add');$('activity-title').textContent=t('activity');$('activity-note').textContent=t('activityNote');$('backup-title').textContent=t('backup');$('run-backup').textContent=t('backupRun');Array.from($('new-role').options).forEach(option=>option.textContent=t(option.value));
resume();})();</script></body></html>"""
    return template.replace("__NONCE__", html.escape(nonce))


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

                    # Workspace membership is checked on every workspace API
                    # request so a stale snapshot cannot preserve authority.
                    if path.startswith(_REMOTE_PREFIX) and path not in (
                        _LOGIN_PATH,
                        _LOGOUT_PATH,
                        _BROWSER_SESSION_PATH,
                        _BACKUP_RUN_PATH,
                    ):
                        from .collaboration import (
                            require_workspace_permission,
                            selected_workspace_name,
                        )

                        configured_workspace = selected_workspace_name(app.state.config)
                        requested_workspace = request.query_params.get("workspace")
                        if (
                            requested_workspace
                            and requested_workspace != configured_workspace
                        ):
                            raise RemoteAccessError(
                                "WORKSPACE_NOT_AVAILABLE",
                                "The selected workspace is unavailable.",
                                404,
                            )
                        membership_operation = None
                        if request.method.upper() in ("GET", "HEAD"):
                            membership_operation = "read"
                        elif path in (
                            "/api/remote/v1/item-mutations",
                            "/api/remote/v1/ticket-mutations",
                            "/api/remote/v1/write-check",
                        ):
                            membership_operation = "write"
                        if membership_operation:
                            request.state.workspace_membership = (
                                require_workspace_permission(
                                    app.state.config,
                                    principal,
                                    membership_operation,
                                    configured_workspace,
                                )
                            )

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
                clock = getattr(request.state, "remote_clock", None)
                if clock is not None:
                    response.headers["X-Lifetxt-Clock-State"] = clock["state"]
                    response.headers["X-Lifetxt-Clock-Skew-Seconds"] = str(
                        clock["skew_seconds"]
                    )
                for key, value in protocol_response_headers(
                    app.state.config, negotiated
                ).items():
                    response.headers[key] = value
                capability_revision_value = getattr(
                    request.state, "remote_capability_revision", None
                )
                if path == "/api/remote/v1/capabilities" and capability_revision_value:
                    response.headers[REMOTE_CAPABILITY_REVISION_HEADER] = (
                        capability_revision_value
                    )
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
                        {
                            "authentication": auth_method,
                            "protocol": negotiated,
                            "session": "active" if session else "not_applicable",
                            "clock": clock_evidence,
                        },
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
                        {
                            "authentication": auth_method,
                            "protocol": negotiated,
                            "session": "active" if session else "not_applicable",
                            "clock": clock_evidence,
                        },
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
            value = capability(app.state.config, request.state.remote_protocol)
            membership = getattr(request.state, "workspace_membership", None)
            if (
                membership
                and membership["collaboration_enabled"]
                and int(request.state.remote_protocol) >= 2
            ):
                member_admin_available = bool(
                    membership["permissions"]["member_admin"]
                    and app.state.config.get("_path")
                    and os.path.isfile(app.state.config.get("_path"))
                )
                value["workspace_collaboration"] = {
                    "enabled": True,
                    "role": membership["role"],
                    "permissions": membership["permissions"],
                    "member_management_available": member_admin_available,
                }
                if member_admin_available:
                    features = list(value.get("features") or [])
                    if "workspace-membership-admin" not in features:
                        features.append("workspace-membership-admin")
                    value["features"] = features
                    value["workspace_membership_admin"] = {
                        "available": True,
                        "route": _WORKSPACE_MEMBERS_PATH,
                        "operations": ["list", "add", "role", "remove"],
                        "config_revision_required": True,
                    }
                else:
                    value["workspace_membership_admin"] = {"available": False}
                capability_payload = OrderedDict(value)
                capability_payload.pop("capability_revision", None)
                value["capability_revision"] = hashlib.sha256(
                    json.dumps(
                        capability_payload, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest()
                request.state.remote_capability_revision = value["capability_revision"]
            return value

        @app.get(_WORKSPACE_MEMBERS_PATH)
        def workspace_members(request: Request, workspace: str = Query(...)):
            _require_v2(request)
            from .collaboration import fresh_config_snapshot, member_listing

            app.state.config, _revision = fresh_config_snapshot(app.state.config)
            return member_listing(app.state.config, principal(request), str(workspace))

        @app.post(_WORKSPACE_MEMBERS_PATH)
        def workspace_member_mutation(request: Request, payload=Body(default={})):
            _require_v2(request)
            current = principal(request)
            body = payload if isinstance(payload, dict) else {}
            operation = str(body.get("operation") or "").strip().lower()
            workspace_name = str(body.get("workspace") or "")[:128]
            target_id = str(body.get("principal_id") or "")[:128]
            target_role = body.get("role")
            outcome = 403
            before_revision = None
            after_revision = None
            expected_revision = body.get("expected_config_revision")
            target_is_configured = target_id in principal_registry(app.state.config)
            try:
                allowed_fields = {
                    "workspace",
                    "operation",
                    "principal_id",
                    "role",
                    "expected_config_revision",
                }
                if set(body) - allowed_fields:
                    raise RemoteAccessError(
                        "WORKSPACE_MEMBER_REQUEST_INVALID",
                        "The membership request contains unsupported fields.",
                        400,
                    )
                from .collaboration import (
                    change_membership,
                    fresh_config_snapshot,
                    selected_workspace_name,
                )

                fresh_config, before_revision = fresh_config_snapshot(app.state.config)
                target_is_configured = target_id in principal_registry(fresh_config)
                configured_workspace = selected_workspace_name(app.state.config)
                if workspace_name != configured_workspace:
                    raise RemoteAccessError(
                        "WORKSPACE_NOT_AVAILABLE",
                        "The selected workspace is unavailable.",
                        404,
                    )
                result, updated_config = change_membership(
                    fresh_config,
                    current,
                    workspace_name,
                    operation,
                    target_id,
                    target_role,
                    expected_revision,
                )
                app.state.config = updated_config
                after_revision = result["revision_after"]
                outcome = 200
                return result
            except RemoteAccessError as exc:
                outcome = exc.status
                raise
            finally:
                action = (
                    "member.%s" % operation
                    if operation in ("add", "role", "remove")
                    else "member.invalid"
                )
                _audit_safely(
                    app.state.config,
                    audit_event(
                        current,
                        action,
                        outcome,
                        request.state.remote_request_id,
                        request.client.host if request.client else None,
                        {
                            "workspace_id": __import__("hashlib")
                            .sha256(
                                (
                                    "lifetxt-collaboration-workspace-v1\0"
                                    + workspace_name
                                ).encode("utf-8")
                            )
                            .hexdigest(),
                            "target_principal": target_id
                            if target_is_configured
                            else None,
                            "target_role": target_role
                            if target_role in ("owner", "editor", "viewer")
                            else None,
                            "expected_config_revision": expected_revision
                            if isinstance(expected_revision, str)
                            and len(expected_revision) == 64
                            and all(
                                char in "0123456789abcdef" for char in expected_revision
                            )
                            else None,
                            "before_config_revision": before_revision,
                            "result_config_revision": after_revision,
                        },
                    ),
                )

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
            value = snapshot(
                app.state.paths,
                app.state.config,
                current,
                request.state.remote_protocol,
                app.state.writable_path,
            )
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

        @app.get("/api/remote/v1/historical")
        def remote_historical(request: Request):
            _require_v2(request)
            current = principal(request)
            return read_historical_resource(
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

        @app.post(_BACKUP_RUN_PATH, status_code=202)
        def admit_backup_run(request: Request):
            _require_v2(request)
            current = principal(request)
            require_scope(current, "backup:run")
            operation, duplicate = backup_run_store.admit(
                current["id"], request.headers.get("idempotency-key"), app.state.config
            )
            event = audit_event(
                current,
                "backup.run",
                "duplicate" if duplicate else "accepted",
                request.state.remote_request_id,
                request.client.host if request.client else None,
                {"operation_id": operation["operation_id"]},
            )
            if not _audit_safely(app.state.config, event):
                if not duplicate:
                    backup_run_store.abandon(operation["operation_id"])
                raise RemoteAccessError(
                    "AUDIT_UNAVAILABLE", "Backup run audit is unavailable.", 503
                )
            if not duplicate:
                lifecycle_request_id = request.state.remote_request_id
                lifecycle_host = request.client.host if request.client else None

                def audit_lifecycle(outcome, operation_id):
                    _audit_safely(
                        app.state.config,
                        audit_event(
                            current,
                            "backup.run",
                            outcome,
                            lifecycle_request_id,
                            lifecycle_host,
                            {"operation_id": operation_id},
                        ),
                    )

                backup_run_store.start(
                    operation["operation_id"],
                    app.state.config,
                    audit_callback=audit_lifecycle,
                )
            return operation

        @app.get("/api/remote/v1/operations/backup-runs/{operation_id}")
        def backup_run_status(operation_id: str, request: Request):
            _require_v2(request)
            current = principal(request)
            require_scope(current, "backup:run")
            return backup_run_store.get(operation_id, current["id"])

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
