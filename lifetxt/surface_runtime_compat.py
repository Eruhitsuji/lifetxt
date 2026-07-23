"""Compatibility edges for the public-surface runtime adapter.

Kept separate from the main adapter so the core transaction code stays focused
on request semantics.  These wrappers preserve historical call signatures and
normalize the older missing-file hash representation used by MCP.
"""

from . import mutation
from .mutation import MISSING_HASH, MutationConflict
from .surface_runtime import active_transaction, normalize_revision


_INSTALLED = False


def install_runtime_compatibility():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_mutation_signature()
    _patch_mcp_expected_hash()
    _patch_web_path_shape()
    _INSTALLED = True


def _patch_mutation_signature():
    current = mutation.apply_text_mutation
    if getattr(current, "_lifetxt_signature_compatible", False):
        return

    def compatible_apply_text_mutation(
        path,
        operation,
        expected_hash=None,
        lock_timeout=mutation.DEFAULT_LOCK_TIMEOUT,
        poll_interval=mutation.DEFAULT_POLL_INTERVAL,
        stale_lock_after=mutation.DEFAULT_STALE_LOCK_AFTER,
        encoding="utf-8",
    ):
        return current(
            path,
            operation,
            expected_hash=expected_hash,
            lock_timeout=lock_timeout,
            poll_interval=poll_interval,
            stale_lock_after=stale_lock_after,
            encoding=encoding,
        )

    compatible_apply_text_mutation._lifetxt_signature_compatible = True
    mutation.apply_text_mutation = compatible_apply_text_mutation


def _patch_mcp_expected_hash():
    from . import mcp

    original = mcp._check_expected_hash
    if getattr(original, "_lifetxt_revision_aware", False):
        return

    def check_expected_hash(context, args):
        supplied = "expected_file_hash" in args or "file_hash" in args
        raw = args.get("expected_file_hash") if "expected_file_hash" in args else args.get("file_hash")
        transaction = active_transaction()
        if transaction is not None and transaction.matches(context.writable_path):
            if not supplied:
                return original(context, args)
            expected = normalize_revision(raw, supplied=True)
            if expected != transaction.expected_hash:
                raise MutationConflict(
                    context.writable_path,
                    expected,
                    transaction.expected_hash,
                    operation="mcp.precondition",
                )
            return None
        if supplied and normalize_revision(raw, supplied=True) == MISSING_HASH:
            current = mcp.file_hash(context.writable_path)
            if current == "":
                return None
        return original(context, args)

    check_expected_hash._lifetxt_revision_aware = True
    mcp._check_expected_hash = check_expected_hash


def _patch_web_path_shape():
    from . import webapp

    original = webapp.create_app
    if getattr(original, "_lifetxt_path_shape_compatible", False):
        return

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        normalized = [paths] if isinstance(paths, str) else paths
        return original(
            paths=normalized,
            writable_path=writable_path,
            config=config,
            read_only=read_only,
        )

    create_app._lifetxt_path_shape_compatible = True
    webapp.create_app = create_app
