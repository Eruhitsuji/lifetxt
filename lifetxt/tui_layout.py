"""Pure display-width and frame-text helpers for the interactive TUI."""

from .tui import _char_display_width, _clip_display_width


def display_width(text):
    return sum(_char_display_width(char) for char in str(text or ""))


def fit(text, width, glyphs=None):
    """Clip text to width, appending an ellipsis when it does not fit."""
    text = str(text or "")
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    marker = (glyphs or {"ellipsis": "…"})["ellipsis"]
    marker_width = display_width(marker)
    if width <= marker_width:
        return _clip_display_width(text, width)
    return _clip_display_width(text, width - marker_width) + marker


def pad(text, width):
    text = str(text or "")
    return text + " " * max(0, width - display_width(text))


def fit_spans(spans, width):
    """Clip a list of (text, style) spans to a total display width."""
    result = []
    used = 0
    for text, style in spans:
        text = str(text or "")
        if not text or used >= width:
            continue
        chunk_width = display_width(text)
        if used + chunk_width <= width:
            result.append((text, style))
            used += chunk_width
            continue
        clipped = _clip_display_width(text, width - used)
        if clipped:
            result.append((clipped, style))
        break
    return result


def spans_to_text(spans):
    return "".join(text for text, _style in spans)


def frame_to_text(frame):
    """Flatten a styled frame into plain text (used by tests and snapshots)."""
    return "\n".join(spans_to_text(line) for line in frame) + "\n"
