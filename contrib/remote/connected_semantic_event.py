"""Bounded WAN semantic-event client for Remote protocol v2.

This module intentionally delegates authentication, revision/CAS, transaction
replay, and ordinary-item mutation to the existing Remote client.
"""

from __future__ import unicode_literals

import argparse
import re

from lifetxt.remote_client import get_profile, request
from lifetxt.remote_client_writes import RemoteMutationConflict, mutate_item


EVENTS = {
    "WAN_UP": "WAN restored",
    "WAN_DOWN": "WAN disconnected",
}
TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


def event_payload(event):
    """Return the fixed ordinary-E payload for one approved semantic token."""
    try:
        title = EVENTS[str(event)]
    except KeyError:
        raise ValueError("unsupported semantic event; use WAN_UP or WAN_DOWN")
    return {
        "status": "[ ]",
        "type": "E",
        "title": title,
        "details": {"tag": ["iot", "network"]},
    }


def _capability_check(profile):
    session, session_headers = request(profile, "GET", "/api/remote/v1/session")
    capabilities, capability_headers = request(
        profile, "GET", "/api/remote/v1/capabilities"
    )
    session_protocol = session_headers.get("lifetxt_negotiated_protocol")
    capability_protocol = capability_headers.get("lifetxt_negotiated_protocol")
    if session_protocol != "2" or capability_protocol != "2":
        raise RuntimeError("Remote protocol v2 negotiation is required.")
    scopes = ((session.get("principal") or {}).get("scopes") or [])
    policy = capabilities.get("mutation_policy") or {}
    if "write" not in scopes:
        raise RuntimeError("Remote principal requires the minimum write scope.")
    if "item-mutations" not in (capabilities.get("features") or []):
        raise RuntimeError("Remote server does not advertise item mutations.")
    if not policy.get("item_mutations_enabled"):
        raise RuntimeError("Remote item mutations are disabled by the server.")


def send(profile, event, transaction_id, retries=1):
    """Send one fixed event, retrying only the same payload and transaction."""
    if not TOKEN_RE.match(str(transaction_id or "")):
        raise ValueError("transaction_id must be a non-empty safe token")
    payload = {"item": event_payload(event)}
    _capability_check(profile)
    attempts = 0
    while True:
        try:
            return mutate_item(
                profile,
                "create",
                payload,
                transaction_id=str(transaction_id),
            )
        except RemoteMutationConflict:
            if attempts >= retries:
                raise
            attempts += 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="configured lifetxt Remote profile")
    parser.add_argument("event", choices=sorted(EVENTS))
    parser.add_argument("transaction_id", help="stable identity for this transition")
    parser.add_argument("--profiles-file")
    args = parser.parse_args(argv)
    result = send(
        get_profile(args.profile, args.profiles_file),
        args.event,
        args.transaction_id,
    )
    print(result)
    return 0


if __name__ == "__main__":
    main()
