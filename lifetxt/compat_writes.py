"""Compatibility routing for legacy writers that bypassed ``atomic``.

Most historical writers imported ``atomic_write_text`` or
``atomic_write_json`` and are covered by the compatibility facade in
:mod:`lifetxt.atomic`.  The fzf/peco helper predates that module and retained a
private ``open(..., 'w')`` helper.  TUI bulk status/delete actions call that
helper, so install one narrow replacement until the command modules are split
and can import the shared mutation API directly.
"""


def install_legacy_write_routes():
    """Route known direct-open compatibility helpers through shared mutation."""
    from . import fzf_helper

    fzf_helper._write_text = _fzf_write_text


def _fzf_write_text(path, text):
    # Resolve lazily so tests and applications can instrument the authoritative
    # writer without this compatibility bridge retaining a stale function.
    from .mutation import write_text

    return write_text(
        path,
        text,
        operation="fzf_helper.write_text",
        create=False,
    )
