"""Compensated multi-target mutation transactions.

A filesystem cannot provide a portable atomic commit across unrelated files.  This
module therefore provides the strongest dependency-free contract available:
ordered locks, revision checks for every target before any write, fully staged
replacements, verified commits, and reverse-order compensation if a later target
fails.  Rollback failure is never hidden.
"""

from __future__ import unicode_literals

import contextlib
import json
import os
from collections import namedtuple

from . import mutation
from .mutation import MISSING_HASH, FileLock, MutationConflict


BytesSnapshot = namedtuple("BytesSnapshot", "path data content_hash exists")
TargetResult = namedtuple(
    "TargetResult", "path kind before_hash after_hash changed created deleted"
)
MultiTargetResult = namedtuple(
    "MultiTargetResult",
    "operation targets compensated transaction_id journal_path recovery_required",
)
MultiTargetResult.__new__.__defaults__ = (None, None, False)


class MultiTargetError(RuntimeError):
    pass


class MultiTargetCommitError(MultiTargetError):
    def __init__(self, operation, cause, rollback_errors=None):
        self.operation = operation
        self.cause = cause
        self.rollback_errors = list(rollback_errors or [])
        message = "%s failed: %s" % (operation, cause)
        if self.rollback_errors:
            message += "; compensation also failed: %s" % "; ".join(
                str(error) for error in self.rollback_errors
            )
        else:
            message += "; committed targets were compensated."
        MultiTargetError.__init__(self, message)


class TargetPlan(object):
    """One staged target in a multi-target operation.

    ``kind`` is ``text``, ``json``, or ``bytes``.  A transform receives the
    current decoded value and returns its replacement.  ``delete=True`` removes
    the target after revision validation and ignores the transform result.
    """

    def __init__(
        self,
        path,
        transform,
        expected_hash,
        kind="text",
        create=False,
        default=None,
        validate=None,
        delete=False,
    ):
        if expected_hash is None or str(expected_hash).strip() == "":
            raise ValueError("Multi-target plans require expected_hash.")
        if kind not in ("text", "json", "bytes"):
            raise ValueError("Unsupported target kind: %s" % kind)
        if not callable(transform) and not delete:
            raise TypeError("TargetPlan.transform must be callable unless delete=True.")
        if validate is not None and not callable(validate):
            raise TypeError("TargetPlan.validate must be callable.")
        self.path = os.path.abspath(path)
        self.transform = transform
        self.expected_hash = expected_hash
        self.kind = kind
        self.create = bool(create)
        self.default = default
        self.validate = validate
        self.delete = bool(delete)


def apply_multi_target(
    plans,
    operation="multi_target",
    lock_timeout=5.0,
    stale_lock_after=300.0,
    failure_hook=None,
    journal_dir=None,
    journal=True,
    transaction_id=None,
    config=None,
    transaction_policy=None,
):
    """Stage and commit all plans, compensating any partial commit on failure."""
    plans = list(plans or [])
    if not plans:
        raise ValueError("At least one target plan is required.")
    paths = [plan.path for plan in plans]
    if len(paths) != len(set(paths)):
        raise ValueError("A multi-target operation cannot contain duplicate paths.")
    ordered_paths = sorted(paths)
    plan_by_path = dict((plan.path, plan) for plan in plans)
    staged = []
    committed = []
    journal_handle = None
    with contextlib.ExitStack() as stack:
        for path in ordered_paths:
            stack.enter_context(
                FileLock(
                    path,
                    operation=operation,
                    timeout=lock_timeout,
                    stale_after=stale_lock_after,
                )
            )
        for path in ordered_paths:
            staged.append(_stage(plan_by_path[path], operation))
        if journal:
            from .transaction_journal import journal_directory, prepare

            resolved_journal_dir = journal_dir or journal_directory(
                writable_path=ordered_paths[0]
            )
            journal_handle = prepare(
                operation,
                staged,
                resolved_journal_dir,
                transaction_id_value=transaction_id,
                config=config,
                policy=transaction_policy,
            )
            journal_handle.set_state("committing")
        try:
            for index, row in enumerate(staged):
                if failure_hook is not None:
                    failure_hook("before_commit", row["plan"], index)
                from .transaction_policy import fault_point

                fault_point(
                    "before_target_commit",
                    path=row["plan"].path,
                    index=index,
                    operation=operation,
                )
                _commit_staged(row, operation)
                fault_point(
                    "after_target_commit",
                    path=row["plan"].path,
                    index=index,
                    operation=operation,
                )
                committed.append(row)
                if journal_handle is not None:
                    journal_handle.mark_target(index, commit_state="committed")
                if failure_hook is not None:
                    failure_hook("after_commit", row["plan"], index)
                _verify_staged(row, operation)
                if journal_handle is not None:
                    journal_handle.mark_target(index, commit_state="verified")
        except Exception as exc:
            if journal_handle is not None:
                journal_handle.set_state("compensating", error=exc)
            rollback_errors = _compensate(committed, journal_handle=journal_handle)
            if journal_handle is not None:
                journal_handle.set_state(
                    "compensated" if not rollback_errors else "recovery_required",
                    error=None
                    if not rollback_errors
                    else "; ".join(str(error) for error in rollback_errors),
                )
            raise MultiTargetCommitError(operation, exc, rollback_errors)
        if journal_handle is not None:
            journal_handle.set_state("committed")
    results = []
    for row in staged:
        before = row["before"]
        results.append(
            TargetResult(
                row["plan"].path,
                row["plan"].kind,
                before.content_hash,
                row["after_hash"],
                row["changed"],
                not before.exists and not row["plan"].delete,
                row["plan"].delete and before.exists,
            )
        )
    return MultiTargetResult(
        operation,
        results,
        False,
        None if journal_handle is None else journal_handle.load()["transaction_id"],
        None if journal_handle is None else journal_handle.path,
        False,
    )


