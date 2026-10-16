"""Build the public introduction only; no dependencies or network calls (#1351)."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website"
DEFAULT_URL = "https://eruhitsuji.github.io/lifetxt/"
REPO = "https://github.com/Eruhitsuji/lifetxt"
PAGES = ("index", "features", "use-cases", "get-started", "download", "documentation")
BRAND = ("lifetxt-symbol.svg", "lifetxt-favicon.svg", "lifetxt-logo-horizontal.svg")


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def site_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or any(c in value for c in '<>"\r\n')
        or any(p in (".", "..") for p in parts.path.split("/"))
    ):
        raise ValueError(
            "site URL must be a public HTTPS base URL without query/fragment"
        )
    return value.rstrip("/") + "/"


def href(target: str, lang: str, prefix: str = "../") -> str:
    if target.startswith("doc:"):
        return f"{REPO}/blob/main/docs/{lang}/{target[4:]}"
    if target == "docs":
        return f"{REPO}/tree/main/docs/{lang}"
    if target == "releases":
        return f"{REPO}/releases"
    if target == "sample":
        return prefix + "example.txt"
    if target not in PAGES:
        raise ValueError(f"Unknown website target: {target}")
    return ("./" if prefix == "../" else f"{lang}/") + (
        "" if target == "index" else target + ".html"
    )


def render(
    content: dict, lang: str, page: str, base: str, *, root: bool = False
) -> str:
    copy = content[lang]
    other = "en" if lang == "ja" else "ja"
    prefix = "./" if root else "../"
    canonical = (
        base
        if root
        else base + lang + "/" + ("" if page == "index" else page + ".html")
    )
    filename = "" if page == "index" else page + ".html"
    alternates = (
        "".join(
            f'<link rel="alternate" hreflang="{code}" href="{escape(base + code + "/" + filename)}">'
            for code in ("ja", "en")
        )
        + f'<link rel="alternate" hreflang="x-default" href="{escape(base if page == "index" else base + "ja/" + filename)}">'
    )
    title, intro, cards = copy["pages"][page]
    nav = "".join(
        f'<a href="{escape(href(slug, lang, prefix))}"'
        + (' aria-current="page"' if slug == page else "")
        + f">{escape(label)}</a>"
        for slug, label in zip(PAGES, copy["nav"], strict=True)
    )
    card_html = "".join(
        f'<article class="card"><span class="number">{escape(number)}</span>'
        f"<h3>{escape(heading)}</h3><p>{escape(body)}</p>"
        f'<a href="{escape(href(target, lang, prefix))}">{escape(label)} →</a></article>'
        for number, heading, body, target, label in cards
    )
    sample = escape((SOURCE / "example.txt").read_text(encoding="utf-8"))
    show_sample = page in ("index", "get-started")
    hero_title = copy["headline"] if page == "index" else title
    hero_intro = copy["intro"] if page == "index" else intro
    file_html = (
        '<div><div class="file"><div class="file-label">life.txt</div>'
        f"<pre><code>{sample}</code></pre></div>"
        f'<p class="file-caption">{escape(copy["sample"])}</p></div>'
        if show_sample
        else ""
    )
    switch = f"{prefix}{other}/{filename}"
    footer = "".join(
        f'<a href="{escape(href(target, lang, prefix))}">{escape(copy[label])}</a>'
        for target, label in (
            ("doc:getting-started.md", "guide"),
            ("docs", "docs"),
            ("releases", "releases"),
        )
    )
    return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | lifetxt</title>
<meta name="description" content="{escape(intro)}">
<link rel="canonical" href="{escape(canonical)}">{alternates}
<meta property="og:type" content="website"><meta property="og:site_name" content="lifetxt">
<meta property="og:title" content="{escape(title)} | lifetxt">
<meta property="og:description" content="{escape(intro)}">
<meta property="og:url" content="{escape(canonical)}">
<link rel="icon" type="image/svg+xml" href="{prefix}assets/lifetxt-favicon.svg">
<link rel="stylesheet" href="{prefix}style.css">
</head><body>
<a class="skip" href="#main">{escape(copy["skip"])}</a>
<header><div class="wrap header-inner">
<a class="brand" href="{escape(href("index", lang, prefix))}"><img src="{prefix}assets/lifetxt-symbol.svg" width="48" height="48" alt="">lifetxt</a>
<nav aria-label="{"メイン" if lang == "ja" else "Main"}">{nav}<a href="{REPO}">GitHub</a></nav>
<a class="language" href="{switch}" lang="{other}" hreflang="{other}">{escape(copy["switch"])}</a>
</div></header>
<main id="main" class="wrap" tabindex="-1">
<section class="{"hero" if show_sample else ""}" aria-labelledby="page-title"><div>
<p class="eyebrow">{escape(copy["eyebrow"])}</p>
<h1 id="page-title">{escape(hero_title)}</h1><p class="lead">{escape(hero_intro)}</p>
<div class="actions"><a class="button primary" href="{escape(href("get-started", lang, prefix))}">{escape(copy["start"])} →</a>
<a class="button" href="{escape(href("releases" if page == "download" else "download", lang, prefix))}">{escape(copy["releases"] if page == "download" else copy["download"])}</a></div>
</div>{file_html}</section>
<section class="section" aria-labelledby="section-title"><div class="section-title">
<h2 id="section-title">{escape(copy["cards_title"] if page == "index" else title)}</h2></div>
<div class="cards">{card_html}</div></section>
<aside class="note">{escape(copy["notice"])}</aside>
</main><footer><div class="wrap"><div class="footer-links">{footer}<a href="{REPO}">GitHub</a></div>
<p>Your life. In text. Connected.</p><p class="fine">{escape(copy["privacy"])}</p></div></footer>
</body></html>
'''


def build(output: Path, base: str = DEFAULT_URL) -> None:
    base = site_url(base)
    output = output.resolve()
    if any(
        output == path or output.is_relative_to(path)
        for path in (SOURCE, ROOT / "assets")
    ):
        raise ValueError("output must not be inside source or brand assets")
    # Never overwrite or recursively delete an existing directory.
    output.mkdir(parents=True, exist_ok=False)
    content = json.loads((SOURCE / "content.json").read_text(encoding="utf-8"))
    (output / "assets").mkdir()
    for name in BRAND:
        shutil.copyfile(ROOT / "assets/brand" / name, output / "assets" / name)
    for name in ("style.css", "example.txt"):
        shutil.copyfile(SOURCE / name, output / name)
    urls = [base]
    for lang in ("ja", "en"):
        (output / lang).mkdir()
        for page in PAGES:
            name = "index.html" if page == "index" else page + ".html"
            (output / lang / name).write_text(
                render(content, lang, page, base), encoding="utf-8"
            )
            urls.append(base + lang + "/" + ("" if page == "index" else name))
    (output / "index.html").write_text(
        render(content, "ja", "index", base, root=True), encoding="utf-8"
    )
    # The failed URL may have arbitrary depth. This one recovery page intentionally
    # uses the configured absolute base path and has no relative assets.
    recovery = escape(urlsplit(base).path)
    (output / "404.html").write_text(
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex"><title>404 | lifetxt</title></head>'
        "<body><main><h1>404 — ページが見つかりません / Page not found</h1>"
        f'<p><a href="{recovery}ja/">日本語ホーム</a></p>'
        f'<p><a href="{recovery}en/" lang="en">English home</a></p></main></body></html>',
        encoding="utf-8",
    )
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    sitemap += (
        "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls) + "</urlset>\n"
    )
    (output / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (output / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8"
    )
    (output / ".nojekyll").touch()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site-url", default=DEFAULT_URL)
    args = parser.parse_args()
    build(args.output, args.site_url)
    print("Built bilingual public website.")


if __name__ == "__main__":
    main()
