"""Configurable TUI key bindings (`tui.bindings`, #595).

A small, explicit overlay over named TUI actions layered on top of the
existing `prompt`/`vim`/`arrows` keymap presets:

    selected built-in keymap preset  <  tui.bindings overrides

This module only resolves which physical key(s) invoke each named action
and validates that resolution has no ambiguity. It creates no new input or
command engine: `lifetxt/tui_app.py`'s existing nav-mode handlers remain the
sole implementation of what each action does; this module only decides
which key reaches which handler. Ctrl-C and the nav-mode Esc/cancel path are
never part of this registry and always remain available, so a custom map
can never make the TUI impossible to exit or cancel.
"""

from __future__ import unicode_literals

from collections import OrderedDict


#: Every action a user may remap in this first slice. Fixed and closed --
#: unknown action ids in configuration are rejected, not silently ignored.
ACTION_IDS = (
    "move_up",
    "move_down",
    "first",
    "last",
    "open",
    "toggle_mark",
    "done",
    "search",
    "command",
    "reload",
    "help",
    "quit",
)

#: Human-readable label for each action, used by the effective-bindings
#: help/hint rendering so help text is generated from resolved bindings
#: rather than a second, separately maintained copy.
ACTION_LABELS = OrderedDict(
    (
        ("move_up", "move the selection up"),
        ("move_down", "move the selection down"),
        ("first", "jump to the first row"),
        ("last", "jump to the last row"),
        ("open", "toggle the inspector"),
        ("toggle_mark", "mark or unmark the selected row"),
        ("done", "mark the selected item done"),
        ("search", "filter rows"),
        ("command", "type a command"),
        ("reload", "reload from disk"),
        ("help", "toggle help"),
        ("quit", "quit"),
    )
)

#: Preset base bindings: keymap name -> action id -> default key tuple.
#: Mirrors the physical key set `lifetxt/tui_app.py`'s nav-mode handler
#: already hard-codes for the vim/arrows keymaps -- both share one physical
#: key set today, so one base table covers both. `prompt` has no nav-mode
#: bindings of its own, since it stays in the input bar permanently.
_VIM_BASE = OrderedDict(
    (
        ("move_up", ("k", "up", "ctrl-p")),
        ("move_down", ("j", "down", "ctrl-n")),
        ("first", ("g", "home")),
        ("last", ("G", "end")),
        ("open", ("enter",)),
        ("toggle_mark", (" ",)),
        ("done", ("d",)),
        ("search", ("/",)),
        ("command", (":",)),
        ("reload", ("r",)),
        ("help", ("?",)),
        ("quit", ("q",)),
    )
)
_PRESET_BASE_BINDINGS = {
    "vim": _VIM_BASE,
    "arrows": _VIM_BASE,
    "prompt": OrderedDict(),
}

#: Keys that stay hard-coded outside the registry (page moves, edit/undo,
#: the view-cycle key, and cancel) and can never be reassigned through
#: `tui.bindings`. Reserving them prevents a custom binding from silently
#: shadowing a key nav-mode still handles directly, and keeps the required
#: cancel/exit path (`escape`, and Ctrl-C above this module entirely)
#: unremappable by construction.
RESERVED_KEYS = frozenset(
    ("e", "u", "tab", "escape", "pgup", "pgdn", "ctrl-u", "ctrl-d", "ctrl-c")
)

_KEY_ALIASES = {"spacebar": "space", "space": "space", "esc": "escape"}
_SYMBOLIC_KEYS = frozenset(
    (
        "up",
        "down",
        "left",
        "right",
        "home",
        "end",
        "pgup",
        "pgdn",
        "enter",
        "escape",
        "tab",
        "backspace",
        "delete",
    )
)

_DISPLAY_NAMES = {" ": "space"}


