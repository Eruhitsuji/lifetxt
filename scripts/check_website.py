"""Offline checks for generated website links, assets, and metadata (#1351)."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

if __package__ in (None, ""):
    from build_website import DEFAULT_URL, PAGES, REPO, ROOT, site_url
else:
    from scripts.build_website import DEFAULT_URL, PAGES, REPO, ROOT, site_url


class Document(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: list[str] = []
        self.canonical: list[str] = []
        self.alternates: dict[str, str] = {}
        self.errors: list[str] = []
        self.lang = ""
        self.h1 = 0
        self.main = 0
        self.description = False
        self.viewport = False
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag in ("script", "iframe", "form", "object", "embed", "base"):
            self.errors.append(f"forbidden active element: {tag}")
        if any(key.startswith("on") for key in attr):
            self.errors.append("inline event handler")
        if "id" in attr:
            self.ids.append(attr["id"] or "")
        for key in ("href", "src"):
            if attr.get(key):
                self.links.append(attr[key])
        if tag in ("img", "link"):
            asset = (
                attr.get("src")
                if tag == "img"
                else (
                    attr.get("href")
                    if attr.get("rel") in ("stylesheet", "icon")
                    else None
                )
            )
            if asset and urlsplit(asset).netloc:
                self.errors.append("remote asset")
        if tag == "img" and "alt" not in attr:
            self.errors.append("image missing alt")
        if tag == "html":
            self.lang = attr.get("lang", "") or ""
        self.h1 += tag == "h1"
        self.main += tag == "main"
        if tag == "meta":
            self.description |= attr.get("name") == "description" and bool(
                attr.get("content")
            )
            self.viewport |= attr.get("name") == "viewport"
        if tag == "link" and attr.get("rel") == "canonical":
            self.canonical.append(attr.get("href") or "")
        if tag == "link" and attr.get("rel") == "alternate":
            self.alternates[attr.get("hreflang") or ""] = attr.get("href") or ""


def check(output: Path, base: str = DEFAULT_URL) -> list[str]:
    output = output.resolve()
    base = site_url(base)
    errors = []
    docs = {
        file: Document(file.read_text(encoding="utf-8"))
        for file in output.rglob("*.html")
    }
    expected = {"index.html", "404.html"} | {
        f"{lang}/{page}.html" for lang in ("ja", "en") for page in PAGES
    }
    actual = {str(file.relative_to(output)) for file in docs}
    if actual != expected:
        errors.append(f"unexpected/missing HTML pages: {sorted(actual ^ expected)}")
    origin = urlsplit(base)
    for file, doc in docs.items():
        relative = file.relative_to(output).as_posix()
        page_url = base + relative
        errors.extend(f"{relative}: {error}" for error in doc.errors)
        if len(doc.ids) != len(set(doc.ids)):
            errors.append(f"{relative}: duplicate IDs")
        if (
            doc.lang not in ("ja", "en")
            or doc.h1 != 1
            or doc.main != 1
            or not doc.viewport
        ):
            errors.append(f"{relative}: missing language, heading, main, or viewport")
        if relative != "404.html":
            expected_lang = "ja" if relative.startswith("ja/") else "en"
            if doc.lang != expected_lang:
                errors.append(f"{relative}: wrong page language")
            canonical = base + relative.removesuffix("index.html")
            if doc.canonical != [canonical] or not doc.description:
                errors.append(f"{relative}: wrong canonical or missing description")
            filename = "" if file.name == "index.html" else file.name
            alternatives = {lang: base + lang + "/" + filename for lang in ("ja", "en")}
            alternatives["x-default"] = base if not filename else alternatives["en"]
            if doc.alternates != alternatives:
                errors.append(f"{relative}: wrong language alternates")
        for link in doc.links:
            parsed = urlsplit(urljoin(page_url, link))
            if parsed.scheme != "https":
                errors.append(f"{relative}: unsafe link: {link}")
                continue
            if parsed.netloc != origin.netloc:
                # Check repository documentation against the exact checkout offline.
                for prefix in (REPO + "/blob/main/", REPO + "/tree/main/"):
                    if (
                        link.startswith(prefix)
                        and not (
                            ROOT / unquote(urlsplit(link).path.split("/main/", 1)[1])
                        ).exists()
                    ):
                        errors.append(f"{relative}: missing repository target: {link}")
                continue
            path = unquote(parsed.path)
            if not path.startswith(origin.path):
                errors.append(f"{relative}: link escapes project prefix: {link}")
                continue
            target = (output / path[len(origin.path) :]).resolve()
            if not target.is_relative_to(output):
                errors.append(f"{relative}: link escapes output: {link}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{relative}: missing link: {link}")
            elif parsed.fragment and (
                target not in docs or unquote(parsed.fragment) not in docs[target].ids
            ):
                errors.append(f"{relative}: missing fragment: {link}")
    sitemap = output / "sitemap.xml"
    if not sitemap.is_file():
        errors.append("missing sitemap")
    else:
        locations = {
            node.text
            for node in ET.parse(sitemap).iter(
                "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
        }
        canonicals = {
            url
            for file, doc in docs.items()
            if file.name != "404.html"
            for url in doc.canonical
        }
        if locations != canonicals:
            errors.append("sitemap does not match canonical pages")
    if not (output / "robots.txt").is_file() or not (output / ".nojekyll").is_file():
        errors.append("missing robots.txt or .nojekyll")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--site-url", default=DEFAULT_URL)
    args = parser.parse_args()
    errors = check(args.output, args.site_url)
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print("Website: 14 HTML pages, local links/assets/fragments and metadata OK.")


if __name__ == "__main__":
    main()
