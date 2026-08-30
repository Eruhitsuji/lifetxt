"""Shared delivery primitives for digest, notification, and report send.

Extracted so `lifetxt report send` (#602) does not become a third
independent SMTP implementation alongside `digest --format email` and
notification email delivery. Credentials are always read from environment
variables named by the caller and are never logged; ``dry_run`` renders what
would be sent without opening a network connection.
"""

from __future__ import annotations

import json
import os
import smtplib
from email.mime.text import MIMEText
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MailDeliveryError(ValueError):
    """Raised for missing credentials or a failed delivery attempt."""


def validate_smtp_port(value):
    """Validate an explicit SMTP port, raising :class:`MailDeliveryError`.

    Returns the validated integer. This is never used to select a default
    port: omitting a port entirely (``None``) is a distinct, unvalidated
    case handled by each caller, so smtplib's own default port is preserved
    exactly for every existing configuration that does not set one.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise MailDeliveryError("SMTP port must be an integer, got %r." % (value,))
    if not (1 <= value <= 65535):
        raise MailDeliveryError(
            "SMTP port must be between 1 and 65535, got %d." % value
        )
    return value


def _deliver_smtp_message(mime, to_addrs, smtp_host, smtp_user, smtp_pass, port=None):
    """Open one STARTTLS SMTP connection, authenticate, and send ``mime``.

    The sole SMTP transport implementation shared by every mail-delivery
    caller in this project (``send_smtp_text`` and notification email in
    ``lifetxt/cli.py``) so the connect/login/send sequence is never
    duplicated. ``port=None`` reaches ``smtplib.SMTP`` exactly as it did
    before this parameter existed, preserving the existing effective
    default port for every caller that does not set one explicitly.
    """
    connect_args = (smtp_host, port) if port is not None else (smtp_host,)
    with smtplib.SMTP(*connect_args, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.sendmail(smtp_user, to_addrs, mime.as_string())


def split_email_addresses(value):
    """Split a comma-separated string, or flatten a list/tuple, into addresses."""
    if isinstance(value, (list, tuple)):
        result = []
        for part in value:
            result.extend(split_email_addresses(part))
        return result
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def resolve_smtp_credentials(host_env, user_env, pass_env):
    smtp_host = os.environ.get(host_env, "")
    smtp_user = os.environ.get(user_env, "")
    smtp_pass = os.environ.get(pass_env, "")
    if not smtp_host:
        raise MailDeliveryError(
            "Environment variable %s (SMTP host) is not set." % host_env
        )
    if not smtp_user or not smtp_pass:
        raise MailDeliveryError(
            "Environment variables %s and %s (SMTP credentials) must be set."
            % (user_env, pass_env)
        )
    return smtp_host, smtp_user, smtp_pass


def send_smtp_text(
    subject,
    body,
    to_addrs,
    host_env="LIFETXT_SMTP_HOST",
    user_env="LIFETXT_SMTP_USER",
    pass_env="LIFETXT_SMTP_PASS",
    port=None,
    dry_run=False,
    output=None,
):
    """Send ``body`` as a plain-text UTF-8 email via STARTTLS SMTP.

    Shared by ``digest --format email``, ``report send``, and notification
    email. Returns ``True`` once the message is sent (or, under ``dry_run``,
    once it would have been).

    ``port`` is an optional explicit SMTP port (e.g. ``587`` for STARTTLS
    submission), validated up front regardless of ``dry_run`` so an invalid
    value fails deterministically before any network access is attempted.
    Omitting it (``None``) preserves the existing effective default port
    unchanged for every configuration written before this parameter existed.
    """
    to_addrs = (
        split_email_addresses(to_addrs)
        if isinstance(to_addrs, str)
        else [str(addr).strip() for addr in (to_addrs or []) if str(addr).strip()]
    )
    if not to_addrs:
        raise MailDeliveryError("At least one recipient email address is required.")
    if port is not None:
        port = validate_smtp_port(port)

    if dry_run:
        if output is not None:
            port_note = " port %d" % port if port is not None else ""
            output.write(
                "[dry-run] Would email %r to %s via $%s%s:\n%s\n"
                % (subject, ", ".join(to_addrs), host_env, port_note, body)
            )
            output.flush()
        return True

    smtp_host, smtp_user, smtp_pass = resolve_smtp_credentials(
        host_env, user_env, pass_env
    )
    mime = MIMEText(body, "plain", "utf-8")
    mime["Subject"] = subject
    mime["From"] = smtp_user
    mime["To"] = ", ".join(to_addrs)
    _deliver_smtp_message(mime, to_addrs, smtp_host, smtp_user, smtp_pass, port=port)
    if output is not None:
        output.write("Sent email to %s.\n" % ", ".join(to_addrs))
        output.flush()
    return True


def send_slack_webhook(text, url_env, dry_run=False, output=None):
    """POST ``text`` to a Slack incoming webhook URL named by ``url_env``."""
    webhook_url = os.environ.get(url_env, "")
    if dry_run:
        if output is not None:
            output.write(
                "[dry-run] Would POST to Slack webhook from $%s:\n%s\n"
                % (url_env, text)
            )
            output.flush()
        return True
    if not webhook_url:
        raise MailDeliveryError("Environment variable %s is not set." % url_env)
    payload = json.dumps({"text": text}).encode("utf-8")
    request = Request(
        webhook_url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        urlopen(request, timeout=10)
    except (HTTPError, URLError) as exc:
        raise MailDeliveryError("Slack webhook request failed: %s" % exc)
    if output is not None:
        output.write("Sent to Slack webhook.\n")
        output.flush()
    return True


def append_local_file(path, text, revision=None, dry_run=False, output=None):
    """Append ``text`` to a local Markdown/text file via the semantic writer."""
    if dry_run:
        if output is not None:
            output.write("[dry-run] Would append to %s:\n%s\n" % (path, text))
            output.flush()
        return True
    from .write_operations import append_text as semantic_append_text

    semantic_append_text(
        path,
        "\n" + text + "\n",
        expected_revision=revision,
        operation="digest.append",
        create=True,
    )
    if output is not None:
        output.write("Appended to %s.\n" % path)
        output.flush()
    return True
