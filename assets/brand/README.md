# lifetxt brand assets

This directory is the canonical source for lifetxt visual identity assets.

The mark represents **a durable life record in plain text**: the portrait
notebook/document stands for readable structured text, while the sprout
represents a life record that keeps growing over time. The design intentionally
avoids tying lifetxt to one category such as tasks, calendars, databases, or AI.

## Geometry contract

All icon variants use one base geometry (`data-lifetxt-geometry="v2"`). They are
not independently redrawn.

- Design grid: **512 × 512**.
- Combined notebook + sprout bounds: **x=122..390, y=84..420**. The horizontal
  center is exactly **256**; the vertical visual center is **252**, within 4 units
  of the canvas center.
- Notebook bounds: **196 × 312** (`x=122..318`, `y=84..396`), giving a portrait
  height/width ratio of about **1.59**.
- The base symbol leaves at least **84 design units** of safety margin to every
  canvas edge. The app tile adds a further launcher background around it.
- Notebook, fold, list marks, stem, and leaves are **filled vector shapes**.
  Canonical geometry does not depend on thin strokes, which keeps rasterization
  stable at favicon/launcher sizes.
- Favicon, Web header mark, transparent symbol, monochrome symbol, horizontal
  logo, Desktop icon, and PWA variants keep the same notebook/sprout path and
  primitive geometry. Color, background, and whole-symbol scale may change for
  the target surface; proportions and silhouette do not.
- The maskable PWA variant scales the same base geometry to **88% around the
  center** so it remains inside the platform mask safe zone. It is not a redraw.

These values are intentionally covered by `tests/test_brand_assets.py`. If the
base geometry is ever redesigned, change the master and the geometry contract as
one reviewed change rather than adjusting individual derivatives.

## Canonical files

| File | Purpose |
| --- | --- |
| `lifetxt-symbol.svg` | Primary transparent symbol. Use in documentation, diagrams, and product UI when no app tile is needed. |
| `lifetxt-symbol-monochrome.svg` | Single-color/knockout symbol using the same base geometry. Use for tray/menu-bar icons, stamps, and print. |
| `lifetxt-logo-horizontal.svg` | Same canonical symbol + `lifetxt` wordmark + supporting tagline. |
| `lifetxt-app-icon.svg` | Vector master for Desktop/launcher/store-style square icons. |
| `lifetxt-favicon.svg` | Browser-tab master. It uses the same base geometry rather than a separately redrawn tiny icon. |
| `lifetxt-maskable-icon.svg` | Maskable PWA vector master; same geometry at 88% safe-zone scale. |
| `lifetxt-app-icon-1024.png` | High-resolution raster app icon. |
| `favicon-32.png` | Legacy/browser fallback raster. |
| `apple-touch-icon-180.png` | Apple touch/home-screen size. |
| `pwa-icon-192.png` / `pwa-icon-512.png` | PWA manifest sizes. |
| `pwa-maskable-512.png` | Raster derivative of `lifetxt-maskable-icon.svg`. |

The SVG files are the vector sources of truth. Raster files are derivatives and
must not be edited independently.

## Palette

| Token | Hex | Role |
| --- | --- | --- |
| Graphite | `#27343D` | Durable text/document structure; primary dark neutral |
| Teal | `#2E9F8F` | Growth/continuity accent |
| Teal Light | `#7ADCC8` | Accent used on dark app surfaces |
| White | `#FFFFFF` | High-contrast notebook on dark app surfaces |

The product Web UI may use its own semantic/theme tokens. Do not replace status,
warning, or other semantic colors with brand colors merely to match the logo.

## Size and spacing

- At **16-32 px**, use `lifetxt-favicon.svg` (or `favicon-32.png`). Its geometry
  remains the same as the app icon; filled primitives keep the mark stable.
- At **24 px and above**, `lifetxt-symbol.svg` is suitable for normal UI and
  documentation.
- For app launchers, use `lifetxt-app-icon.svg` or the supplied raster
  derivatives.
