"""CLI surface for journal-backed attachment transactions."""

from __future__ import unicode_literals

import os
import subprocess

from .attachment_transactions import (
    attachment_state,
    delete_attachment,
    package_directory,
    prepare_open_reference,
    put_attachment_from_path,
    reconcile_attachment,
    reference_attachment,
    reference_directory,
)
from .attachments import DIR_KEY, FILE_KEY
from .extra_common import _json_text, _write_output


def command_attachment(args, config_data):
    action = args.attachment_action
    life_path = os.path.abspath(args.path)
    stored_path = args.file
    common = dict(
        config=config_data,
        allow_symlink=bool(getattr(args, "allow_symlink", False)),
    )
    transaction = dict(transaction_id=getattr(args, "transaction_id", None))
    if action == "status":
        report = attachment_state(life_path, stored_path, **common)
    elif action == "put":
        report = put_attachment_from_path(
            life_path,
            args.id,
            stored_path,
            args.source,
            item_revision=getattr(args, "item_revision", None),
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            allow_executable=bool(getattr(args, "allow_executable", False)),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            **transaction,
            **common,
        )
    elif action == "reference":
        report = reference_attachment(
            life_path,
            args.id,
            stored_path,
            item_revision=getattr(args, "item_revision", None),
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            **transaction,
            **common,
        )
    elif action == "directory-reference":
        report = reference_directory(
            life_path,
            args.id,
            stored_path,
            item_revision=getattr(args, "item_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            **common,
        )
    elif action == "package":
        report = package_directory(
            life_path,
            args.id,
            args.source,
            stored_path,
            item_revision=getattr(args, "item_revision", None),
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            include_hidden=bool(getattr(args, "include_hidden", False)),
            **transaction,
            **common,
        )
    elif action == "reconcile":
        report = reconcile_attachment(
            life_path,
            args.id,
            stored_path,
            key=DIR_KEY if getattr(args, "key", "file") == "dir" else FILE_KEY,
            item_revision=getattr(args, "item_revision", None),
            recorded_revision=getattr(args, "recorded_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            config=config_data,
        )
    elif action == "open":
        report = prepare_open_reference(
            life_path,
            stored_path,
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            metadata_revision=getattr(args, "metadata_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            record=not bool(getattr(args, "no_record", False)),
            config=config_data,
        )
        if getattr(args, "execute", False):
            report["exit_code"] = subprocess.call(report["command"])
            report["executed"] = True
        else:
            report["executed"] = False
    elif action == "delete":
        report = delete_attachment(
            life_path,
            args.id,
            stored_path,
            item_revision=getattr(args, "item_revision", None),
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            **transaction,
            **common,
        )
    else:
        raise ValueError("Unknown attachment action: %s" % action)

    text = _json_text(report, pretty=bool(getattr(args, "pretty", False)))
    _write_output(text, getattr(args, "output", None))
    return 0
