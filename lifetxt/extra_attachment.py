"""CLI surface for journal-backed attachment transactions."""

from __future__ import unicode_literals

import json
import os
import sys

from .attachment_transactions import (
    attachment_state, delete_attachment, put_attachment, reference_attachment,
)
from .extra_common import _json_text, _write_output


def command_attachment(args, config_data):
    action = args.attachment_action
    life_path = os.path.abspath(args.path)
    stored_path = args.file
    common = dict(
        config=config_data,
        allow_symlink=bool(getattr(args, "allow_symlink", False)),
    )
    if action == "status":
        report = attachment_state(life_path, stored_path, **common)
    elif action == "put":
        if not getattr(args, "source", None):
            raise ValueError("attachment put requires --source FILE.")
        with open(args.source, "rb") as handle:
            payload = handle.read()
        report = put_attachment(
            life_path,
            args.id,
            stored_path,
            payload,
            item_revision=getattr(args, "item_revision", None),
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            allow_executable=bool(getattr(args, "allow_executable", False)),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            **common
        )
    elif action == "reference":
        report = reference_attachment(
            life_path,
            args.id,
            stored_path,
            item_revision=getattr(args, "item_revision", None),
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            **common
        )
    elif action == "delete":
        report = delete_attachment(
            life_path,
            args.id,
            stored_path,
            item_revision=getattr(args, "item_revision", None),
            attachment_expected_revision=getattr(args, "attachment_revision", None),
            require_revisions=bool(getattr(args, "require_revisions", False)),
            **common
        )
    else:
        raise ValueError("Unknown attachment action: %s" % action)

    text = _json_text(report, pretty=bool(getattr(args, "pretty", False)))
    _write_output(text, getattr(args, "output", None))
    return 0
