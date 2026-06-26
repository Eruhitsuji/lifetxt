import html
import re
from collections import OrderedDict
from urllib.parse import urlparse


_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_UNORDERED_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_ORDERED_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_SAFE_LINK_SCHEMES = {"http", "https", "mailto"}


def markdown_to_html(text, inline=False):
    """Render the safe life.txt Markdown subset to HTML."""
    text = "" if text is None else str(text)
    if inline:
        return render_inline_markdown(text)
    return render_block_markdown(text)


def markdown_to_plain(text):
    """Strip the supported Markdown markers while preserving readable text."""
    text = "" if text is None else str(text)
    text = _strip_fence_markers(text)
    text = re.sub(r"(?m)^#{1,3}\s+", "", text)
    text = _LINK_RE.sub(lambda match: match.group(1), text)
    text = _CODE_RE.sub(lambda match: match.group(1), text)
    text = _BOLD_RE.sub(lambda match: match.group(1), text)
    text = _ITALIC_RE.sub(lambda match: match.group(1), text)
    return text


def item_markdown_payload(item):
    """Return sanitized Markdown HTML for fields likely to contain Markdown."""
    details = OrderedDict()
    for key in ("body", "note"):
        values = item.details.get(key) or []
        if values:
            details[key] = [markdown_to_html(value) for value in values]

    return OrderedDict(
        [
            ("title", markdown_to_html(item.title, inline=True)),
            ("details", details),
        ]
    )


def render_inline_markdown(text):
    text = "" if text is None else str(text)
    placeholders = []

    def stash(value):
        token = "\x00MD%d\x00" % len(placeholders)
        placeholders.append(value)
        return token

    def replace_code(match):
        return stash("<code>%s</code>" % html.escape(match.group(1), quote=True))

    def replace_link(match):
        label = render_inline_markdown(match.group(1))
        url = match.group(2)
        if not _is_safe_link(url):
            return stash(label)
        href = html.escape(url, quote=True)
        return stash(
            '<a href="%s" rel="noopener noreferrer" target="_blank">%s</a>'
            % (href, label)
        )

    text = _CODE_RE.sub(replace_code, text)
    text = _LINK_RE.sub(replace_link, text)
    escaped = html.escape(text, quote=True)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC_RE.sub(r"<em>\1</em>", escaped)

    for index, value in enumerate(placeholders):
        escaped = escaped.replace("\x00MD%d\x00" % index, value)
    return escaped


def render_block_markdown(text):
    text = "" if text is None else str(text)
    lines = text.splitlines()
    output = []
    paragraph = []
    list_type = None
    in_code = False
    code_lines = []

    def close_paragraph():
        if paragraph:
            joined = " ".join(line.strip() for line in paragraph)
            output.append("<p>%s</p>" % render_inline_markdown(joined))
            paragraph[:] = []

    def close_list():
        nonlocal list_type
        if list_type:
            output.append("</%s>" % list_type)
            list_type = None

    def ensure_list(kind):
        nonlocal list_type
        if list_type == kind:
            return
        close_paragraph()
        close_list()
        output.append("<%s>" % kind)
        list_type = kind

    def close_code():
        if code_lines:
            output.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code_lines)))
            code_lines[:] = []
        else:
            output.append("<pre><code></code></pre>")

    for line in lines:
        if line.strip().startswith("```"):
            close_paragraph()
            close_list()
            if in_code:
                close_code()
                in_code = False
            else:
                in_code = True
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            close_paragraph()
            close_list()
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            close_paragraph()
            close_list()
            level = len(heading.group(1))
            output.append(
                "<h%d>%s</h%d>"
                % (level, render_inline_markdown(heading.group(2)), level)
            )
            continue

        unordered = _UNORDERED_RE.match(line)
        if unordered:
            ensure_list("ul")
            output.append("<li>%s</li>" % render_inline_markdown(unordered.group(1)))
            continue

        ordered = _ORDERED_RE.match(line)
        if ordered:
            ensure_list("ol")
            output.append("<li>%s</li>" % render_inline_markdown(ordered.group(1)))
            continue

        close_list()
        paragraph.append(line)

    if in_code:
        close_code()
    close_paragraph()
    close_list()
    return "\n".join(output)


def _is_safe_link(url):
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _SAFE_LINK_SCHEMES:
        return False
    if parsed.scheme.lower() in ("http", "https") and not parsed.netloc:
        return False
    return True


def _strip_fence_markers(text):
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines)
