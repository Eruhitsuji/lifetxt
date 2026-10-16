# Official product website

Source for #1350 / #1351. This is a static introduction to lifetxt, separate
from the runnable Web UI. The planned URL is
`https://eruhitsuji.github.io/lifetxt/`; this file does not claim it is live.

`content.json` owns bilingual product copy, not technical specifications.
Keep command/format details in `docs/{ja,en}/` and link to those authoritative
guides. Update corresponding Japanese and English pages together. `example.txt`
is synthetic public sample data, not a user's record.

```sh
python scripts/build_website.py --output .cache/website
python scripts/check_website.py .cache/website
python -m lifetxt check website/example.txt
python -m http.server 8080 --directory .cache/website
```

Open `http://localhost:8080/`. To reproduce the project prefix, build into
`.cache/preview/lifetxt` and serve `.cache/preview`, then open `/lifetxt/`.
Output must be outside source directories and must not already exist: choose
a new directory for each build. The builder never deletes an output directory.

Root is a Japanese introduction with an English link, without browser-language
redirects or persistence. Stable language URLs use `/ja/` and `/en/`; language
links keep the same page. All ordinary local links are relative. The self-contained
404 recovery page uses the configured base path because unknown URL depth cannot
be resolved with relative links. `--site-url` changes canonical URLs, sitemap,
robots and that 404 base for a future host/domain (default: the planned URL).

Build copies only the three named canonical brand SVGs from `assets/brand/`.
No JavaScript, telemetry, cookies, external fonts, network build calls, runtime
APIs or user data are included. GitHub Pages itself is third-party hosting;
external documentation/release links use their destination services' policies.
Native binaries/Desktop installation and current support limitations stay in
the distribution guide, rather than being inferred from a package-manager recipe.

Publication, live checks and README/homepage promotion require separate human
approval and are tracked by #1352 and #1353.
