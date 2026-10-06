"""Dedicated bearer-only ASGI consumer; no generic Web routes are mounted."""

import asyncio
from collections import deque
from copy import deepcopy
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import threading
import time
from types import SimpleNamespace

from . import attachment_snapshot
from .remote_access import authenticate_token, _token_for
from .resource_reference_policy import policy, validate_principals, safe_text, HANDLE
from .resource_reference_resolution import (
    ReadContext,
    ResourceResolver,
    ResourceFailure,
)
from .resource_reference_store import BindingStore, BindingUnavailable, REF
from .schema_extensions_v33 import ERROR_CATALOG

PREFIX = "/api/remote/v1/resource-references/"
CODES = dict(ERROR_CATALOG)
STATUS = dict(
    AUTHENTICATION_REQUIRED=401,
    INVALID_REFERENCE=400,
    REVISION_REQUIRED=400,
    INVALID_REQUEST=400,
    RESOURCE_UNAVAILABLE=404,
    STALE_REVISION=409,
    UNSUPPORTED_CONTRACT=406,
    OPERATION_UNSUPPORTED=405,
    RESOURCE_LIMIT=429,
    RESOURCE_BUSY=503,
)
SAFE_HEADERS = {
    "cache-control": "private, no-store",
    "referrer-policy": "no-referrer",
    "cross-origin-resource-policy": "same-origin",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'; sandbox",
}


class Admission:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = {}
        self.rates = {}

    def rate(self, key, limit):
        with self.lock:
            now = time.monotonic()
            queue = self.rates.setdefault(key, deque())
            while queue and queue[0] <= now - 60:
                queue.popleft()
            if len(queue) >= limit:
                raise ResourceFailure("RESOURCE_LIMIT")
            queue.append(now)

    def reserve(self, context, limits):
        with self.lock:
            if len(self.active) >= limits["active_process"]:
                raise ResourceFailure("RESOURCE_BUSY")
            context.admission_key = secrets.token_hex(16)
            self.active[context.admission_key] = None

    def identify(self, context):
        with self.lock:
            if context.principal_id in self.active.values():
                raise ResourceFailure("RESOURCE_BUSY")
            self.active[context.admission_key] = context.principal_id

    def release_when_stopped(self, context):
        def release():
            while not context.stopped():
                time.sleep(0.05)
            with self.lock:
                self.active.pop(context.admission_key, None)

        if context.stopped():
            release()
        else:
            threading.Thread(
                target=release, daemon=True, name="resource-slot-reap"
            ).start()


_ADMISSION = Admission()


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ResourceFailure("INVALID_REQUEST")
        result[key] = value
    return result


def envelope(raw, operation):
    try:
        if raw.startswith(b"\xef\xbb\xbf") or len(raw) > 2048:
            raise ValueError()
        data = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError()),
        )
        if not isinstance(data, dict):
            raise ValueError()
        if data.get("contract_version") != "1":
            if isinstance(data.get("contract_version"), str) and re.fullmatch(
                r"[0-9]{1,3}", data["contract_version"]
            ):
                raise ResourceFailure("UNSUPPORTED_CONTRACT")
            raise ResourceFailure("INVALID_REQUEST")
        base = {"contract_version", "workspace_id"}
        fields = base | (
            {"source_id", "item_id"}
            if operation == "discover"
            else {"resource_ref", "source_revision", "resource_revision"}
        )
        if operation == "chunk":
            fields |= {"offset", "length"}
        if operation != "discover" and not {
            "source_revision",
            "resource_revision",
        } <= set(data):
            raise ResourceFailure("REVISION_REQUIRED")
        if set(data) != fields:
            raise ValueError()
        if not isinstance(data["workspace_id"], str) or not HANDLE.fullmatch(
            data["workspace_id"]
        ):
            raise ValueError()
        if operation == "discover":
            if (
                not isinstance(data["source_id"], str)
                or not HANDLE.fullmatch(data["source_id"])
                or not safe_text(data["item_id"])
            ):
                raise ValueError()
        else:
            for key, prefix in [
                ("resource_ref", "att:v1:"),
                ("source_revision", "rev:v1:"),
                ("resource_revision", "rev:v1:"),
            ]:
                value = data[key]
                if not isinstance(value, str) or len(value) > 64:
                    raise ResourceFailure("INVALID_REFERENCE")
                if not value.startswith(prefix) and re.fullmatch(
                    prefix[:4] + r"v[0-9]{1,3}:[0-9a-f]{32}", value
                ):
                    raise ResourceFailure("UNSUPPORTED_CONTRACT")

                if not re.fullmatch(prefix + r"[0-9a-f]{32}", value):
                    raise ResourceFailure("INVALID_REFERENCE")
        if operation == "chunk":
            if type(data["offset"]) is not int or not 0 <= data["offset"] <= 10485760:
                raise ValueError()
            if type(data["length"]) is not int or not 1 <= data["length"] <= 65536:
                raise ValueError()
        return data
    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
        if isinstance(exc, ResourceFailure):
            raise
        raise ResourceFailure("INVALID_REQUEST") from None


