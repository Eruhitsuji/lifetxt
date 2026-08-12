"""Packaged Web UI asset loaded from ``web_assets.html``.

The pristine value remains separate from ``webapp.HTML_PAGE`` so
``surface_runtime`` can rebind only the served compatibility value.
"""

from importlib import resources


HTML_PAGE = (
    resources.files(__package__).joinpath("web_assets.html").read_text(encoding="utf-8")
)