def normalize_key_name(raw):
    """Normalize one configured key spelling to the form `handle_key()` uses.

    Accepts the same deterministic symbolic names `normalize_key()` already
    produces (`j`, `k`, `enter`, `space`, `esc`, `ctrl-p`, `up`, `down`, ...).
    Raises ``ValueError`` for anything else.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Key names must be non-empty strings, got %r." % (raw,))
    text = raw.strip()
    lowered = text.lower()
    if lowered in _KEY_ALIASES:
        alias = _KEY_ALIASES[lowered]
        return " " if alias == "space" else alias
    if lowered in _SYMBOLIC_KEYS:
        return lowered
    if lowered.startswith("ctrl-") and len(lowered) == 6 and lowered[5].isalpha():
        return lowered
    if len(text) == 1 and text != " ":
        # Single visible characters stay case-sensitive: g and G are
        # different keys (first vs. last in the default vim/arrows map).
        return text
    raise ValueError("Unsupported key name: %r" % (raw,))


def display_key(key):
    return _DISPLAY_NAMES.get(key, key)


def resolve_bindings(keymap, overrides=None):
    """Merge a preset's base bindings with configured `tui.bindings` overrides.

    Returns ``(action_by_key, keys_by_action)``:

    * ``action_by_key`` -- normalized key -> action id, for input dispatch.
    * ``keys_by_action`` -- action id -> ordered, deduplicated key list, for
      help/hint rendering.

    Raises ``ValueError`` for an unknown action id, an unsupported key
    name, a key reserved for a still hard-coded action (see
    ``RESERVED_KEYS``), or a normalized key that would resolve to two
    different actions in the same mode -- naming both actions.
    """
    base = _PRESET_BASE_BINDINGS.get(keymap, _VIM_BASE)
    keys_by_action = OrderedDict((action, list(keys)) for action, keys in base.items())

    if overrides:
        if not isinstance(overrides, dict):
            raise ValueError(
                "tui.bindings must be an object mapping action -> key name(s)."
            )
        for action, raw_keys in overrides.items():
            if action not in ACTION_IDS:
                raise ValueError(
                    "tui.bindings has an unknown action %r. Known actions: %s."
                    % (action, ", ".join(ACTION_IDS))
                )
            if isinstance(raw_keys, str):
                raw_keys = [raw_keys]
            if not isinstance(raw_keys, list) or not raw_keys:
                raise ValueError(
                    "tui.bindings.%s must be a key name or a non-empty array "
                    "of key names." % action
                )
            normalized = []
            for raw_key in raw_keys:
                key = normalize_key_name(raw_key)
                if key in RESERVED_KEYS:
                    raise ValueError(
                        "tui.bindings.%s cannot use %r: that key is reserved "
                        "for an existing action outside this registry." % (action, key)
                    )
                if key not in normalized:
                    normalized.append(key)
            keys_by_action[action] = normalized

    action_by_key = OrderedDict()
    for action, keys in keys_by_action.items():
        for key in keys:
            if key in action_by_key and action_by_key[key] != action:
                raise ValueError(
                    "tui.bindings conflict: key %r is bound to both %r and %r."
                    % (key, action_by_key[key], action)
                )
            action_by_key[key] = action

    return action_by_key, keys_by_action


def install_tui_bindings_config_registry():
    """Extend the authoritative registry with `tui.bindings` metadata once.

    Mirrors the wildcard-key pattern `lifetxt.report_config` established for
    `reports.*.period`. `tui.*` has no other registered keys yet (a
    pre-existing gap recorded in docs/en/config.md's "Complete key
    reference"); this adds only the two keys #595 introduces.
    """
    from . import config_registry

    if getattr(config_registry, "_lifetxt_tui_bindings_config_installed", False):
        return

    entry = config_registry._entry
    entries = (
        (
            "tui.bindings",
            entry(
                "object",
                None,
                "Per-action key overrides layered on top of the selected "
                "tui.keymap preset (prompt/vim/arrows). See `lifetxt config "
                "explain tui.bindings.*` for one action's contract.",
                since="unreleased",
            ),
        ),
        (
            "tui.bindings.*",
            entry(
                "string or array<string>",
                None,
                "One or more key names (e.g. k, up, ctrl-p, space) invoking "
                "this action instead of the keymap preset's default. See "
                "ACTION_IDS in lifetxt/tui_bindings.py for the fixed set of "
                "overridable actions and RESERVED_KEYS for keys that always "
                "stay hard-coded (edit, undo, page moves, cancel, quit-key "
                "escape hatches).",
                since="unreleased",
            ),
        ),
    )
    for key, metadata in entries:
        config_registry.CONFIG_REGISTRY[key] = metadata
    config_registry._lifetxt_tui_bindings_config_installed = True