class ResourceApplication:
    """Single-worker isolated listener. Operator must not expose generic listeners."""

    def __init__(self, config):
        rules = policy(config)
        registry = validate_principals(config)
        self.validate_audit(config)
        if not rules["enabled"]:
            raise BindingUnavailable()
        if not any(not row["disabled"] for row in registry.values()):
            raise BindingUnavailable()
        self.state = SimpleNamespace(config=deepcopy(config), resource_resolver=None)
        self.credentials = {
            key: hashlib.sha256((_token_for(row) or "").encode()).digest()
            for key, row in registry.items()
            if not row["disabled"]
        }
        self.startup_config = deepcopy(config)
        self.store = None
        self.resolver = None

    def load(self, context):
        config = deepcopy(self.state.config)
        if config.get("_path"):
            path = Path(config["_path"]).absolute()
            completed = threading.Event()
            completed.set()
            context.workers.append(completed)
            snapshot = attachment_snapshot.read_snapshot(
                path.parent,
                path.name,
                1048576,
                seconds=context.remaining(),
                cancel=context.cancel,
                principal=context.principal_id
                or ("resource-preauth:" + getattr(context, "admission_key", "startup")),
                completed=completed,
            )
            config = json.loads(
                snapshot.data.decode("utf-8-sig"), object_pairs_hook=_pairs
            )
            config["_path"] = str(path)
        policy(config)
        validate_principals(config)
        self.validate_audit(config)
        # Storage/workspace/selectors and limits are restart boundaries; current
        # grants/metadata reload. Never switch to another install via config edit.
        for key in (
            "enabled",
            "contract_version",
            "workspace_id",
            "store_path",
            "enrolled_items",
            "limits",
        ):
            if policy(config)[key] != policy(self.startup_config)[key]:
                raise ResourceFailure()
        return config

    @staticmethod
    def validate_audit(config):
        remote = config.get("remote") or {}
        if not remote.get("audit_log"):
            return
        from .workspace import resolve_workspace
        from .remote_backend import _opaque_id
        from .collaboration import selected_workspace_name
        from .attachments import split_value
        from .remote_access import validate_remote_storage
        from .resource_reference_store import _check_file
        from .attachment_snapshot import _root_fd

        resolved = resolve_workspace(config)
        protected = list(resolved["input_paths"])
        rules = policy(config)
        protected.extend(
            str(rules["store_path"]) + suffix
            for suffix in ("", ".owner", "-wal", "-shm", "-journal")
        )
        if config.get("_path"):
            protected.append(config["_path"])
        workspace = _opaque_id("workspace", selected_workspace_name(config))
        for index, source in enumerate(resolved["sources"]):
            if len(source["files"]) != 1:
                raise BindingUnavailable()
            source_id = _opaque_id("source", workspace, index, 0, source["role"])
            for entry in rules["enrolled_items"]:
                if entry["source_id"] == source_id:
                    relative, _ = split_value(entry["attachment"])
                    protected.append(str(Path(source["files"][0]).parent / relative))
        validate_remote_storage(config, protected)
        audit = Path(os.path.expanduser(str(remote["audit_log"]))).absolute()
        # Existing protected sink only, no audit creation beside sources.
        _check_file(audit)
        root = _root_fd(audit.parent)
        try:
            import stat

            if stat.S_IMODE(os.fstat(root).st_mode) != 0o700:
                raise BindingUnavailable()
        finally:
            os.close(root)

    async def work(self, context, function, *args):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        done = threading.Event()
        context.workers.append(done)

        def finish(result, error):
            if not future.done():
                if error:
                    future.set_exception(error)
                else:
                    future.set_result(result)

        def worker():
            result = error = None
            try:
                result = function(*args)
            except BaseException as exc:
                error = exc
            finally:
                done.set()
                try:
                    loop.call_soon_threadsafe(finish, result, error)
                except RuntimeError:
                    pass

        threading.Thread(target=worker, daemon=True, name="resource-operation").start()
        return await asyncio.wait_for(future, context.remaining())

    async def start(self):
        rules = policy(self.state.config)
        self.store = BindingStore(rules["store_path"])
        try:
            self.resolver = ResourceResolver(self.store, self.load)
            self.state.resource_resolver = self.resolver
            for principal in self.credentials:
                context = ReadContext(
                    principal, time.monotonic() + rules["limits"]["deadline_seconds"]
                )
                # Each selector is enrolled exactly once by owner configuration.
                await self.work(context, self.resolver.enroll_selected, context)
                break
        except BaseException:
            self.store.close()
            self.store = None
            self.resolver = None
            raise

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        await self.start()
                        await send({"type": "lifespan.startup.complete"})
                    except Exception:
                        await send(
                            {
                                "type": "lifespan.startup.failed",
                                "message": "Resource service unavailable.",
                            }
                        )
                        return
                elif message["type"] == "lifespan.shutdown":
                    if self.store:
                        self.store.close()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
            return
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return
        started = False
        context = None
        lease = False
        watch = None
        try:
            _ADMISSION.rate("preauth", 120)
            negotiation = [
                key.lower()
                for key, _ in scope["headers"]
                if key.lower()
                in (b"x-lifetxt-remote-version", b"x-lifetxt-resource-contract")
            ]
            if len(negotiation) != len(set(negotiation)):
                raise ResourceFailure("UNSUPPORTED_CONTRACT")
            headers = _pairs(
                [
                    (k.decode("ascii").lower(), v.decode("latin1"))
                    for k, v in scope["headers"]
                ]
            )
            rules = policy(self.state.config)
            context = ReadContext(
                "", time.monotonic() + rules["limits"]["deadline_seconds"]
            )
            _ADMISSION.reserve(context, rules["limits"])
            lease = True
            config = await self.work(context, self.load, context)
            from starlette.requests import Request
            from .web_transport import expected_origin, origin_parts

            effective = origin_parts(expected_origin(Request(scope), config))
            if not effective or effective[0] != "https":
                raise ResourceFailure("UNSUPPORTED_CONTRACT")
            if scope.get("query_string") or "@" in headers.get("host", ""):
                raise ResourceFailure("INVALID_REQUEST")
            if (
                "cookie" in headers
                or "origin" in headers
                or any(k.startswith("sec-fetch-") for k in headers)
            ):
                raise ResourceFailure("INVALID_REQUEST")
            if (config.get("remote") or {}).get(
                "proxy_principal_header", "X-Lifetxt-Principal"
            ).lower() in headers:
                raise ResourceFailure("INVALID_REQUEST")
            auth = headers.get("authorization", "")
            if not auth.startswith("Bearer ") or not auth[7:]:
                raise ResourceFailure("AUTHENTICATION_REQUIRED")
            try:
                principal, _ = authenticate_token(
                    auth[7:], config, allow_restricted=True
                )
            except ValueError:
                raise ResourceFailure("AUTHENTICATION_REQUIRED") from None
            if (
                principal.get("disclosure_mode") != "restricted-resource"
                or self.credentials.get(principal["id"])
                != hashlib.sha256(auth[7:].encode()).digest()
            ):
                raise ResourceFailure("AUTHENTICATION_REQUIRED")
            context.principal_id = principal["id"]
            rules = policy(config)
            limits = rules["limits"]
            _ADMISSION.rate(
                "principal:" + principal["id"],
                min(
                    limits["rate_principal"],
                    int(config["remote"].get("rate_limit_per_minute") or 120),
                ),
            )
            _ADMISSION.rate("process", limits["rate_process"])
            _ADMISSION.identify(context)
            operation = (
                scope["path"][len(PREFIX) :]
                if scope["path"].startswith(PREFIX)
                else None
            )
            if operation not in ("discover", "full", "chunk"):
                raise ResourceFailure()
            if scope["method"] != "POST":
                raise ResourceFailure("OPERATION_UNSUPPORTED")
            if (
                headers.get("x-lifetxt-remote-version") != "2"
                or headers.get("x-lifetxt-resource-contract") != "resource-reference-v1"
            ):
                raise ResourceFailure("UNSUPPORTED_CONTRACT")
            if headers.get("content-type") != "application/json" or any(
                key in headers for key in ("range", "if-range", "content-encoding")
            ):
                raise ResourceFailure("INVALID_REQUEST")
            length = headers.get("content-length")
            if length is not None and (
                not length.isdecimal() or len(length) > 4 or int(length) > 2048
            ):
                raise ResourceFailure("INVALID_REQUEST")
            raw = bytearray()
            while True:
                message = await asyncio.wait_for(receive(), context.remaining())
                if message["type"] == "http.disconnect":
                    context.cancel.set()
                    return
                if message["type"] != "http.request":
                    raise ResourceFailure("INVALID_REQUEST")
                raw.extend(message.get("body", b""))
                if len(raw) > 2048:
                    raise ResourceFailure("INVALID_REQUEST")
                if not message.get("more_body", False):
                    break
            if length is not None and int(length) != len(raw):
                raise ResourceFailure("INVALID_REQUEST")
            data = envelope(bytes(raw), operation)
            if self.resolver is None:
                raise ResourceFailure("RESOURCE_BUSY")

            async def disconnected():
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        context.cancel.set()
                        return

            watch = asyncio.create_task(disconnected())
            response_headers = dict(
                SAFE_HEADERS,
                **{
                    "x-lifetxt-remote-version": "2",
                    "x-lifetxt-resource-contract": "resource-reference-v1",
                },
            )
            if operation == "discover":
                result = await self.work(
                    context,
                    self.resolver.discover,
                    data["workspace_id"],
                    data["source_id"],
                    data["item_id"],
                    context,
                )
                payload = json.dumps(result, separators=(",", ":")).encode()
                response_headers.update(
                    {
                        "content-type": "application/json",
                        "content-length": str(len(payload)),
                    }
                )
                started = True
                await self._send(
                    send,
                    context,
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": self._headers(response_headers),
                    },
                )
                started = True
                await self._send(
                    send, context, {"type": "http.response.body", "body": payload}
                )
                return
            args = (
                data["workspace_id"],
                data["resource_ref"],
                data["source_revision"],
                data["resource_revision"],
                context,
            )
            snapshot = await self.work(context, self.resolver.read, *args)
            offset = data.get("offset", 0)
            size = len(snapshot.data)
            amount = data.get("length", size)
            if operation == "chunk" and (
                amount > limits["chunk_bytes"]
                or amount
                > min(
                    limits["file_bytes"],
                    int(
                        (config.get("attachments") or {}).get("remote_chunk_bytes")
                        or 65536
                    ),
                )
            ):
                raise ResourceFailure("INVALID_REQUEST")
            if offset > size:
                raise ResourceFailure("INVALID_REQUEST")
            payload = snapshot.data[offset : offset + amount]
            response_headers.update(
                {
                    "content-type": "application/octet-stream",
                    "content-disposition": 'attachment; filename="download.bin"',
                    "content-length": str(len(payload)),
                    "x-lifetxt-source-revision": data["source_revision"],
                    "x-lifetxt-resource-revision": data["resource_revision"],
                }
            )
            if operation == "chunk":
                response_headers.update(
                    {
                        "x-lifetxt-next-offset": str(offset + len(payload)),
                        "x-lifetxt-eof": str(offset + len(payload) >= size).lower(),
                    }
                )
            await self.work(context, self.resolver.read, *args)
            started = True
            await self._send(
                send,
                context,
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": self._headers(response_headers),
                },
            )
            started = True
            for start in range(0, len(payload), 65536):
                fresh = await self.work(context, self.resolver.read, *args)
                if fresh != snapshot:
                    raise ResourceFailure("STALE_REVISION")
                await self._send(
                    send,
                    context,
                    {
                        "type": "http.response.body",
                        "body": payload[start : start + 65536],
                        "more_body": True,
                    },
                )
            await self._send(send, context, {"type": "http.response.body", "body": b""})
        except asyncio.CancelledError:
            if context:
                context.cancel.set()
            raise
        except Exception as exc:
            if started:
                outcome = "aborted"
                raise ConnectionAbortedError("Resource transfer aborted.") from None
            if context and context.cancel.is_set():
                return
            code = exc.code if isinstance(exc, ResourceFailure) else "RESOURCE_BUSY"
            payload = json.dumps(
                {"error": {"code": code, "message": CODES[code]}}, separators=(",", ":")
            ).encode()
            safe = dict(
                SAFE_HEADERS,
                **{
                    "content-type": "application/json",
                    "content-length": str(len(payload)),
                },
            )
            error_deadline = (
                min(1.0, max(0.001, context.deadline - time.monotonic()))
                if context
                else 1.0
            )
            await asyncio.wait_for(
                send(
                    {
                        "type": "http.response.start",
                        "status": STATUS[code],
                        "headers": self._headers(safe),
                    }
                ),
                error_deadline,
            )
            await asyncio.wait_for(
                send({"type": "http.response.body", "body": payload}), error_deadline
            )
        finally:
            if watch:
                watch.cancel()
                try:
                    await watch
                except asyncio.CancelledError:
                    pass
            if context:
                context.cancel.set()
                if lease:
                    _ADMISSION.release_when_stopped(context)

    @staticmethod
    def _headers(headers):
        return [(k.encode("ascii"), v.encode("ascii")) for k, v in headers.items()]

    @staticmethod
    async def _send(send, context, message):
        await asyncio.wait_for(send(message), context.remaining())


_INSTALLED = False


def install_resource_download():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import webapp

    original = webapp.create_app

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        if policy(config or {})["enabled"]:
            return ResourceApplication(config)
        app = original(
            paths=paths, writable_path=writable_path, config=config, read_only=read_only
        )

        @app.middleware("http")
        async def deny_restricted_legacy(request, call_next):
            authorization = request.headers.get("authorization", "")
            if authorization.startswith("Bearer "):
                try:
                    principal, _ = authenticate_token(
                        authorization[7:], app.state.config, allow_restricted=True
                    )
                except ValueError:
                    principal = None
                if (
                    principal
                    and principal.get("disclosure_mode") == "restricted-resource"
                ):
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        {
                            "error": {
                                "code": "RESOURCE_UNAVAILABLE",
                                "message": CODES["RESOURCE_UNAVAILABLE"],
                            }
                        },
                        status_code=404,
                        headers=SAFE_HEADERS,
                    )
            return await call_next(request)

        return app

    webapp.create_app = create_app
    _INSTALLED = True
