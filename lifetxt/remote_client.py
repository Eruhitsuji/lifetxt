"""Dependency-free Remote Safe Mode client and profile store."""
from __future__ import unicode_literals

import argparse
import json
import os
import ssl
import stat
import sys
import uuid
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .remote_access import REMOTE_PROTOCOL_CURRENT, REMOTE_PROTOCOL_MIN, REMOTE_VERSION_HEADER

PROFILE_VERSION = 3


def profile_path(path=None):
    return os.path.abspath(
        os.path.expanduser(
            path or os.environ.get("LIFETXT_REMOTE_PROFILES") or "~/.config/lifetxt/remote-profiles.json"
        )
    )


def _normalized_profile(row):
    row = dict(row or {})
    row["url"] = str(row.get("url") or "").rstrip("/")
    row["token_env"] = row.get("token_env")
    row["verify_tls"] = bool(row.get("verify_tls", True))
    try:
        version = int(row.get("protocol_version") or REMOTE_PROTOCOL_CURRENT)
    except (TypeError, ValueError):
        version = REMOTE_PROTOCOL_CURRENT
    row["protocol_version"] = max(REMOTE_PROTOCOL_MIN, min(REMOTE_PROTOCOL_CURRENT, version))
    return row


def _load(path=None):
    target = profile_path(path)
    if not os.path.exists(target):
        return {"version": PROFILE_VERSION, "profiles": {}}
    with open(target, encoding="utf-8") as handle:
        data = json.load(handle)
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict):
        profiles = {}
    migrated = OrderedDict()
    for name, row in sorted(profiles.items()):
        migrated[str(name)] = _normalized_profile(row)
    return {"version": PROFILE_VERSION, "profiles": migrated}


def _save(data, path=None):
    target = profile_path(path)
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {
        "version": PROFILE_VERSION,
        "profiles": OrderedDict(
            (str(name), _normalized_profile(row))
            for name, row in sorted((data.get("profiles") or {}).items())
        ),
    }
    from .atomic import atomic_write_text
    atomic_write_text(
        target,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return target


def set_profile(name, url, token_env=None, verify_tls=True, protocol_version=REMOTE_PROTOCOL_CURRENT, path=None):
    url = str(url).rstrip("/")
    if url.startswith("http://") and not any(value in url for value in ("127.0.0.1", "localhost", "[::1]")):
        raise ValueError("Remote profiles require HTTPS outside loopback.")
    protocol_version = int(protocol_version)
    if protocol_version < REMOTE_PROTOCOL_MIN or protocol_version > REMOTE_PROTOCOL_CURRENT:
        raise ValueError("Unsupported Remote protocol version: %s" % protocol_version)
    data = _load(path)
    data["profiles"][str(name)] = {
        "url": url,
        "token_env": token_env,
        "verify_tls": bool(verify_tls),
        "protocol_version": protocol_version,
    }
    _save(data, path)
    return dict(data["profiles"][str(name)])


def list_profiles(path=None):
    return OrderedDict(sorted(_load(path)["profiles"].items()))


def get_profile(name, path=None):
    row = _load(path)["profiles"].get(str(name))
    if not row:
        raise KeyError("Unknown remote profile: %s" % name)
    return dict(row)


def delete_profile(name, path=None):
    data = _load(path)
    removed = data["profiles"].pop(str(name), None)
    _save(data, path)
    return removed is not None


def _ssl_context(profile):
    if bool(profile.get("verify_tls", True)):
        return None
    return ssl._create_unverified_context()  # explicit profile opt-in only


def _response_protocol(headers, requested):
    raw = headers.get(REMOTE_VERSION_HEADER) or headers.get(REMOTE_VERSION_HEADER.lower())
    if raw is None:
        if int(requested) > REMOTE_PROTOCOL_MIN:
            raise RuntimeError("Remote server did not return protocol negotiation headers.")
        return REMOTE_PROTOCOL_MIN
    try:
        negotiated = int(str(raw))
    except (TypeError, ValueError):
        raise RuntimeError("Remote server returned an invalid protocol version.")
    if negotiated != int(requested):
        raise RuntimeError(
            "Remote protocol negotiation mismatch: requested %s, server returned %s."
            % (requested, negotiated)
        )
    return negotiated


def request(profile, method, route, payload=None, revision=None, params=None, timeout=20):
    profile = _normalized_profile(profile)
    url = profile["url"].rstrip("/") + "/" + route.lstrip("/")
    if params:
        url += "?" + urlencode(params, doseq=True)
    requested = int(profile.get("protocol_version") or REMOTE_PROTOCOL_CURRENT)
    headers = {
        "Accept": "application/json",
        "User-Agent": "lifetxt-remote/%s" % requested,
        "X-Request-ID": str(uuid.uuid4()),
        REMOTE_VERSION_HEADER: str(requested),
        "X-Lifetxt-Client-Time": __import__(
            "lifetxt.timezone_policy", fromlist=["utcnow"]
        ).utcnow().isoformat(),
    }
    token = os.environ.get(str(profile.get("token_env"))) if profile.get("token_env") else None
    if token:
        headers["Authorization"] = "Bearer " + token
    if revision:
        headers["If-Match"] = '"' + str(revision).strip('"') + '"'
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        kwargs = {"timeout": timeout}
        context = _ssl_context(profile)
        if context is not None:
            kwargs["context"] = context
        with urlopen(Request(url, data=body, headers=headers, method=method), **kwargs) as response:
            response_headers = dict(response.headers)
            negotiated = _response_protocol(response_headers, requested)
            value = json.loads(response.read().decode("utf-8"))
            response_headers["lifetxt_negotiated_protocol"] = negotiated
            return value, response_headers
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw)
        except ValueError:
            detail = {"error": "HTTP_%s" % exc.code, "message": raw}
        raise RuntimeError(json.dumps(detail, ensure_ascii=False))
    except URLError as exc:
        raise RuntimeError("Remote connection failed: %s" % exc)


