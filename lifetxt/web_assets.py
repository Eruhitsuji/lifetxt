"""Assemble the packaged Web UI from split HTML/CSS/JavaScript resources.

``HTML_PAGE`` remains the pristine page. ``surface_runtime`` may rebind
``webapp.HTML_PAGE`` with compatibility scripts without mutating this value.
"""

from importlib import resources


_STYLE_MARKER = "__LIFETXT_WEB_STYLES__"
_SCRIPT_MARKER = "__LIFETXT_WEB_SCRIPT__"
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


def _assemble_html() -> str:
    template = _read_resource("web_assets.html")
    if template.count(_STYLE_MARKER) != 1 or template.count(_SCRIPT_MARKER) != 1:
        raise RuntimeError("web_assets.html must contain exactly one CSS and JS marker")
    styles = "".join(_read_resource(name) for name in _CSS_RESOURCE_NAMES)
    script = "".join(_read_resource(name) for name in _JS_RESOURCE_NAMES)
    return template.replace(_STYLE_MARKER, styles).replace(_SCRIPT_MARKER, script)


HTML_PAGE = _assemble_html()