def text_plan(path, transform, expected_hash, create=False, default="", validate=None):
    return TargetPlan(
        path,
        transform,
        expected_hash,
        kind="text",
        create=create,
        default=default,
        validate=validate,
    )


def json_plan(
    path, transform, expected_hash, create=False, default=None, validate=None
):
    return TargetPlan(
        path,
        transform,
        expected_hash,
        kind="json",
        create=create,
        default={} if default is None else default,
        validate=validate,
    )


def bytes_plan(
    path, transform, expected_hash, create=False, default=b"", validate=None
):
    return TargetPlan(
        path,
        transform,
        expected_hash,
        kind="bytes",
        create=create,
        default=default,
        validate=validate,
    )


def delete_plan(path, expected_hash, kind="bytes"):
    return TargetPlan(
        path,
        lambda current: current,
        expected_hash,
        kind=kind,
        create=False,
        delete=True,
    )


def timer_and_item_transaction(
    timer_path,
    timer_transform,
    timer_expected_hash,
    item_path,
    item_transform,
    item_expected_hash,
    operation="timer_and_item",
    timer_delete=False,
    journal_dir=None,
    transaction_id=None,
    config=None,
):
    """Commit timer JSON state and associated life.txt semantic change together."""
    timer_plan = (
        delete_plan(timer_path, timer_expected_hash, kind="json")
        if timer_delete
        else json_plan(
            timer_path,
            timer_transform,
            timer_expected_hash,
            create=timer_expected_hash == MISSING_HASH,
            default={},
        )
    )
    return apply_multi_target(
        [
            timer_plan,
            text_plan(
                item_path,
                item_transform,
                item_expected_hash,
                create=item_expected_hash == MISSING_HASH,
                default="",
            ),
        ],
        operation=operation,
        journal_dir=journal_dir,
        transaction_id=transaction_id,
        config=config,
    )


def attachment_and_item_transaction(
    attachment_plan,
    item_path,
    item_transform,
    item_expected_hash,
    operation="attachment_and_item",
    journal_dir=None,
    transaction_id=None,
    config=None,
):
    """Commit an attachment create/update/delete and its life.txt reference together."""
    if not isinstance(attachment_plan, TargetPlan) or attachment_plan.kind != "bytes":
        raise TypeError("attachment_plan must be a bytes TargetPlan.")
    return apply_multi_target(
        [
            attachment_plan,
            text_plan(
                item_path,
                item_transform,
                item_expected_hash,
                create=item_expected_hash == MISSING_HASH,
                default="",
            ),
        ],
        operation=operation,
        journal_dir=journal_dir,
        transaction_id=transaction_id,
        config=config,
    )


