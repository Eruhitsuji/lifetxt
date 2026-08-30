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
    dry_run=False,
    output=None,
):
    """Send ``body`` as a plain-text UTF-8 email via STARTTLS SMTP.

    Shared by ``digest --format email`` and ``report send``. Returns ``True``
    once the message is sent (or, under ``dry_run``, once it would have
    been).
    """
    to_addrs = (
        split_email_addresses(to_addrs)
        if isinstance(to_addrs, str)
        else [str(addr).strip() for addr in (to_addrs or []) if str(addr).strip()]
    )
    if not to_addrs:
        raise MailDeliveryError("At least one recipient email address is required.")

    if dry_run:
        if output is not None:
            output.write(
                "[dry-run] Would email %r to %s via $%s:\n%s\n"
                % (subject, ", ".join(to_addrs), host_env, body)
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
    with smtplib.SMTP(smtp_host, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.sendmail(smtp_user, to_addrs, mime.as_string())
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
