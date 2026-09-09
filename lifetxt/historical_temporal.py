"""Read-only Git evidence for historical temporal-thread reconstruction."""

from __future__ import unicode_literals

import datetime
import os
import re
import subprocess
from collections import OrderedDict

from .ids import duplicate_id_diagnostics
from .links import reference_diagnostics
from .parser import parse_text
from .temporal_thread import temporal_thread


GIT_TIMEOUT_SECONDS = 15
MAX_HISTORICAL_FILE_BYTES = 16 * 1024 * 1024
MAX_HISTORICAL_TOTAL_BYTES = 64 * 1024 * 1024
MAX_HISTORY_COMMITS = 100000
RFC3339_OFFSET_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _git(repo_root, arguments, text=True):
    command = ["git", "-c", "core.pager=cat"] + list(arguments)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    try:
        return subprocess.run(
            command,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            timeout=GIT_TIMEOUT_SECONDS,
            env=env,
        )
    except FileNotFoundError:
        raise ValueError(
            "git executable not found; historical temporal reads require Git."
        )
    except subprocess.TimeoutExpired:
        raise ValueError("Git historical evidence lookup timed out.")
    except OSError as exc:
        raise ValueError("Git historical evidence lookup failed: %s" % exc)


def _git_error(result, action):
    detail = result.stderr.strip() if isinstance(result.stderr, str) else ""
    if detail:
        raise ValueError("%s: %s" % (action, detail))
    raise ValueError(action)


def _probe_directory(path):
    candidate = os.path.abspath(path)
    if not os.path.isdir(candidate):
        candidate = os.path.dirname(candidate)
    while candidate and not os.path.isdir(candidate):
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    return candidate or os.getcwd()


def resolve_git_inputs(paths):
    """Resolve input paths to one repository and stable tree-relative paths."""
    values = [str(path) for path in paths or []]
    if not values:
        raise ValueError("Historical temporal reads require at least one input path.")
    if any(path == "-" for path in values):
        raise ValueError("Historical temporal reads cannot use stdin.")

    repo_root = None
    resolved = []
    for source_path in values:
        absolute = os.path.abspath(source_path)
        probe = _probe_directory(absolute)
        result = _git(probe, ["rev-parse", "--show-toplevel"])
        if result.returncode != 0:
            _git_error(result, "Input %r is not inside a Git repository" % source_path)
        current_root = os.path.realpath(result.stdout.strip())
        if repo_root is None:
            repo_root = current_root
        elif os.path.normcase(current_root) != os.path.normcase(repo_root):
            raise ValueError(
                "Historical temporal inputs must belong to one Git repository."
            )
        relative = os.path.relpath(absolute, current_root)
        if relative == os.pardir or relative.startswith(os.pardir + os.sep):
            raise ValueError(
                "Historical input escapes its Git repository: %s" % source_path
            )
        resolved.append(
            OrderedDict(
                (
                    ("source_path", source_path),
                    ("tree_path", relative.replace(os.sep, "/")),
                )
            )
        )
    return repo_root, resolved


def resolve_commit(repo_root, revision):
    value = str(revision or "").strip()
    if not value:
        raise ValueError("A Git revision is required.")
    if value.startswith("-"):
        raise ValueError("Git revision must not begin with '-'.")
    result = _git(
        repo_root,
        ["rev-parse", "--verify", "--end-of-options", value + "^{commit}"],
    )
    if result.returncode != 0:
        raise ValueError("Unknown or non-commit Git revision %r." % value)
    resolved = result.stdout.strip()
    if len(resolved) not in (40, 64):
        raise ValueError("Git did not resolve %r to a full commit SHA." % value)
    return resolved


