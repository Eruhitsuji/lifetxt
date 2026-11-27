"""Build the site with the JavaScript syntax checker."""

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
ASSETS = {
    "ui.mjs": ROOT / "website/js-checker/ui.mjs",
    "checker.css": ROOT / "website/checker/checker.css",
    "parser.mjs": ROOT / "contrib/lifetxt-js-check/parser.mjs",
    "LICENSE.txt": ROOT / "LICENSE",
}
COPY = {
    "ja": (
        "書式チェック",
        "日本語ホーム",
        "状態・種類・タイトル・key:value・JSON詳細値・引用符・行継続・縦棒で始まる本文の書式を確認します。",
        "未対応の形式バージョンと、JavaScriptの安全な整数範囲を超えるJSON整数は検査対象外です。"
        "日付・時刻、イベントの開始・終了日時、繰り返し、開始条件 requires: を検査し、インデントから親子関係を推定します。"
        "同じ入力内のID、参照先、参照の循環、時系列参照と日付順の矛盾を検査します。完全な検査には lifetxt check を使用してください。",
        "UTF-8で16 KiBまで、診断は最大100件。本文はブラウザ内で処理し、送信や永続保存は行いません。",
        "life.txtのテキスト",
        "チェック",
        "サンプルを読み込む",
        "空欄でサンプルを読み込めます。読み込んだら、編集して書式をチェックできます。",
        "自分の life.txt を作る",
        "JavaScriptを有効にするか、CLIを使用してください。",
        "最初の1行を書いてみる",
        "まずはサンプルのタイトルを変えるか、下の入力欄に自分のタスクを1行書いて「チェック」を押します。",
        "未完了を示す状態です。完了したら [x] に変えます。",
        "タスクを示す種類です。",
        "タスクのタイトルです。空白を含むタイトルは半角の二重引用符で囲みます。",
        "期限を付ける場合は due: の直後に YYYY-MM-DD 形式の日付を書きます。",
        "チェックの範囲と制限",
        "書式の詳細",
    ),
    "en": (
        "Syntax check",
        "English home",
        "Checks statuses, types, titles, key:value and JSON details, quotes, backslash line joins, and pipe-prefixed body lines.",
        "Unsupported format versions and JSON integers outside the JavaScript safe range are not checked. "
        "Checks dates, times, event range ordering, recurrence values, and requires: conditions, and infers parents from indentation. "
        "Checks ID format, duplicates, reference targets, relation cycles, and temporal relation ordering within the input. Use lifetxt check for full validation.",
        "Up to 16 KiB in UTF-8 and 100 diagnostics. Text is processed in your browser without transmission or persistent storage.",
        "life.txt text",
        "Check",
        "Load sample",
        "Load the sample into the empty field, then edit it and check its syntax.",
        "Create your own life.txt",
        "Enable JavaScript or use the CLI.",
        "Write your first line",
        "Change a title in the sample or write one task of your own below, then select Check.",
        "Marks an unfinished item. Change it to [x] when the task is done.",
        "Identifies the item as a task.",
        "The task title. Wrap titles that contain spaces in double quotes.",
        "To add a deadline, put a YYYY-MM-DD date directly after due:.",
        "What the checker covers",
        "Format reference",
    ),
}


def render(lang: str, base: str) -> str:
    (
        title, home, scope, excluded, limits, label, button, load, hint, guide, noscript,
        lesson, exercise, state_help, type_help, title_help, due_help, coverage, reference,
    ) = map(escape, COPY[lang])
    example = (ROOT / "website/example.txt").read_text(encoding="utf-8")
    sample = escape(example)
    first_line = escape(example.splitlines()[0])
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
<h1>{title}</h1>
<section id="lesson" aria-labelledby="lesson-title">
<h2 id="lesson-title">{lesson}</h2>
<pre class="lesson-example"><code>{first_line}</code></pre>
<dl class="lesson-parts">
<dt><code>[ ]</code></dt><dd>{state_help}</dd>
<dt><code>T</code></dt><dd>{type_help}</dd>
<dt><code>&quot;…&quot;</code></dt><dd>{title_help}</dd>
<dt><code>due:</code></dt><dd>{due_help}</dd>
</dl>
<p id="exercise">{exercise}</p>
</section>
<label for="input">{label}</label>
<textarea id="input" aria-describedby="exercise limits" spellcheck="false" autocomplete="off"></textarea>
<p id="sample-hint">{hint}</p>
<div class="actions">
<button class="button primary" id="check" type="button" disabled>{button}</button>
<button class="button" id="load-sample" type="button" disabled aria-describedby="sample-hint" data-sample="{sample}">{load}</button>
</div>
<p id="status" role="status"></p>
<pre id="output" tabindex="0" aria-label="{title}"></pre>
<noscript><p>{noscript}</p></noscript>
<details>
<summary>{coverage}</summary>
<p>{scope}</p><p>{excluded}</p>
</details>
<p id="limits">{limits}</p>
<p><a href="../get-started.html">{guide} →</a> · <a href="../documentation.html">{reference} →</a></p>
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
    for name, source in ASSETS.items():
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
