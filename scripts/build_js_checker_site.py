"""Build an explicit local site candidate with the JavaScript syntax checker."""

import argparse
from pathlib import Path
import shutil

if __package__ in (None, ""):
    from build_website import DEFAULT_URL, ROOT, build, escape, site_url
else:
    from scripts.build_website import DEFAULT_URL, ROOT, build, escape, site_url

CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self'; connect-src 'none'; worker-src 'none'; "
    "base-uri 'none'; form-action 'none'"
)
COPY = {
    "ja": (
        "書式チェック",
        "日本語ホーム",
        "状態・種類・タイトル・key:value・引用符・縦棒で始まる本文の書式を確認します。",
        "バックスラッシュによる行継続と未対応の形式バージョンは検査対象外です。"
        "日時やID・参照などを含む完全な検査には lifetxt check を使用してください。",
        "UTF-8で16 KiBまで、診断は最大100件。本文はブラウザ内で処理し、送信や永続保存は行いません。",
        "life.txtのテキスト",
        "チェック",
        "JavaScriptを有効にするか、CLIを使用してください。",
    ),
    "en": (
        "Syntax check",
        "English home",
        "Checks the syntax of statuses, types, titles, key:value details, quotes, and pipe-prefixed body lines.",
        "Backslash line joins and unsupported format versions are not checked. "
        "Use lifetxt check for full validation, including dates, IDs, and references.",
        "Up to 16 KiB in UTF-8 and 100 diagnostics. Text is processed in your browser without transmission or persistent storage.",
        "life.txt text",
        "Check",
        "Enable JavaScript or use the CLI.",
    ),
}


def render(lang: str, base: str) -> str:
    title, home, scope, excluded, limits, label, button, noscript = map(escape, COPY[lang])
    other, switch = ("en", "English") if lang == "ja" else ("ja", "日本語")
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><meta name="description" content="{scope}">
<title>{title} | lifetxt</title>
<link rel="canonical" href="{escape(base + lang + "/check/")}">
<link rel="alternate" hreflang="{other}" href="{escape(base + other + "/check/")}">
<link rel="stylesheet" href="../../style.css">
<link rel="stylesheet" href="../../js-checker/checker.css">
<link rel="icon" href="../../assets/lifetxt-favicon.svg">
<script type="module" src="../../js-checker/ui.mjs"></script>
</head><body><main class="wrap checker">
<p><a href="../">{home}</a> · <a href="../../{other}/check/" lang="{other}">{switch}</a></p>
<h1>{title}</h1><p id="scope">{scope}</p><p>{excluded}</p><p id="limits">{limits}</p>
<label for="input">{label}</label>
<textarea id="input" aria-describedby="scope limits" spellcheck="false" autocomplete="off"></textarea>
<div class="actions"><button class="button primary" id="check" type="button" disabled>{button}</button></div>
<p id="status" role="status"></p>
<pre id="output" tabindex="0" aria-label="{title}"></pre>
<noscript><p>{noscript}</p></noscript>
</main></body></html>
"""


def build_candidate(output: Path, base: str = DEFAULT_URL) -> None:
    output = output.resolve()
    protected = ("contrib", "scripts", "tests", ".ai", ".github", ".git")
    if output == ROOT or any(output.is_relative_to(ROOT / name) for name in protected):
        raise ValueError("checker candidate output must be separate from source files")
    base = site_url(base)
    build(output, base, checker_link=True)
    assets = output / "js-checker"
    assets.mkdir()
    for name, source in (
        ("ui.mjs", ROOT / "website/js-checker/ui.mjs"),
        ("checker.css", ROOT / "website/checker/checker.css"),
        ("parser.mjs", ROOT / "contrib/lifetxt-js-check/parser.mjs"),
        ("LICENSE.txt", ROOT / "LICENSE"),
    ):
        shutil.copyfile(source, assets / name)
    for lang in COPY:
        page = output / lang / "check"
        page.mkdir()
        (page / "index.html").write_text(render(lang, base), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site-url", default=DEFAULT_URL)
    args = parser.parse_args()
    build_candidate(args.output, args.site_url)