def _read_blob(repo_root, commit, tree_path):
    object_name = "%s:%s" % (commit, tree_path)
    kind = _git(repo_root, ["cat-file", "-t", object_name])
    if kind.returncode != 0:
        return None
    if kind.stdout.strip() != "blob":
        raise ValueError(
            "Historical input %r is not a file at revision %s." % (tree_path, commit)
        )
    size_result = _git(repo_root, ["cat-file", "-s", object_name])
    if size_result.returncode != 0:
        _git_error(size_result, "Could not size historical input %r" % tree_path)
    try:
        size = int(size_result.stdout.strip())
    except ValueError:
        raise ValueError("Git returned an invalid blob size for %r." % tree_path)
    if size > MAX_HISTORICAL_FILE_BYTES:
        raise ValueError(
            "Historical input %r exceeds the %d-byte per-file limit."
            % (tree_path, MAX_HISTORICAL_FILE_BYTES)
        )
    content = _git(repo_root, ["show", object_name], text=False)
    if content.returncode != 0:
        raise ValueError("Could not read historical input %r." % tree_path)
    if len(content.stdout) != size:
        raise ValueError("Historical input %r changed during Git read." % tree_path)
    try:
        return content.stdout.decode("utf-8-sig"), size
    except UnicodeDecodeError:
        raise ValueError("Historical input %r is not valid UTF-8." % tree_path)


def _set_source(items, diagnostics, source):
    for item in items:
        item.source = source
    for diagnostic in diagnostics:
        diagnostic.source = source


def historical_snapshot(paths, revision, key="id", resolved_commit=None, metadata=None):
    """Parse only tracked bytes from one exact commit.

    Missing paths are reported as incomplete evidence and never filled from
    the working tree. At least one tracked input must exist.
    """
    repo_root, inputs = resolve_git_inputs(paths)
    commit = resolved_commit or resolve_commit(repo_root, revision)
    if (
        resolved_commit
        and resolve_commit(repo_root, resolved_commit) != resolved_commit
    ):
        raise ValueError("Resolved historical commit is not available.")

    items = []
    diagnostics = []
    loaded_paths = []
    missing_paths = []
    total_bytes = 0
    for entry in inputs:
        blob = _read_blob(repo_root, commit, entry["tree_path"])
        if blob is None:
            missing_paths.append(entry["tree_path"])
            continue
        text, blob_size = blob
        total_bytes += blob_size
        if total_bytes > MAX_HISTORICAL_TOTAL_BYTES:
            raise ValueError(
                "Historical inputs exceed the %d-byte aggregate limit."
                % MAX_HISTORICAL_TOTAL_BYTES
            )
        path_items, path_diagnostics = parse_text(
            text, id_key=key, check_ids=False, check_references=False
        )
        _set_source(path_items, path_diagnostics, entry["tree_path"])
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
        loaded_paths.append(entry["tree_path"])

    if not loaded_paths:
        raise ValueError(
            "None of the requested input paths exist at Git revision %s." % commit
        )
    diagnostics.extend(duplicate_id_diagnostics(items, key=key))
    diagnostics.extend(reference_diagnostics(items, key=key))

    limitations = ["missing_at_revision:%s" % path for path in missing_paths]
    historical = OrderedDict(
        (
            ("mode", "git_exact_revision"),
            ("requested_revision", str(revision)),
            ("resolved_commit", commit),
            ("requested_paths", [entry["tree_path"] for entry in inputs]),
            ("loaded_paths", loaded_paths),
            ("missing_paths", missing_paths),
            ("evidence_complete", not missing_paths),
            ("limitations", limitations),
        )
    )
    if metadata:
        historical = OrderedDict(metadata)
        historical["requested_paths"] = [entry["tree_path"] for entry in inputs]
        historical["loaded_paths"] = loaded_paths
        historical["missing_paths"] = missing_paths
        historical["evidence_complete"] = bool(
            historical.get("history_complete", True) and not missing_paths
        )
        historical["limitations"] = (
            list(historical.get("limitations", [])) + limitations
        )
    return OrderedDict(
        (
            ("repo_root", repo_root),
            ("items", items),
            ("diagnostics", diagnostics),
            ("historical", historical),
        )
    )


def _target(items, target_id, key):
    matches = [
        item
        for item in items
        if any(str(value) == str(target_id) for value in item.details.get(key, []))
    ]
    if len(matches) > 1:
        raise ValueError("Historical temporal target %r is ambiguous." % target_id)
    return matches[0] if matches else None


