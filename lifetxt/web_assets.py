"""Assemble the packaged Web UI from split HTML/CSS/JavaScript resources.

``HTML_PAGE`` remains the pristine page. ``surface_runtime`` may rebind
``webapp.HTML_PAGE`` with compatibility scripts without mutating this value.
"""

import base64
from importlib import resources


_STYLE_MARKER = "__LIFETXT_WEB_STYLES__"
_SCRIPT_MARKER = "__LIFETXT_WEB_SCRIPT__"
_BRAND_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="2" y="2" width="60" height="60" rx="14" fill="#27343D"/>
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 13h18l9 9v17c0 6-4 10-10 10H18c-6 0-10-4-10-10V23c0-6 4-10 10-10Z" stroke="#FFFFFF" stroke-width="4"/>
    <path d="M36 14v6c0 2 2 4 4 4h4" stroke="#FFFFFF" stroke-width="4"/>
    <path d="M18 29h14M18 36h10" stroke="#FFFFFF" stroke-width="3.5"/>
    <path d="M37 51c1-8 4-14 9-18" stroke="#7ADCC8" stroke-width="4"/>
    <path d="M45 38c-5 1-9-2-10-7 6-1 10 2 11 6M46 37c1-6 5-9 11-9 0 6-4 10-10 10" stroke="#7ADCC8" stroke-width="4"/>
  </g>
</svg>
"""
_BRAND_MARK_SVG = """<svg viewBox="0 0 64 64" width="27" height="27" focusable="false" aria-hidden="true">
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 12h19l9 9v18c0 6-4 10-10 10H18c-6 0-10-4-10-10V22c0-6 4-10 10-10Z" stroke="#fff" stroke-width="4"/>
    <path d="M37 13v6c0 2 2 4 4 4h4M18 29h14M18 36h10" stroke="#fff" stroke-width="3.5"/>
    <path d="M37 51c1-8 4-14 9-18M45 38c-5 1-9-2-10-7 6-1 10 2 11 6M46 37c1-6 5-9 11-9 0 6-4 10-10 10" stroke="#bff3e6" stroke-width="4"/>
  </g>
</svg>"""
_CSS_RESOURCE_NAMES = (
    "web_assets_css_01.css",
    "web_assets_css_02.css",
    "web_assets_css_03.css",
    "web_assets_css_04.css",
)
_JS_RESOURCE_NAMES = (
    "web_assets_js_01.js",
    "web_assets_js_02.js",
    "web_assets_js_03.js",
    "web_assets_js_04.js",
    "web_assets_js_05.js",
    "web_assets_js_06.js",
    "web_assets_js_07.js",
    "web_assets_js_08.js",
    "web_assets_js_09.js",
    "web_assets_js_10.js",
    "web_assets_js_11.js",
    "web_assets_js_12.js",
    "web_assets_js_13.js",
    "web_assets_js_14.js",
    "web_assets_js_15.js",
    "web_assets_js_16.js",
    "web_assets_js_17.js",
    "web_assets_js_18.js",
)


def _read_resource(name: str) -> str:
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


def _svg_data_uri(svg: str) -> str:
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


def _apply_brand_assets(template: str) -> str:
    favicon = _svg_data_uri(_BRAND_FAVICON_SVG)
    title = "<title>life.txt</title>"
    brand_mark = '<span class="brand-mark" aria-hidden="true">✓</span>'
    if template.count(title) != 1 or template.count(brand_mark) != 1:
        raise RuntimeError("web_assets.html brand anchors must each occur exactly once")
    template = template.replace(
        title,
        title
        + '\n  <link data-lifetxt-brand="favicon" rel="icon" '
        + f'type="image/svg+xml" href="{favicon}">',
    )
    return template.replace(
        brand_mark,
        '<span class="brand-mark" data-lifetxt-brand="mark" aria-hidden="true">'
        + _BRAND_MARK_SVG
        + "</span>",
    )


def _assemble_html() -> str:
    template = _read_resource("web_assets.html")
    if template.count(_STYLE_MARKER) != 1 or template.count(_SCRIPT_MARKER) != 1:
        raise RuntimeError("web_assets.html must contain exactly one CSS and JS marker")
    template = _apply_brand_assets(template)
    styles = "".join(_read_resource(name) for name in _CSS_RESOURCE_NAMES)
    script = "".join(_read_resource(name) for name in _JS_RESOURCE_NAMES)
    return template.replace(_STYLE_MARKER, styles).replace(_SCRIPT_MARKER, script)


HTML_PAGE = _assemble_html()
