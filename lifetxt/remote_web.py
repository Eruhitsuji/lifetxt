"""FastAPI surface for authenticated Remote Safe Mode."""
from __future__ import unicode_literals
import hashlib, os
from collections import OrderedDict
from .remote_access import (RateLimiter, RemoteAccessError, append_audit, audit_event, authenticate, capability, filter_records, request_id, require_exact_revision, require_https, require_scope)

_INSTALLED=False

def _revision(paths):
    h=hashlib.sha256()
    for path in paths:
        h.update(str(path).encode()); h.update(b"\0")
        try:
            with open(path,"rb") as f:
                for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        except OSError: h.update(b"<missing>")
        h.update(b"\0")
    return h.hexdigest()

def _item_rows(paths, config):
    from .ticket_projects import load_items
    from .tickets import ticket_list
    items=load_items(paths)
    tickets=ticket_list(items,config)
    projects=[]; seen=set()
    for row in tickets:
        p=row.get("project")
        if p and p not in seen: seen.add(p); projects.append({"id":p,"name":p,"visibility":"shared"})
    for row in tickets:
        row.setdefault("visibility","shared")
        row.setdefault("owner",row.get("assignee"))
    return tickets,projects

def install_remote_web():
    global _INSTALLED
    if _INSTALLED:return
    from . import webapp, surface_runtime
    surface_runtime._WEB_NO_REVISION_PATHS = frozenset(set(surface_runtime._WEB_NO_REVISION_PATHS) | {"/api/remote/v1/write-check"})
    original=webapp.create_app; limiter=RateLimiter()
    def create_app(paths=None,writable_path=None,config=None,read_only=False):
        from fastapi import Body, Request
        from fastapi.responses import JSONResponse
        app=original(paths=paths,writable_path=writable_path,config=config,read_only=read_only)
        app.state.remote_enabled=bool((app.state.config.get("remote") or {}).get("enabled"))
        @app.middleware("http")
        async def remote_guard(request:Request,call_next):
            if not request.url.path.startswith("/api/remote/v1/"): return await call_next(request)
            rid=request_id(request.headers)
            try:
                host=request.client.host if request.client else None
                require_https(request.headers,host,app.state.config)
                principal,method=authenticate(request.headers,host,app.state.config)
                limit=int((app.state.config.get("remote") or {}).get("rate_limit_per_minute") or 120)
                limiter.check(principal["id"],limit)
                request.state.remote_principal=principal; request.state.remote_auth_method=method; request.state.remote_request_id=rid
                response=await call_next(request)
                response.headers["X-Request-ID"]=rid
                append_audit(app.state.config,audit_event(principal,request.method+" "+request.url.path,response.status_code,rid,host))
                return response
            except RemoteAccessError as exc:
                append_audit(app.state.config,audit_event(None,request.method+" "+request.url.path,exc.code,rid,request.client.host if request.client else None))
                return JSONResponse(status_code=exc.status,content={"error":exc.code,"message":str(exc),"request_id":rid},headers={"X-Request-ID":rid})
        def principal(request): return request.state.remote_principal
        @app.get("/api/remote/v1/capabilities")
        def remote_capabilities(request:Request):
            require_scope(principal(request),"read"); return capability(app.state.config)
        @app.get("/api/remote/v1/session")
        def remote_session(request:Request):
            p=principal(request); require_scope(p,"read")
            return {"schema":"remote-session-v1.schema.json","principal":p,"authentication":request.state.remote_auth_method,"request_id":request.state.remote_request_id}
        @app.get("/api/remote/v1/snapshot")
        def remote_snapshot(request:Request):
            p=principal(request); require_scope(p,"read"); tickets,projects=_item_rows(app.state.paths,app.state.config)
            return {"schema":"remote-snapshot-v1.schema.json","revision":_revision(app.state.paths),"tickets":filter_records(tickets,p),"projects":filter_records(projects,p),"read_only":app.state.read_only}
        @app.get("/api/remote/v1/tickets")
        def remote_tickets(request:Request):
            p=principal(request); require_scope(p,"read"); tickets,_=_item_rows(app.state.paths,app.state.config); return {"revision":_revision(app.state.paths),"tickets":filter_records(tickets,p)}
        @app.get("/api/remote/v1/projects")
        def remote_projects(request:Request):
            p=principal(request); require_scope(p,"read"); _,projects=_item_rows(app.state.paths,app.state.config); return {"revision":_revision(app.state.paths),"projects":filter_records(projects,p)}
        @app.post("/api/remote/v1/write-check")
        def remote_write_check(request:Request,payload=Body(default={})): 
            p=principal(request); require_scope(p,"write"); current=_revision(app.state.paths); require_exact_revision(request.headers,current)
            return {"ok":True,"revision":current,"operation":str((payload or {}).get("operation") or "write-check"),"principal":p["id"]}
        @app.get("/api/remote/v1/audit")
        def remote_audit(request:Request):
            p=principal(request); require_scope(p,"audit"); path=(app.state.config.get("remote") or {}).get("audit_log"); rows=[]
            if path and os.path.exists(path):
                import json
                with open(path,encoding="utf-8") as h:
                    for line in h.readlines()[-200:]:
                        try: rows.append(json.loads(line))
                        except ValueError: pass
            return {"events":rows}
        return app
    webapp.create_app=create_app; _INSTALLED=True
