# lifetxt brand assets

This directory is the canonical source for lifetxt visual identity assets.

The mark represents **a durable life record in plain text**: the document/list
shape stands for readable, structured text, while the sprout represents a life
record that keeps growing over time. The design intentionally avoids tying
lifetxt to one category such as tasks, calendars, databases, or AI.

## Canonical files

| File | Purpose |
| --- | --- |
| `lifetxt-symbol.svg` | Primary transparent symbol. Use in documentation, diagrams, and product UI when no app tile is needed. |
| `lifetxt-symbol-monochrome.svg` | Single-color symbol. Use for tray/menu-bar icons, stamps, print, and contexts that control foreground color. |
| `lifetxt-logo-horizontal.svg` | Symbol + `lifetxt` wordmark + supporting tagline. Use for repository/document headers and wider brand placements. |
| `lifetxt-app-icon.svg` | Vector master for app/store-style square icons. |
| `lifetxt-favicon.svg` | Simplified small-size master for browser tabs and other tiny placements. |
| `lifetxt-app-icon-1024.png` | High-resolution raster app icon. |
| `favicon-32.png` | Legacy/browser fallback raster. |
| `apple-touch-icon-180.png` | Apple touch/home-screen size. |
| `pwa-icon-192.png` / `pwa-icon-512.png` | PWA manifest sizes. |
| `pwa-maskable-512.png` | Maskable PWA-safe derivative. |

`lifetxt-symbol.svg`, `lifetxt-app-icon.svg`, and `lifetxt-favicon.svg` are the
vector sources of truth. Raster files are derivatives and should not be edited
independently.

## Palette

| Token | Hex | Role |
| --- | --- | --- |
| Graphite | `#27343D` | Durable text/document structure; primary dark neutral |
| Teal | `#2E9F8F` | Growth/continuity accent |
| Teal Light | `#7ADCC8` | Accent used on the dark app tile |
| White | `#FFFFFF` | High-contrast app-icon foreground |

The product Web UI may use its own semantic/theme tokens. Do not replace status,
warning, or other semantic colors with brand colors merely to match the logo.

## Size and spacing

- At **16-32 px**, use `lifetxt-favicon.svg` (or `favicon-32.png`) rather than
  the full transparent symbol.
- At **24 px and above**, `lifetxt-symbol.svg` is suitable for normal UI and
  documentation.
- For app launchers, use `lifetxt-app-icon.svg` or the supplied raster
  derivatives; do not place the transparent symbol directly on an arbitrary
  colored square.
- Keep clear space around the standalone symbol of at least **1/8 of its
  rendered width**. Do not let text or other marks touch the document outline
  or sprout.
- Keep the symbol upright and preserve its aspect ratio.

## Light, dark, and monochrome use

The primary transparent symbol is intended for light/neutral backgrounds. On a
dark background, prefer the app icon or the monochrome asset with a sufficiently
contrasting foreground color. The monochrome SVG uses `currentColor`, so the
embedding surface owns the final foreground color.

## Wordmark

The product name is **`lifetxt`**. `life.txt` remains the name of the human-
readable file format. The horizontal logo uses a neutral system-sans wordmark
with `life` in Graphite and `txt` in Teal.

`Your life. In text. Connected.` is supporting brand copy, not part of the
product name and not required next to the symbol.

## Current repository integrations

- The browser Web UI embeds the simplified favicon and brand mark through
  `lifetxt/web_assets.py`.
- Tauri Desktop packages `desktop/src-tauri/icons/icon.png` and `icon.ico`,
  generated from `lifetxt-app-icon.svg`.
- Future websites, installers, documentation, social cards, and store listings
  should start from the assets in this directory instead of creating a new
  symbol.

## Do not

- do not stretch, rotate, shadow, outline, or redraw the symbol;
- do not recolor individual document/list elements with semantic task/calendar
  colors;
- do not add a checkmark, calendar, database cylinder, AI sparkle, or provider
  logo to the canonical mark;
- do not edit raster derivatives as independent masters.

---

# 日本語

このディレクトリを lifetxt の**正式なブランド資産の基準**とします。

ロゴは「プレーンテキストとして長く所有できる生活記録」を表します。文書と行は
`txt` / 構造化された記録を、芽は過去・現在・未来にわたって記録が育ち続ける
`life` を表します。Task、Calendar、AI など個別機能だけを示すロゴにはしません。

用途の基本は次のとおりです。

- favicon・16〜32 px: `lifetxt-favicon.svg`
- 通常のシンボル: `lifetxt-symbol.svg`
- 横長のロゴ表示: `lifetxt-logo-horizontal.svg`
- Desktop / launcher / store: `lifetxt-app-icon.svg` または各 PNG
- tray・menu bar・白黒印刷: `lifetxt-symbol-monochrome.svg`
- PWA: `pwa-icon-192.png`, `pwa-icon-512.png`,
  `pwa-maskable-512.png`

シンボルの周囲には表示幅の 1/8 以上を目安に余白を確保し、変形・回転・独自の
影付け・要素ごとの色変更は行わないでください。
