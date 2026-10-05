"""Bounded browser upload transport; local attachment transactions remain authoritative."""

import asyncio
import mimetypes
import os
import re
import stat
import threading
import unicodedata
import uuid
from urllib.parse import unquote_to_bytes, urlsplit

from . import attachment_transactions as attachments
from . import mutation
from .ids import id_key_from_config
from .parser import parse_text
from .safety_foundation import format_version_report


UPLOAD_PATH = "/api/attachments/upload"
WEB_MAX_BYTES = 10 * 1024 * 1024
RECEIVE_TIMEOUT_SECONDS = 30
MAX_ACTIVE_UPLOADS = 2
MANAGED_DIRECTORY = "web-uploads"


class UploadError(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def upload_limit(config):
    return min(
        WEB_MAX_BYTES, attachments._attachment_settings(config)["max_file_bytes"]
    )


def upload_filename(encoded):
    if not encoded or len(encoded) > 2048:
        raise UploadError("INVALID_FILENAME", "Supply a bounded encoded basename.")
    if re.search(r"%(?![0-9a-fA-F]{2})", encoded):
        raise UploadError("INVALID_FILENAME", "Filename encoding is invalid.")
    try:
        name = unquote_to_bytes(encoded).decode("utf-8", errors="strict")
    except (UnicodeError, ValueError):
        raise UploadError("INVALID_FILENAME", "Filename encoding is invalid.") from None
    name = unicodedata.normalize("NFC", name)
    if (
        len(name.encode("utf-8")) > 255
        or name in (".", "..")
        or not name
        or name != name.strip()
        or name.endswith(".")
        or any(c in name for c in "/\\:")
        or any(unicodedata.category(c).startswith("C") for c in name)
        or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", name)
    ):
        raise UploadError("INVALID_FILENAME", "Filename must be a safe basename.")
    return name


def expected_revision(headers):
    value = headers.get("x-lifetxt-expected-revision")
    if value is None:
        raise UploadError("PRECONDITION_REQUIRED", "Source revision is required.", 428)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise UploadError("INVALID_REVISION", "Supply the exact source SHA-256.")
    return value


def check_source(life_path, config, item_id, expected):
    from .webapp import is_generated_path

    if not life_path or is_generated_path(life_path, config):
        raise UploadError("NOT_WRITABLE", "The selected source is not writable.", 403)
    snapshot = mutation.read_text_snapshot(life_path)
    if snapshot.content_hash != expected:
        raise UploadError(
            "REVISION_CONFLICT", "Refresh the source before retrying.", 409
        )
    if format_version_report(snapshot.text)["state"] == "unsupported":
        raise UploadError(
            "UNSUPPORTED_FORMAT", "Migrate the source before writing.", 409
        )
    key = id_key_from_config(config)
    items, diagnostics = parse_text(snapshot.text, id_key=key, check_references=False)
    if any(d.severity == "error" for d in diagnostics):
        raise UploadError(
            "INVALID_SOURCE", "The source requires repair before writing.", 409
        )
    matches = [item for item in items if item_id in item.details.get(key, [])]
    if len(matches) != 1:
        raise UploadError(
            "ITEM_NOT_WRITABLE", "Select one existing writable item.", 404
        )


def check_transport(request):
    headers = request.headers
    for key in (
        "content-length",
        "content-type",
        "content-encoding",
        "origin",
        "x-lifetxt-upload",
        "x-lifetxt-item-id",
        "x-lifetxt-filename",
        "x-lifetxt-expected-revision",
    ):
        if len(headers.getlist(key)) > 1:
            raise UploadError(
                "INVALID_REQUEST", "Duplicate upload headers are unsupported."
            )
    if request.query_params:
        raise UploadError("INVALID_REQUEST", "Upload query parameters are unsupported.")
    if headers.get("x-lifetxt-upload") != "1":
        raise UploadError(
            "UPLOAD_MARKER_REQUIRED", "Upload request marker is required.", 403
        )
    origin = headers.get("origin")
    if origin:
        try:
            parsed = urlsplit(origin)
            incoming = urlsplit(str(request.url))
            port = lambda u: u.port or (443 if u.scheme == "https" else 80)
            same = (
                parsed.scheme in ("http", "https")
                and parsed.scheme == incoming.scheme
                and parsed.hostname == incoming.hostname
                and port(parsed) == port(incoming)
                and not parsed.username
                and not parsed.password
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            same = False
        if not same:
            raise UploadError("ORIGIN_FORBIDDEN", "Upload origin is not allowed.", 403)
    if headers.get("sec-fetch-site") in ("cross-site", "same-site"):
        raise UploadError(
            "ORIGIN_FORBIDDEN", "Uploads require same-origin requests.", 403
        )
    if headers.get("content-type", "").lower() != "application/octet-stream":
        raise UploadError(
            "UNSUPPORTED_MEDIA_TYPE", "Send raw application/octet-stream bytes.", 415
        )
    if headers.get("content-encoding", "identity").lower() != "identity":
        raise UploadError(
            "UNSUPPORTED_ENCODING", "Compressed request bodies are unsupported.", 415
        )


async def read_upload(request, limit):
    length = request.headers.get("content-length")
    if length is not None:
        if not re.fullmatch(r"[0-9]{1,12}", length):
            raise UploadError("INVALID_LENGTH", "Content length is invalid.")
        if int(length) > limit:
            raise UploadError("UPLOAD_TOO_LARGE", "File exceeds the upload limit.", 413)
    buffer, total = bytearray(), 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise UploadError("UPLOAD_TOO_LARGE", "File exceeds the upload limit.", 413)
        if chunk:
            buffer.extend(chunk)
    if length is not None and total != int(length):
        raise UploadError("INVALID_LENGTH", "Content length does not match the body.")
    return bytes(buffer)


def content_type(name, payload, config):
    # No client MIME assertion is trusted; executable magic is refused even with .txt.
    if payload.startswith(
        (
            b"MZ",
            b"\x7fELF",
            b"#!",
            b"\xca\xfe\xba\xbe",
            b"\xca\xfe\xba\xbf",
            b"\xbe\xba\xfe\xca",
            b"\xbf\xba\xfe\xca",
            b"\xfe\xed\xfa",
            b"\xce\xfa\xed",
            b"\xcf\xfa\xed",
        )
    ):
        raise UploadError(
            "CONTENT_FORBIDDEN", "Executable content is not allowed.", 415
        )
    attachments._reject_executable_target(name, payload, False)
    detected = "application/octet-stream"
    for magic, mime in (
        (b"%PDF-", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
        (b"PK\x03\x04", "application/zip"),
        (b"PK\x05\x06", "application/zip"),
    ):
        if payload.startswith(magic):
            detected = mime
            break
    if detected == "application/octet-stream" and b"\x00" not in payload:
        try:
            payload.decode("utf-8", errors="strict")
            detected = "text/plain"
        except UnicodeError:
            pass
    guessed = mimetypes.guess_type(name)[0]
    # Apply deny/allow policy to both filename-associated MIME and observed content.
    # This is conservative classification, not a proof that a document is harmless.
    for mime in {detected, guessed} - {None}:
        attachments._enforce_mime_policy(config, name, mime)
    return detected


def managed_target(life_path, config, attachment_id, name):
    root = os.path.abspath(attachments._attachment_root(config, life_path))
    namespace = os.path.join(root, MANAGED_DIRECTORY)
    # Walk/create directories without accepting any existing symlink or special file.
    parts = []
    cursor = namespace
    while True:
        parts.append(cursor)
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    for part in reversed(parts):
        try:
            os.mkdir(part, mode=0o700)
        except FileExistsError:
            pass
        mode = os.lstat(part).st_mode
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            raise UploadError(
                "STORAGE_UNAVAILABLE", "Managed storage is unavailable.", 409
            )
    extension = os.path.splitext(name)[1].lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,12}", extension):
        extension = ""
    target = os.path.join(namespace, attachment_id + extension)
    if os.path.lexists(target):
        raise UploadError(
            "ATTACHMENT_COLLISION", "Retry the upload with a fresh revision.", 409
        )
    relative = os.path.relpath(target, os.path.dirname(os.path.abspath(life_path)))
    attachments.resolve_attachment_target(life_path, relative, root=root)
    return relative


def commit_upload(life_path, config, item_id, revision, name, payload):
    check_source(life_path, config, item_id, revision)
    mime = content_type(name, payload, config)
    attachment_id = uuid.uuid4().hex
    stored = managed_target(life_path, config, attachment_id, name)
    result = attachments.put_attachment(
        life_path,
        item_id,
        stored,
        payload,
        item_revision=revision,
        attachment_expected_revision=mutation.MISSING_HASH,
        config=config,
        require_revisions=True,
    )
    # Explicit allowlist: never forward domain paths, values, targets or journal fields.
    return {
        "contract_version": "1",
        "attachment_id": attachment_id,
        "display_name": name,
        "size_bytes": len(payload),
        "media_type": mime,
        "source_revision": result["item_revision"],
        "attachment_revision": result["attachment_revision"],
    }


def register_upload_routes(app):
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool
    from starlette.requests import ClientDisconnect
    from .schema_extensions_v32 import upload_receipt_schema

    # A process-local gate bounds body buffers and transaction work together.
    gate = threading.BoundedSemaphore(MAX_ACTIVE_UPLOADS)

    @app.get(UPLOAD_PATH)
    async def upload_policy():
        from .webapp import is_generated_path

        return JSONResponse(
            content={
                "contract_version": "1",
                "max_upload_bytes": upload_limit(app.state.config),
                "receive_timeout_seconds": RECEIVE_TIMEOUT_SECONDS,
                "max_active_uploads_per_process": MAX_ACTIVE_UPLOADS,
                "upload_enabled": bool(
                    not app.state.read_only
                    and app.state.writable_path
                    and not is_generated_path(app.state.writable_path, app.state.config)
                ),
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post(
        UPLOAD_PATH,
        status_code=201,
        openapi_extra={
            "parameters": [
                {
                    "name": name,
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string"},
                }
                for name in (
                    "X-Lifetxt-Upload",
                    "X-Lifetxt-Item-Id",
                    "X-Lifetxt-Filename",
                    "X-Lifetxt-Expected-Revision",
                )
            ],
            "requestBody": {
                "content": {
                    "application/octet-stream": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "Path-free upload receipt",
                    "content": {
                        "application/json": {"schema": upload_receipt_schema()}
                    },
                }
            },
        },
    )
    async def upload(request: Request):
        acquired = False
        commit_task = None
        try:
            if app.state.read_only:
                raise UploadError("READ_ONLY", "Uploads are disabled.", 403)
            check_transport(request)
            revision = expected_revision(request.headers)
            item_id = request.headers.get("x-lifetxt-item-id", "")
            if not re.fullmatch(r"[!-~]{1,128}", item_id):
                raise UploadError("INVALID_ITEM_ID", "Supply one compact item ID.")
            name = upload_filename(request.headers.get("x-lifetxt-filename"))
            acquired = gate.acquire(blocking=False)
            if not acquired:
                raise UploadError(
                    "UPLOAD_BUSY", "Retry after another upload completes.", 429
                )
            await run_in_threadpool(
                check_source,
                app.state.writable_path,
                app.state.config,
                item_id,
                revision,
            )
            payload = await asyncio.wait_for(
                read_upload(request, upload_limit(app.state.config)),
                RECEIVE_TIMEOUT_SECONDS,
            )
            # Request cancellation must not release the buffer/transaction gate
            # while a synchronous journal-backed commit is still running.
            commit_task = asyncio.create_task(
                run_in_threadpool(
                    commit_upload,
                    app.state.writable_path,
                    app.state.config,
                    item_id,
                    revision,
                    name,
                    payload,
                )
            )
            receipt = await asyncio.shield(commit_task)
            return JSONResponse(
                status_code=201, content=receipt, headers={"Cache-Control": "no-store"}
            )
        except UploadError as exc:
            status, code, message = exc.status, exc.code, exc.message
        except mutation.MutationConflict:
            status, code, message = (
                409,
                "REVISION_CONFLICT",
                "Refresh the source before retrying.",
            )
        except (asyncio.TimeoutError, ClientDisconnect):
            status, code, message = 408, "UPLOAD_INCOMPLETE", "Upload did not complete."
        except attachments.AttachmentTransactionError:
            status, code, message = (
                415,
                "CONTENT_FORBIDDEN",
                "Attachment content or MIME policy rejected the upload.",
            )
        except Exception:
            # Journal evidence remains available to the local operator; never leak it.
            status, code, message = (
                503,
                "UPLOAD_FAILED",
                "Upload failed; inspect local transaction recovery before retrying.",
            )
        finally:
            if acquired:
                if commit_task is not None and not commit_task.done():

                    def completed(task):
                        if not task.cancelled():
                            task.exception()
                        gate.release()

                    commit_task.add_done_callback(completed)
                else:
                    gate.release()
        return JSONResponse(
            status_code=status,
            content={"error": code, "message": message},
            headers={"Cache-Control": "no-store"},
        )
