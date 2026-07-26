"""Authenticated, deny-by-default Remote Safe Mode contracts."""
from __future__ import unicode_literals

import hashlib
import hmac
import ipaddress
import json
import os
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque

ROLES = {
    "owner": frozenset(("read", "write", "admin", "audit")),
    "editor": frozenset(("read", "write")),
    "reader": frozenset(("read",)),
    "auditor": frozenset(("read", "audit")),
}
VISIBILITIES = frozenset(("public", "shared", "team", "private", "secret"))

class RemoteAccessError(ValueError):
    def __init__(self, code, message, status=403):
        super(RemoteAccessError, self).__init__(message)
        self.code = str(code); self.status = int(status)


def _section(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def enabled(config):
    return bool(_section(config).get("enabled", False))


def _principal_rows(config):
    value = _section(config).get("principals") or []
    if isinstance(value, dict):
        rows=[]
        for key,row in value.items():
            item=dict(row or {}); item.setdefault("id", str(key)); rows.append(item)
        return rows
    return [dict(row) for row in value if isinstance(row, dict)]


def principal_registry(config):
    result=OrderedDict()
    for row in _principal_rows(config):
        pid=str(row.get("id") or "").strip()
        if not pid or pid in result: continue
        role=str(row.get("role") or "reader").lower()
        if role not in ROLES: role="reader"
        scopes=set(ROLES[role]); scopes.update(str(x) for x in row.get("scopes") or [])
        result[pid]=OrderedDict((
            ("id",pid),("display_name",str(row.get("display_name") or pid)),
            ("role",role),("scopes",sorted(scopes)),
            ("projects",sorted(str(x) for x in row.get("projects") or [])),
            ("groups",sorted(str(x) for x in row.get("groups") or [])),
            ("visibilities",sorted(str(x) for x in row.get("visibilities") or ["public","shared"])),
            ("disabled",bool(row.get("disabled"))),
            ("token_env",row.get("token_env")),
        ))
    return result


def _token_for(row):
    name=row.get("token_env")
    return os.environ.get(str(name)) if name else None


def _trusted_peer(remote, address):
    if not address: return False
    try: ip=ipaddress.ip_address(str(address))
    except ValueError: return False
    for raw in remote.get("trusted_proxies") or []:
        try:
            if ip in ipaddress.ip_network(str(raw), strict=False): return True
        except ValueError: continue
    return False


def authenticate(headers, client_host, config):
    if not enabled(config):
        raise RemoteAccessError("REMOTE_DISABLED", "Remote Safe Mode is disabled.", 404)
    remote=_section(config); registry=principal_registry(config)
    headers={str(k).lower():str(v) for k,v in (headers or {}).items()}
    proxy_header=str(remote.get("proxy_principal_header") or "X-Lifetxt-Principal").lower()
    asserted=headers.get(proxy_header)
    if asserted and _trusted_peer(remote, client_host):
        row=registry.get(asserted)
        if row and not row["disabled"]: return row, "trusted-proxy"
        raise RemoteAccessError("UNKNOWN_PRINCIPAL", "Trusted proxy asserted an unknown principal.", 401)
    auth=headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise RemoteAccessError("UNAUTHORIZED", "Authorization: Bearer TOKEN is required.", 401)
    supplied=auth[7:]
    for row in registry.values():
        expected=_token_for(row)
        if expected and not row["disabled"] and hmac.compare_digest(supplied, expected):
            return row, "bearer"
    raise RemoteAccessError("UNAUTHORIZED", "The bearer token is invalid.", 401)


def require_scope(principal, scope):
    if scope not in set(principal.get("scopes") or []):
        raise RemoteAccessError("FORBIDDEN", "Principal lacks %s scope." % scope, 403)


def can_access(principal, project=None, visibility="shared", owner=None, groups=None):
    visibility=str(visibility or "shared").lower()
    if visibility not in VISIBILITIES: visibility="private"
    if principal.get("role") == "owner": return True
    if project and principal.get("projects") and str(project) not in principal.get("projects",[]): return False
    if visibility == "public": return True
    if visibility == "shared": return visibility in principal.get("visibilities",[])
    if visibility == "team":
        return bool(set(groups or []) & set(principal.get("groups") or []))
    if visibility in ("private","secret"):
        return bool(owner and str(owner)==principal.get("id"))
    return False


def filter_records(records, principal):
    out=[]
    for row in records or []:
        if can_access(principal,row.get("project"),row.get("visibility"),row.get("owner"),row.get("groups")):
            value=dict(row)
            for key in list(value):
                if "path" in key.lower() and os.path.isabs(str(value[key])): value[key]="<redacted>"
            out.append(value)
    return out


def require_exact_revision(headers, current):
    value=(headers or {}).get("if-match") or (headers or {}).get("If-Match")
    if not value: raise RemoteAccessError("REVISION_REQUIRED", "If-Match exact revision is required.", 428)
    value=str(value).strip().strip('"')
    if value != str(current): raise RemoteAccessError("REVISION_CONFLICT", "The authoritative revision changed.", 409)
    return value


def require_https(headers, client_host, config):
    remote=_section(config)
    proto=str((headers or {}).get("x-forwarded-proto") or (headers or {}).get("X-Forwarded-Proto") or "http").split(",")[0].strip().lower()
    loopback=str(client_host or "") in ("127.0.0.1","::1","localhost","testclient")
    if proto != "https" and not (loopback and remote.get("allow_loopback_http", True)):
        raise RemoteAccessError("HTTPS_REQUIRED", "Remote access requires HTTPS.", 400)


class RateLimiter(object):
    def __init__(self): self._lock=threading.Lock(); self._events=defaultdict(deque)
    def check(self, key, limit, window=60):
        now=time.monotonic()
        with self._lock:
            q=self._events[str(key)]
            while q and q[0] <= now-window: q.popleft()
            if len(q)>=int(limit): raise RemoteAccessError("RATE_LIMITED","Remote request rate limit exceeded.",429)
            q.append(now)


def request_id(headers=None):
    value=(headers or {}).get("x-request-id") or (headers or {}).get("X-Request-ID")
    return str(value or uuid.uuid4())[:128]


def audit_event(principal, action, outcome, request_id_value, client_host=None, detail=None):
    return OrderedDict((
        ("schema","remote-audit-event-v1.schema.json"),("version","1"),
        ("at",__import__("lifetxt.timezone_policy",fromlist=["utcnow"]).utcnow().isoformat()),("request_id",request_id_value),
        ("principal",principal.get("id") if principal else None),("role",principal.get("role") if principal else None),
        ("action",str(action)),("outcome",str(outcome)),("client",str(client_host or "")),
        ("detail",dict(detail or {})),
    ))


def append_audit(config, event):
    remote=_section(config); path=remote.get("audit_log")
    if not path: return
    path=os.path.abspath(os.path.expanduser(str(path)))
    line=json.dumps(event,ensure_ascii=False,separators=(",",":"))+"\n"
    limit=int(remote.get("audit_max_bytes") or 5*1024*1024)
    from .mutation import write_text
    def transform(current):
        value=current+line
        if len(value.encode("utf-8")) > limit:
            value=value[-max(1,limit//2):]
            cut=value.find("\n")
            if cut >= 0: value=value[cut+1:]
        return value
    write_text(path,transform=transform,operation="remote audit append",create=True,default_text="")


def capability(config):
    remote=_section(config)
    return OrderedDict((
        ("schema","remote-access-policy-v1.schema.json"),("contract_version","1"),
        ("enabled",enabled(config)),("browser_ui",bool(remote.get("browser_ui",False))),
        ("authentication",["bearer","trusted-proxy"]),("roles",{k:sorted(v) for k,v in ROLES.items()}),
        ("exact_revision_required",True),("https_required",True),
        ("write_operations",["ticket.transition","ticket.comment","ticket.change","ticket.assign","ticket.plan"]),
        ("read_operations",["capabilities","session","snapshot","tickets","projects","audit"]),
        ("remote_opener_execution",False),("local_paths_redacted",True),
    ))