def _stage(plan, operation):
    before = _snapshot(plan)
    if not before.exists and not plan.create:
        raise FileNotFoundError(plan.path)
    if plan.expected_hash != before.content_hash:
        raise MutationConflict(
            plan.path,
            plan.expected_hash,
            before.content_hash,
            operation=operation + ".precondition",
        )
    if plan.delete:
        replacement = None
        replacement_bytes = None
        after_hash = MISSING_HASH
    elif plan.kind == "bytes":
        current = before.data if before.exists else plan.default
        replacement = plan.transform(current)
        if not isinstance(replacement, bytes):
            raise TypeError("Bytes transform must return bytes for %s." % plan.path)
        replacement_bytes = replacement
        after_hash = mutation.hash_bytes(replacement_bytes)
    elif plan.kind == "json":
        current_text = before.text if before.exists else ""
        if current_text.strip():
            try:
                current = json.loads(current_text)
            except ValueError as exc:
                raise MultiTargetError("Cannot parse %s as JSON: %s" % (plan.path, exc))
        else:
            current = plan.default
        replacement = plan.transform(current)
        if plan.validate is not None:
            result = plan.validate(replacement)
            if result is False:
                raise ValueError("Validator rejected %s." % plan.path)
        replacement_text = (
            json.dumps(replacement, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        replacement_bytes = mutation._encode_text(
            replacement_text, encoding="utf-8", bom=False
        )
        after_hash = mutation.hash_bytes(replacement_bytes)
    else:
        current = before.text if before.exists else (plan.default or "")
        replacement = plan.transform(current)
        if not isinstance(replacement, str):
            raise TypeError("Text transform must return text for %s." % plan.path)
        if plan.validate is not None:
            result = plan.validate(replacement)
            if result is False:
                raise ValueError("Validator rejected %s." % plan.path)
        replacement_bytes = mutation._encode_text(
            replacement,
            encoding=before.encoding if before.exists else "utf-8",
            bom=before.bom if before.exists else False,
        )
        after_hash = mutation.hash_bytes(replacement_bytes)
    changed = (plan.delete and before.exists) or (
        not plan.delete and (not before.exists or before.content_hash != after_hash)
    )
    return {
        "plan": plan,
        "before": before,
        "replacement": replacement,
        "replacement_bytes": replacement_bytes,
        "after_hash": after_hash,
        "changed": changed,
    }


def _snapshot(plan):
    if plan.kind in ("text", "json"):
        return mutation.read_text_snapshot(plan.path, allow_missing=True)
    try:
        with open(plan.path, "rb") as handle:
            data = handle.read()
    except FileNotFoundError:
        return BytesSnapshot(plan.path, b"", MISSING_HASH, False)
    return BytesSnapshot(plan.path, data, mutation.hash_bytes(data), True)


def _commit_staged(row, operation):
    if not row["changed"]:
        return
    plan = row["plan"]
    if plan.delete:
        from .transaction_policy import fault_point

        fault_point("before_target_delete", path=plan.path, operation=operation)
        try:
            os.unlink(plan.path)
        except FileNotFoundError:
            pass
        _fsync_parent(plan.path)
        fault_point("after_target_delete", path=plan.path, operation=operation)
    else:
        mutation.atomic_write_bytes(plan.path, row["replacement_bytes"])


def _verify_staged(row, operation):
    plan = row["plan"]
    from .transaction_policy import fault_point

    fault_point("before_target_verify", path=plan.path, operation=operation)
    latest = _snapshot(plan)
    if latest.content_hash != row["after_hash"]:
        raise MutationConflict(
            plan.path,
            row["after_hash"],
            latest.content_hash,
            operation=operation + ".verification",
        )
    fault_point("after_target_verify", path=plan.path, operation=operation)


def _compensate(committed, journal_handle=None):
    errors = []
    target_indexes = {}
    if journal_handle is not None:
        try:
            target_indexes = dict(
                (target["path"], int(target["index"]))
                for target in journal_handle.load().get("targets", [])
            )
        except Exception:
            target_indexes = {}
    for row in reversed(committed):
        plan = row["plan"]
        index = target_indexes.get(plan.path)
        before = row["before"]
        try:
            if before.exists:
                if plan.kind in ("text", "json"):
                    payload = mutation._encode_text(
                        before.text, encoding=before.encoding, bom=before.bom
                    )
                else:
                    payload = before.data
                from .transaction_policy import fault_point

                fault_point(
                    "before_compensation_target_write",
                    path=plan.path,
                    operation="multi_target.compensate",
                )
                mutation.atomic_write_bytes(plan.path, payload)
                fault_point(
                    "after_compensation_target_write",
                    path=plan.path,
                    operation="multi_target.compensate",
                )
            else:
                try:
                    os.unlink(plan.path)
                except FileNotFoundError:
                    pass
                _fsync_parent(plan.path)
            from .transaction_policy import fault_point

            fault_point(
                "before_compensation_verify",
                path=plan.path,
                operation="multi_target.compensate",
            )
            restored = _snapshot(plan)
            if restored.content_hash != before.content_hash:
                raise MultiTargetError(
                    "Compensation verification failed for %s." % plan.path
                )
            fault_point(
                "after_compensation_verify",
                path=plan.path,
                operation="multi_target.compensate",
            )
            if journal_handle is not None and index is not None:
                journal_handle.mark_target(index, compensation_state="verified")
        except Exception as exc:
            if journal_handle is not None and index is not None:
                journal_handle.mark_target(
                    index, compensation_state="failed", error=exc
                )
            errors.append(exc)
    return errors


def _fsync_parent(path):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
