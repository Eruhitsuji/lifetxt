"""Read-only local Web projection of the canonical Daily Flow model (#1146)."""

import copy
import os
from types import SimpleNamespace

from .daily_flow import build_daily_flow
from .daily_flow_cli import _parse, _read, _validate_window
from .daily_flow_model import HARD_LIMITS
from .mutation import MutationError
from .timezone_policy import now, resolve_timezone_name


def _active_paths(paths, config):
    """Only registered server sources; never expand request/config paths."""
    from .workspace import resolve_workspace, workspace_resolution_active

    selected = list(paths)
    if workspace_resolution_active(config, config.get("_active_workspace")):
        resolution = resolve_workspace(config, config.get("_active_workspace"))
        if any(d["severity"] == "error" for d in resolution["diagnostics"]):
            raise OSError("Workspace unavailable")
        archives = {
            os.path.normcase(os.path.realpath(p)) for p in resolution["archive_paths"]
        }
        selected = [
            p for p in selected if os.path.normcase(os.path.realpath(p)) not in archives
        ]
    if not selected or "-" in selected or len(selected) > HARD_LIMITS["context"]:
        raise OSError("Active sources unavailable")
    return list(dict.fromkeys(os.path.normcase(os.path.realpath(p)) for p in selected))


def daily_flow_response(
    paths, config, *, date, day_start, day_end, area=None, saved_view=None
):
    """Bounded byte snapshot, one retry, no scheduling/auth logic in adapter.

    This is the existing full-workspace local Web reader, not Remote's
    principal-filtered reader. Candidate selectors are never access grants.
    """
    _validate_window(SimpleNamespace(date=date, day_start=day_start, day_end=day_end))
    config = copy.deepcopy(config or {})
    evaluated = now("UTC")
    # Establish a safe fallback zone without reading any source on IO failure.
    zone = resolve_timezone_name(config)
    if zone.lower() in ("local", "host"):
        zone = "UTC"
    options = dict(
        date=date,
        day_start=day_start,
        day_end=day_end,
        timezone=zone,
        evaluated_at=evaluated,
        occupancy_complete=False,
    )
    try:
        for attempt in range(2):
            selected = _active_paths(paths, config)
            snapshots = {}
            total = 0
            for path in selected:
                snapshot = _read(path)
                total += len(snapshot.text)
                if total > HARD_LIMITS["text_chars"]:
                    raise OSError("Input bound exceeded")
                snapshots[path] = snapshot
            zone = resolve_timezone_name(config, text=snapshots[selected[0]].text)
            if zone.lower() in ("local", "host"):
                raise ValueError(
                    "Daily Flow requires an explicit resolved workspace timezone."
                )
            items, diagnostics = _parse(snapshots, None, config)
            options = dict(
                date=date,
                day_start=day_start,
                day_end=day_end,
                timezone=zone,
                evaluated_at=evaluated,
                occupancy_complete=True,
                config=config,
                area=area,
                saved_view=saved_view,
                source_revisions={
                    p.replace("\\", "/"): s.content_hash for p, s in snapshots.items()
                },
                input_diagnostics=diagnostics,
            )
            result = build_daily_flow(items, **options)
            if selected == _active_paths(paths, config) and all(
                _read(p).content_hash == s.content_hash for p, s in snapshots.items()
            ):
                return result
            if attempt == 1:
                return build_daily_flow((), **{**options, "snapshot_consistent": False})
    except (OSError, UnicodeError, MutationError):
        # Never return partially read inventory, exception filenames or times.
        return build_daily_flow((), **{**options, "occupancy_complete": False})