def thread_from_snapshot(
    snapshot, target_id, today, key="id", allow_missing_target=False, **bounds
):
    errors = [
        diagnostic
        for diagnostic in snapshot["diagnostics"]
        if diagnostic.severity == "error"
    ]
    if errors:
        first = errors[0]
        raise ValueError(
            "Historical input has %s at %s:%s."
            % (first.code, first.source or "(unknown source)", first.line or "?")
        )
    target = _target(snapshot["items"], target_id, key)
    if target is None:
        if allow_missing_target:
            return None
        raise ValueError(
            "No item with id %r exists in the selected historical inputs." % target_id
        )
    result = temporal_thread(snapshot["items"], target, today, key=key, **bounds)
    result["historical"] = snapshot["historical"]
    return result


def historical_temporal_thread(paths, target_id, today, revision, key="id", **bounds):
    snapshot = historical_snapshot(paths, revision, key=key)
    return thread_from_snapshot(snapshot, target_id, today, key=key, **bounds)


def parse_cutoff(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("An offset-aware RFC3339 --as-of timestamp is required.")
    if not RFC3339_OFFSET_RE.match(text):
        raise ValueError("--as-of must be an offset-aware RFC3339 timestamp.")
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.datetime.fromisoformat(candidate)
    except ValueError:
        raise ValueError("--as-of must be an offset-aware RFC3339 timestamp.")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            "--as-of must be offset-aware and include Z or an explicit UTC offset."
        )
    return parsed


def select_revision_as_of(paths, cutoff, ref=None):
    """Select the newest reachable committer timestamp at or before cutoff."""
    repo_root, _inputs = resolve_git_inputs(paths)
    cutoff_value = parse_cutoff(cutoff)
    requested_ref = str(ref or "HEAD")
    root = resolve_commit(repo_root, requested_ref)
    history = _git(
        repo_root,
        [
            "rev-list",
            "--timestamp",
            "--max-count=%d" % (MAX_HISTORY_COMMITS + 1),
            root,
        ],
    )
    if history.returncode != 0:
        _git_error(history, "Could not enumerate Git history")
    rows = [line.split() for line in history.stdout.splitlines() if line.strip()]
    if len(rows) > MAX_HISTORY_COMMITS:
        raise ValueError(
            "Git history exceeds the %d-commit selection limit." % MAX_HISTORY_COMMITS
        )
    cutoff_epoch = int(cutoff_value.timestamp())
    candidates = []
    for row in rows:
        if len(row) != 2:
            raise ValueError("Git returned malformed history evidence.")
        try:
            timestamp = int(row[0])
        except ValueError:
            raise ValueError("Git returned a malformed committer timestamp.")
        if timestamp <= cutoff_epoch:
            candidates.append((timestamp, row[1]))
    if not candidates:
        raise ValueError(
            "No commit on %r exists at or before %s." % (requested_ref, cutoff)
        )
    selected_timestamp, selected = max(
        candidates, key=lambda value: (value[0], value[1])
    )

    shallow = _git(repo_root, ["rev-parse", "--is-shallow-repository"])
    history_complete = shallow.returncode == 0 and shallow.stdout.strip() == "false"
    limitations = [] if history_complete else ["shallow_or_unverifiable_history"]
    return OrderedDict(
        (
            ("repo_root", repo_root),
            ("mode", "git_as_of"),
            ("cutoff", cutoff_value.isoformat()),
            ("time_policy", "committer"),
            ("requested_ref", requested_ref),
            ("selection_root", root),
            ("selected_commit", selected),
            (
                "selected_committer_time",
                (
                    datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
                    + datetime.timedelta(seconds=selected_timestamp)
                ).isoformat(),
            ),
            ("tie_break", "maximum_full_sha"),
            ("history_complete", history_complete),
            ("limitations", limitations),
        )
    )


def historical_temporal_thread_as_of(
    paths, target_id, today, cutoff, ref=None, key="id", **bounds
):
    selection = select_revision_as_of(paths, cutoff, ref=ref)
    metadata = OrderedDict(
        (name, value) for name, value in selection.items() if name != "repo_root"
    )
    snapshot = historical_snapshot(
        paths,
        selection["selected_commit"],
        key=key,
        resolved_commit=selection["selected_commit"],
        metadata=metadata,
    )
    return thread_from_snapshot(snapshot, target_id, today, key=key, **bounds)