- For maskable PWA surfaces, use `lifetxt-maskable-icon.svg` or
  `pwa-maskable-512.png`.
- Do not crop to the visible mark. Preserve the complete square viewBox/canvas
  so the designed safety margin remains intact.
- Keep the symbol upright and preserve its aspect ratio. Never independently
  scale the notebook and sprout.

## Light, dark, and monochrome use

The primary transparent symbol is intended for light/neutral backgrounds. On a
dark background, prefer the app icon or the monochrome asset with a sufficiently
contrasting foreground color. The monochrome SVG uses `currentColor` with
knockout details, so the embedding surface owns the foreground/background
contrast while the silhouette remains canonical.

## Wordmark

The product name is **`lifetxt`**. `life.txt` remains the name of the human-
readable file format. The horizontal logo uses a neutral system-sans wordmark
with `life` in Graphite and `txt` in Teal.

`Your life. In text. Connected.` is supporting brand copy, not part of the
product name and not required next to the symbol.

## Current repository integrations

- The browser Web UI embeds the canonical favicon and the same base geometry for
  its header mark through `lifetxt/web_assets.py`.
- Tauri Desktop packages `desktop/src-tauri/icons/icon.png` and `icon.ico`,
  generated from `lifetxt-app-icon.svg`.
- Future websites, installers, documentation, social cards, and store listings
  should start from these masters instead of redrawing the symbol.

## Do not

- do not stretch, rotate, crop, shadow, outline, or independently redraw the
  symbol;
- do not change notebook/sprout proportions between favicon, Desktop, Web, or
  documentation variants;
- do not move the visible mark toward an edge to compensate for a platform mask;
  scale the whole canonical geometry around its center instead;
- do not recolor individual document/list elements with semantic task/calendar
  colors;
- do not add a checkmark, calendar, database cylinder, AI sparkle, or provider
  logo to the canonical mark;
- do not edit raster derivatives as independent masters.

---

# 日本語

このディレクトリを lifetxt の**正式なブランド資産の基準**とします。

ロゴは「プレーンテキストとして長く所有できる生活記録」を表します。縦長の
ノート/文書と行は `txt` / 構造化された記録を、芽は過去・現在・未来にわたって
記録が育ち続ける `life` を表します。

## 幾何学上の基準

すべての派生アイコンは、同一のベース形状から作ります。favicon用、Desktop用、
Webヘッダー用などを個別に描き直しません。

- 基準キャンバス: **512 × 512**
- ノート＋芽の外接範囲: **x=122..390, y=84..420**
- 横方向の中心: **256**（キャンバス中央と一致）
- 縦方向の視覚中心: **252**（中央256との差4）
- ノート: **196 × 312**、縦/横比 約 **1.59** の明確な縦長
- 最小安全余白: **84**
- ノート、折り返し、リスト、茎、葉はすべて塗り形状を基本とし、小サイズで不安定
  になりやすい細い線だけの構成を使用しない
- maskable PWAのみ、同一形状全体を中央基準で **88%** に縮小する

これにより、以下を明示的なデザイン要件とします。

1. 中央配置を維持する
2. 縦横比を維持し、ノートを縦長にする
3. どの派生サイズでも見切れない安全余白を維持する
4. 塗りつぶし形状を主体として小サイズの描画を安定させる
5. ベースから各パターンを大きく崩さない

用途の基本は次のとおりです。

- favicon・16〜32 px: `lifetxt-favicon.svg`
- 通常のシンボル: `lifetxt-symbol.svg`
- 横長のロゴ表示: `lifetxt-logo-horizontal.svg`
- Desktop / launcher / store: `lifetxt-app-icon.svg` または各 PNG
- tray・menu bar・白黒印刷: `lifetxt-symbol-monochrome.svg`
- PWA: `pwa-icon-192.png`, `pwa-icon-512.png`
- maskable PWA: `lifetxt-maskable-icon.svg`, `pwa-maskable-512.png`

変形、回転、トリミング、独自の影付け、各用途ごとの描き直しは行わないでください。