def snapshot(profile):
    return request(profile, "GET", "/api/remote/v1/snapshot")[0]


def resource_catalog(profile):
    return request(profile, "GET", "/api/remote/v1/resources")[0]


def resource(profile, name, params=None):
    return request(profile, "GET", "/api/remote/v1/resources/%s" % str(name), params=params)[0]


def diagnostics(profile):
    return request(profile, "GET", "/api/remote/v1/diagnostics")[0]


def test_connection(profile):
    capabilities, capability_headers = request(profile, "GET", "/api/remote/v1/capabilities")
    session, session_headers = request(profile, "GET", "/api/remote/v1/session")
    requested = int(_normalized_profile(profile)["protocol_version"])
    return {
        "ok": True,
        "requested_protocol": requested,
        "negotiated_protocol": int(session_headers.get("lifetxt_negotiated_protocol", requested)),
        "capability_revision": capability_headers.get("X-Lifetxt-Remote-Capability-Revision"),
        "capabilities": capabilities,
        "session": session,
    }


def export_snapshot(profile, path):
    value = snapshot(profile)
    from .atomic import atomic_write_text
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def render_tui(value):
    lines = ["lifetxt remote (read-only)", "revision: %s" % value.get("revision", "-")]
    for row in value.get("tickets", []):
        lines.append("[ticket] %-16s %s" % (row.get("id", "-"), row.get("title") or row.get("text") or ""))
    for row in value.get("projects", []):
        lines.append("[project] %-15s %s" % (row.get("project") or row.get("id") or row.get("name") or "-", row.get("title") or ""))
    return "\n".join(lines) + "\n"


def _params(values):
    result = []
    for raw in values or []:
        key, separator, value = str(raw).partition("=")
        if not separator or not key:
            raise ValueError("Remote parameters must use key=value syntax: %s" % raw)
        result.append((key, value))
    return result


def install_remote_client_cli():
    from . import cli
    if getattr(cli, "_lifetxt_remote_client_v20", False):
        return
    original = cli.build_parser

    def build_parser():
        parser = original()
        subs = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        if "remote" in subs.choices:
            return parser
        remote = subs.add_parser("remote", help="Use authenticated Remote Safe Mode.")
        remote_subs = remote.add_subparsers(dest="remote_command", required=True)
        command = remote_subs.add_parser("profile-set")
        command.add_argument("name")
        command.add_argument("url")
        command.add_argument("--token-env")
        command.add_argument("--protocol-version", type=int, choices=range(REMOTE_PROTOCOL_MIN, REMOTE_PROTOCOL_CURRENT + 1), default=REMOTE_PROTOCOL_CURRENT)
        command.add_argument("--profiles-file")
        command.set_defaults(func=_cmd_set)
        command = remote_subs.add_parser("profile-list")
        command.add_argument("--profiles-file")
        command.set_defaults(func=_cmd_list)
        command = remote_subs.add_parser("profile-show")
        command.add_argument("name")
        command.add_argument("--profiles-file")
        command.set_defaults(func=_cmd_show)
        for command_name in ("profile-delete", "profile-remove"):
            command = remote_subs.add_parser(command_name)
            command.add_argument("name")
            command.add_argument("--profiles-file")
            command.set_defaults(func=_cmd_delete)
        for command_name, function in (
            ("test", _cmd_test),
            ("snapshot", _cmd_snapshot),
            ("tui", _cmd_tui),
            ("resources", _cmd_resources),
            ("diagnose", _cmd_diagnose),
        ):
            command = remote_subs.add_parser(command_name)
            command.add_argument("profile")
            command.add_argument("--profiles-file")
            command.set_defaults(func=function)
        command = remote_subs.add_parser("get")
        command.add_argument("profile")
        command.add_argument("resource")
        command.add_argument("--param", action="append", default=[])
        command.add_argument("--profiles-file")
        command.set_defaults(func=_cmd_get)
        command = remote_subs.add_parser("export")
        command.add_argument("profile")
        command.add_argument("path")
        command.add_argument("--profiles-file")
        command.set_defaults(func=_cmd_export)
        return parser

    cli.build_parser = build_parser
    cli._lifetxt_remote_client_v19 = True
    cli._lifetxt_remote_client_v20 = True


def _emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _cmd_set(args):
    return _emit(set_profile(args.name, args.url, args.token_env, protocol_version=args.protocol_version, path=args.profiles_file))


def _cmd_list(args):
    return _emit(list_profiles(args.profiles_file))


def _cmd_show(args):
    return _emit(get_profile(args.name, args.profiles_file))


def _cmd_delete(args):
    return _emit({"deleted": delete_profile(args.name, args.profiles_file)})


def _profile(args):
    return get_profile(args.profile, args.profiles_file)


def _cmd_test(args):
    return _emit(test_connection(_profile(args)))


def _cmd_snapshot(args):
    return _emit(snapshot(_profile(args)))


def _cmd_resources(args):
    return _emit(resource_catalog(_profile(args)))


def _cmd_get(args):
    return _emit(resource(_profile(args), args.resource, _params(args.param)))


def _cmd_diagnose(args):
    return _emit(diagnostics(_profile(args)))


def _cmd_export(args):
    return _emit({"path": export_snapshot(_profile(args), args.path)})


def _cmd_tui(args):
    sys.stdout.write(render_tui(snapshot(_profile(args))))
    return 0
