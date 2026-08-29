"""Assemble the packaged Web UI from split HTML/CSS/JavaScript resources.

``HTML_PAGE`` remains the pristine page. ``surface_runtime`` may rebind
``webapp.HTML_PAGE`` with compatibility scripts without mutating this value.
"""

import base64
from importlib import resources


_STYLE_MARKER = "__LIFETXT_WEB_STYLES__"
_SCRIPT_MARKER = "__LIFETXT_WEB_SCRIPT__"
_BRAND_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="lifetxt" data-lifetxt-geometry="v2">
  <rect x="24" y="24" width="464" height="464" rx="108" fill="#27343D"/>
  <g data-lifetxt-base="v2" shape-rendering="geometricPrecision">
    <path data-lifetxt-part="notebook" d="M154 84H270L318 132V364C318 384 306 396 286 396H154C134 396 122 384 122 364V116C122 96 134 84 154 84Z" fill="#FFFFFF"/>
    <path data-lifetxt-part="fold" d="M270 84V116C270 126 276 132 286 132H318Z" fill="#27343D"/>
    <circle data-lifetxt-part="row-1-dot" cx="162" cy="184" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-1-line" x="190" y="176" width="78" height="16" rx="8" fill="#27343D"/>
    <circle data-lifetxt-part="row-2-dot" cx="162" cy="242" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-2-line" x="190" y="234" width="64" height="16" rx="8" fill="#27343D"/>
    <circle data-lifetxt-part="row-3-dot" cx="162" cy="300" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-3-line" x="190" y="292" width="50" height="16" rx="8" fill="#27343D"/>
    <path data-lifetxt-part="stem" d="M314 420C317 384 325 352 346 326C350 321 359 324 356 331C338 354 331 384 330 420Z" fill="#7ADCC8"/>
    <path data-lifetxt-part="leaf-left" d="M344 347C317 349 299 333 296 307C321 305 341 320 347 342C348 345 347 346 344 347Z" fill="#7ADCC8"/>
    <path data-lifetxt-part="leaf-right" d="M351 344C356 320 370 306 390 304C389 325 376 340 355 347C352 347 350 346 351 344Z" fill="#7ADCC8"/>
  </g>
</svg>
"""
_BRAND_MARK_SVG = """<svg viewBox="0 0 512 512" width="27" height="27" focusable="false" aria-hidden="true" data-lifetxt-geometry="v2">
  <g data-lifetxt-base="v2" shape-rendering="geometricPrecision">
    <path data-lifetxt-part="notebook" d="M154 84H270L318 132V364C318 384 306 396 286 396H154C134 396 122 384 122 364V116C122 96 134 84 154 84Z" fill="#FFFFFF"/>
    <path data-lifetxt-part="fold" d="M270 84V116C270 126 276 132 286 132H318Z" fill="#27343D"/>
    <circle data-lifetxt-part="row-1-dot" cx="162" cy="184" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-1-line" x="190" y="176" width="78" height="16" rx="8" fill="#27343D"/>
    <circle data-lifetxt-part="row-2-dot" cx="162" cy="242" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-2-line" x="190" y="234" width="64" height="16" rx="8" fill="#27343D"/>
    <circle data-lifetxt-part="row-3-dot" cx="162" cy="300" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-3-line" x="190" y="292" width="50" height="16" rx="8" fill="#27343D"/>
    <path data-lifetxt-part="stem" d="M314 420C317 384 325 352 346 326C350 321 359 324 356 331C338 354 331 384 330 420Z" fill="#BFF3E6"/>
    <path data-lifetxt-part="leaf-left" d="M344 347C317 349 299 333 296 307C321 305 341 320 347 342C348 345 347 346 344 347Z" fill="#BFF3E6"/>
    <path data-lifetxt-part="leaf-right" d="M351 344C356 320 370 306 390 304C389 325 376 340 355 347C352 347 350 346 351 344Z" fill="#BFF3E6"/>
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
