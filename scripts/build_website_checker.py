"""Explicit LOCAL preview only; never called by the Pages publication build (#1399)."""

import argparse
import html
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contrib.browser_check_poc.build import build as build_poc
from scripts.build_website import DEFAULT_URL, build as build_intro

SOURCE = ROOT / "website/checker"
CSP = "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; connect-src 'self'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'"
COPY = {
    "ja": {
        "title": "文法・項目チェック",
        "home": "日本語ホーム",
        "switch": "English",
        "scope": "文法・項目のみをチェックします。CLI全検査とは異なります。履歴・添付・設定・複数ファイル・サーバ書込は扱いません。",
        "privacy": "本文はこのページのWorker内で処理し、外部送信・URLへの追加・永続保存を行いません。チェックを押すまでランタイムを読み込みません。初回は同一サイトから約14MBを読み込みます。",
        "limits": "開発プレビュー：16,384 UTF-8 bytes、診断表示100件、初期化120秒・再検査5秒は候補値です。製品版での実ブラウザ受入・配布審査は未完です。",
        "support": "初版の対象候補はデスクトップChromium系です。本版はまだ対応環境を認定していません。Firefox・Safari・スマホ・低メモリ機器・スクリーンリーダーは未検証です。",
        "label": "life.txtのテキスト",
        "check": "チェック",
        "cancel": "キャンセル・すべて消去",
        "recovery": "失敗・時間切れでは入力・結果・ランタイムを消去します。接続を確認し、再入力してチェックしてください。別ページへの移動・閉じる操作では入力を保持しません。",
        "noscript": "このチェック機能にはJavaScriptが必要です。CLIを利用することもできます。",
        "notices": "ライセンス・ソース提供の未解決事項",
    },
    "en": {
        "title": "Grammar and item check",
        "home": "English home",
        "switch": "日本語",
        "scope": "Checks grammar and items only. This differs from the full CLI check. History, attachments, configuration, multiple files and server writes are excluded.",
        "privacy": "Text is processed in this page's Worker, without sending it, adding it to URLs or persisting it. Runtime loading starts only on Check. The first run downloads about 14 MB from this site.",
        "limits": "Development preview: 16,384 UTF-8 bytes, 100 displayed diagnostics, 120-second startup and 5-second warm budgets are candidates. Product browser acceptance and distribution review remain incomplete.",
        "support": "The initial target candidate is desktop Chromium. This version has no certified support environment yet. Firefox, Safari, phones, low-memory devices and screen readers are untested.",
        "label": "life.txt text",
        "check": "Check",
        "cancel": "Cancel / clear everything",
        "recovery": "Failure or timeout clears input, results and runtime. Check your connection, paste again and retry. Navigating away or closing the page does not retain input.",
        "noscript": "JavaScript is required for this checker. You can also use the CLI.",
        "notices": "Licences and unresolved source-delivery requirements",
    },
}


def render(lang, base=DEFAULT_URL):
    c = {k: html.escape(v, quote=True) for k, v in COPY[lang].items()}
    other = "en" if lang == "ja" else "ja"
    canonical = html.escape(base + lang + "/check/", quote=True)
    return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><meta name="description" content="{c["scope"]}">
<title>{c["title"]} | lifetxt</title><link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="{other}" href="{html.escape(base + other + "/check/", quote=True)}">
<link rel="stylesheet" href="../../style.css"><link rel="stylesheet" href="../../checker/checker.css">
<link rel="icon" href="../../assets/lifetxt-favicon.svg" type="image/svg+xml">
<script type="module" src="../../checker/ui.mjs"></script></head>
<body><main class="wrap checker"><p><a href="../">{c["home"]}</a> · <a lang="{other}" href="../../{other}/check/">{c["switch"]}</a></p>
<h1>{c["title"]}</h1><p>{c["scope"]}</p><p>{c["privacy"]}</p>
<aside class="note"><p>{c["limits"]}</p><p>{c["support"]}</p></aside>
<p id="help">{c["recovery"]}</p><label for="input">{c["label"]}</label>
<textarea id="input" aria-describedby="help bytes" spellcheck="false" autocomplete="off" autocapitalize="off"></textarea>
<p id="bytes"></p><div class="actions"><button class="button primary" type="button" id="check">{c["check"]}</button>
<button class="button" type="button" id="cancel" disabled>{c["cancel"]}</button></div>
<p id="status" role="status" aria-live="polite"></p><pre id="output" tabindex="0" aria-label="{c["title"]}"></pre>
<noscript><p>{c["noscript"]}</p></noscript>
<p><a href="../../checker/notices/README.md">{c["notices"]}</a></p>
</main></body></html>'''


def build(output):
    output = Path(output).resolve()
    protected = ("website", "assets", "lifetxt", "scripts", "tests", "contrib", ".ai")
    if output == ROOT or any(output.is_relative_to(ROOT / name) for name in protected):
        raise ValueError(
            "checker preview output must be separate from repository sources"
        )
    if output.exists():
        raise FileExistsError(output)
    # The standard website build remains introduction-only, including Pages.
    with tempfile.TemporaryDirectory() as directory:
        poc = Path(directory) / "poc"
        build_poc(poc)
        build_intro(output)
        destination = output / "checker"
        destination.mkdir()
        for name in ("runtime", "notices"):
            shutil.copytree(poc / name, destination / name)
        for name in ("core.zip", "engine.mjs"):
            shutil.copyfile(poc / name, destination / name)
        for name in ("adapter.py", "limits.mjs", "worker.mjs", "ui.mjs", "checker.css"):
            shutil.copyfile(SOURCE / name, destination / name)
        for lang in COPY:
            page = output / lang / "check"
            page.mkdir()
            (page / "index.html").write_text(render(lang), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
