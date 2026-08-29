# lifetxt の distribution channel

このドキュメントは [#567](https://github.com/Eruhitsuji/lifetxt/issues/567) の
canonical distribution architecture を記録します：1 つの release tag/version
から、少数の canonical artifact（Python wheel/sdist、OCI image、standalone
platform binary）を build し、それぞれの audience に適した package manager を
通じて配布します。package manager 側の metadata（winget、Homebrew、
conda-forge）は、canonical artifact への薄い adapter に留め、独立した build を
二重に持たないようにします。

```text
                         lifetxt source
                               |
                         version / tag
                               |
              +----------------+----------------+
              |                                 |
       Python artifacts                    Native artifacts
       wheel / sdist                  Win / Linux / macOS
              |                                 |
            PyPI                         GitHub Release
              |                                 |
       pip / uv / pipx          winget / Scoop / Homebrew
              |
         conda-forge

                     OCI container image
                              |
                             GHCR
                              |
                     Docker / Compose
```

各 channel は、ある version について同じ source revision を指します：Git tag、
`pyproject.toml` の `project.version`、そして公開される各 artifact 自身が持つ
version が一致しなければなりません。`scripts/check_release_tag_version.py` が
tag/version の整合性を release workflow の中で強制します。

## 1. PyPI（Python package）

[#568](https://github.com/Eruhitsuji/lifetxt/issues/568) に対応します。

### end-user 向け install

```sh
pip install lifetxt
uv tool install lifetxt
pipx install lifetxt
uvx lifetxt --help

# optional extras
pip install "lifetxt[web]"
pip install "lifetxt[tui]"
```

公開後は `lifetxt --version` が install された release version を報告します。

### release が PyPI に届くまで

`.github/workflows/release.yml` は `v*.*.*` の tag push ごとに実行されます：

1. その tag の commit を checkout する。
2. tag が `pyproject.toml` の `project.version` と一致することを確認する
   （`scripts/check_release_tag_version.py`）。既存の stable release を指す
   version で、動いている `main` の tree を publish することはできません。
3. 既存の release policy profile（`scripts/run_ci_like.py --profile release`）
   を実行する。
4. checksum・SBOM・provenance metadata 付きで wheel と sdist を build する
   （`scripts/release_evidence.py`。release evidence 記録で既に使われている
   ものと同じ）。
5. `twine check` で package metadata を検証する。
6. build した wheel を clean な virtual environment に install し、
   `lifetxt --version` / `lifetxt check` の smoke test を行う。
7. [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
   （OIDC。長期 upload token をこの repository に保存しない）経由で PyPI へ
   publish する。
8. 同じ wheel/sdist/checksum/SBOM/provenance を、対応する GitHub Release に
   添付する。

### PyPI 側の一回限りの設定（maintainer 自身の作業。ここからは自動化できません）

手順 7 が成功するには、事前に PyPI 側で Trusted Publishing を紐付ける必要が
あります。これは `lifetxt` PyPI project の owner 自身の PyPI account が必要な
ため、この repository の中や AI agent からは実行できません：

1. PyPI 上で `lifetxt` の project name を確保する（初回 publish は手動での
   `twine upload` か、project が存在する前に Trusted Publisher を登録できる
   PyPI の「pending publisher」flow のいずれかが必要です。最新の手順は PyPI
   自身の文書を参照してください）。
2. <https://pypi.org/manage/project/lifetxt/settings/publishing/> で GitHub
   Trusted Publisher を追加する：
   - Owner: `Eruhitsuji`
   - Repository: `lifetxt`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. この repository の Settings → Environments で `pypi` という名前の
   environment を作成する（workflow が初めて参照した時に GitHub が自動作成
   しますが、事前に作っておけば required reviewer や deployment branch rule
   を追加して release review の摩擦を増やすこともできます）。

手順 2 が完了するまでは、`release.yml` の `publish-pypi` job は実行された上で
PyPI 側の OIDC exchange で cleanly に失敗します — 不完全・破損した release を
publish することはありません。

### 公開後の検証

```sh
python -m venv /tmp/lifetxt-pypi-smoke
/tmp/lifetxt-pypi-smoke/bin/pip install lifetxt
/tmp/lifetxt-pypi-smoke/bin/lifetxt --version
/tmp/lifetxt-pypi-smoke/bin/lifetxt check examples/minimal_life.txt

uv tool install lifetxt && lifetxt --version
pipx install lifetxt && lifetxt --version
uvx lifetxt --help
```

## 2. GHCR（OCI container image）

[#569](https://github.com/Eruhitsuji/lifetxt/issues/569) に対応します。

Docker は主に Web/MCP/server/NAS/VPS/home-server/CI 向けの install channel
であり、上記の通常の local CLI install を置き換えるものではありません。

### image の契約

- `ENTRYPOINT ["lifetxt"]`、`CMD` の default は `--help` のみ — image は CLI
  binary そのものとして振る舞います：`docker run ghcr.io/eruhitsuji/lifetxt:<version> check life.txt`
  は `lifetxt check life.txt` と同じことをします。
- non-root user（uid 1000）で動作し、`/data` を working directory かつ
  volume として宣言します。`life.txt`/configuration はここに mount して
  ください。
- `[web]` extra を install 済みで build されているため、同じ image で別
  build なしに Web API/UI を serve できます。
- 対応 architecture：`linux/amd64` と `linux/arm64`。
- development file・build tooling・`.git`・mutable な local state は一切
  含まれません（wheel を build する stage と、その wheel だけを新しい
  runtime layer に install する stage の 2 段階 build）。

### tag

| tag | 意味 |
| --- | --- |
| `ghcr.io/eruhitsuji/lifetxt:<version>`（例：`1.0.0`） | immutable。Git tag/GitHub Release/PyPI release と完全に一致します。production ではこちらを推奨します。 |
| `ghcr.io/eruhitsuji/lifetxt:<major>.<minor>` | convenience tag。その line の最新 patch release を指します。 |
| `ghcr.io/eruhitsuji/lifetxt:<major>` | convenience tag。その major line の最新 release を指します。 |
| `ghcr.io/eruhitsuji/lifetxt:latest` | convenience tag。最新の stable（prerelease でない）release を指します。prerelease tag（`rc`/`a`/`b` suffix）では publish されません。 |

production では immutable な version tag を pin し、convenience tag は
意図的に自動 upgrade を望む場合にのみ使ってください。

### CLI mode

```sh
docker pull ghcr.io/eruhitsuji/lifetxt:<version>

docker run --rm \
  -v "$PWD:/data" \
  ghcr.io/eruhitsuji/lifetxt:<version> \
  check /data/life.txt
```

### Web mode

```sh
docker run --rm \
  -p 8000:8000 \
  -v "$PWD:/data" \
  ghcr.io/eruhitsuji/lifetxt:<version> \
  serve /data/life.txt --host 0.0.0.0 --port 8000 --token-env LIFETXT_API_TOKEN \
  -e LIFETXT_API_TOKEN=change-me
```

（`-e LIFETXT_API_TOKEN=...` は他の `docker run` flag と同様、image name
より前に置いてください。上では可読性のため最後に示しています。）

### MCP mode

MCP は stdio protocol です。MCP client が process を spawn し、その
stdin/stdout と直接やり取りするため、detached かつ network 経由の
`docker compose up -d` service には合いません。代わりに attach した状態で
実行してください：

```sh
docker run -i --rm -v "$PWD:/data" ghcr.io/eruhitsuji/lifetxt:<version> mcp /data/life.txt
```

MCP client の `command`/`args` を、この正確な引数列で `docker` を起動する
よう設定してください（一般的な MCP client setup pattern の代わりにこれを
差し込む形になります。[ai-integration.md](./ai-integration.md) 参照）。

### Docker Compose（永続的な Web deployment）

repository root の [`docker-compose.yml`](../../docker-compose.yml) は、
そのまま copy して使える checked-in の例です：

```sh
cp docker-compose.env.example .env   # 編集して LIFETXT_API_TOKEN を設定
mkdir -p data && cp examples/minimal_life.txt data/life.txt
docker compose up -d
curl http://127.0.0.1:8000/api/health
```

default では何も pin しません（`LIFETXT_VERSION` は `latest` convenience
tag が default）。production では `.env` に `LIFETXT_VERSION=1.0.0` を
設定して immutable な release を pin してください。

### read-only と writable の使い分け

demo・閲覧専用の deployment には `serve` command に `--read-only` を追加
してください（CLI 自体の `--read-only` flag と同じで、Docker 固有のものでは
ありません）。指定しない場合、mount された `life.txt` は container の
uid-1000 user から書き込み可能です。host 側の file/directory permission が
それを許可していることを確認してください。

### update / pin の指針

- immutable な version tag は publish 後変わりません — 無期限に pin して
  安全です。
- `latest` および `<major>`/`<major>.<minor>` の convenience tag は、
  一致する release があるたびに `docker-publish.yml` によって指す先が
  更新されます。新しい version を取り込むには再 pull
  （`docker pull` / `docker compose pull`）が必要で、稼働中の container に
  自動で push されるわけではありません。
- base image（`python:3.12-slim`）は lifetxt 自体の release とは独立に
  OS level の security patch を受け取ります。lifetxt の release がなくても
  convenience tag を定期的に rebuild/再 pull することを推奨します。

### image が GHCR に届くまで

`.github/workflows/docker-publish.yml` は `v*.*.*` の tag push ごとに実行
されます（`release.yml` と同じ trigger）：

1. tag が `pyproject.toml` の version と一致することを確認する。
2. local で single-architecture の image を build し、mount した example
   への `check` command・process が uid 1000 で動作していることの確認・
   `/api/health` が応答するまで poll する `serve` 起動、の 3 つで
   smoke test する。
3. Buildx/QEMU で実際の multi-arch（`linux/amd64`、`linux/arm64`）image を
   build し、上記の tag 方針に従って `ghcr.io/eruhitsuji/lifetxt` へ push
   する。認証は GHCR 自身の `GITHUB_TOKEN` を使うため、別 account や
   credential の準備は不要です。

`workflow_dispatch` は push なしで build・smoke test のみ行うことにも
対応しています（`push: false` が default）。実 tag に届く前に Dockerfile
自体の変更を検証したい場合に使えます。

## 3. Standalone CLI binary

[#570](https://github.com/Eruhitsuji/lifetxt/issues/570) に対応します。

standalone binary は Python を一切 install せずに `lifetxt` を実行できるように
します — Python を使わない user 向けの推奨経路であり、winget/Scoop/Homebrew
（下記）が build の元にする canonical artifact でもあります。

### 対象 UX

GitHub Release から該当する artifact を download し、そのまま実行します：

```sh
lifetxt --version
lifetxt init
lifetxt doctor
lifetxt check life.txt
```

### 対応 target

| artifact | platform |
| --- | --- |
| `lifetxt-windows-x86_64.exe` | Windows x86_64 |
| `lifetxt-linux-x86_64` | Linux x86_64 |
| `lifetxt-linux-arm64` | Linux arm64 |
| `lifetxt-macos-arm64` | macOS arm64（Apple Silicon） |
| `lifetxt-macos-x86_64` | macOS x86_64（Intel） |

各 release では、全 artifact をカバーする `SHA256SUMS` file も同時に
公開されます。

### bundling の方式

[PyInstaller](https://pyinstaller.org/) を
[`packaging/pyinstaller/lifetxt.spec`](../../packaging/pyinstaller/lifetxt.spec)
経由で使い、platform ごとに 1 つの `--onefile` executable を作ります
（PyInstaller は各 target platform 上で native に実行する必要があるため、
`.github/workflows/standalone-binaries.yml` は 1 つの host から
cross-compile するのではなく、対応する GitHub-hosted runner ごとに build
します）。

**部分的な複数 artifact ではなく、1 つの完全な artifact。** bundle には
core・`web`・`tui` を含みます：standalone binary からそのまま
`lifetxt serve` と `lifetxt tui` の両方が動作します。これは本 project 自身の
「canonical artifact は 1 つに」という design 原則とも一致します —
Python packaging を避けるために standalone binary を選んだ user に、
「CLI のみ」と「full」のどちらを download するか選ばせるべきではありません。

frozen された binary には次が含まれます：

- lifetxt 自身の package data（分割された Web UI の HTML/CSS/JS resource）。
- `uvicorn` が実行時に文字列で動的 import する protocol/loop/lifespan の
  submodule（これらは PyInstaller の静的 import 解析だけでは検出できない
  ため、spec で明示的に collect しています）。
- `tzdata`（Windows build のみ）。`pyproject.toml` 自体の platform marker
  付き runtime dependency と同じ理由です（Windows には `zoneinfo` が読める
  IANA timezone database が存在しないため。背景となった incident は
  [RULES.md の Runtime Dependencies section](../../.ai/project/RULES.md#runtime-dependencies)
  を参照してください）。

### local での build

```sh
pip install ".[web,tui]" pyinstaller
pyinstaller packaging/pyinstaller/lifetxt.spec --distpath dist/standalone --clean --noconfirm
dist/standalone/lifetxt --version   # Windows では dist/standalone/lifetxt.exe
```

### 実施した検証

`standalone-binaries.yml` の matrix にある各 target は、それぞれの native
runner 上で以下を実行します：`--version`、実 example に対する `check`、
clean な scratch directory での `init`/`doctor`、空白と非 ASCII 文字を含む
directory path 内での `init`/`check`、そして `#!timezone: Asia/Tokyo` の
fixture に対する `check`/`today` の組み合わせによる timezone 解決の確認。
この project 自身の local Windows build ではさらに、`serve` mode が
`/api/health` に応答し、frozen された binary から bundle された Web UI の
HTML を serve できることも確認しています。

### 既知の制限（最初の slice）

- **code signing / notarization は未実装です。** 未署名の Windows binary
  は SmartScreen 警告を発生させ、未署名・未 notarize の macOS binary は
  明示的な user override（右クリック→開く、または
  `xattr -d com.apple.quarantine`）なしでは Gatekeeper にブロックされます。
  最初の slice では signing を blocker ではなく関連する follow-up として
  扱うという issue 自体の指針に従い、follow-up として明示的に記録します。
- **起動時間と binary size は最適化していません。** `--onefile` build は
  実行のたびに一時 directory へ self-extract するため、`--onedir` 構成より
  遅くなります。1 つの download 可能な file であるという単純さと引き換えに
  数百 ms の起動遅延を許容しています。これは issue 自体の「size の最小化
  より信頼できる動作を優先する」という指針と一致します。
- **UPX 圧縮は無効化しています**（spec の `upx=False`）。UPX で圧縮された
  executable は、非圧縮のものより antivirus の heuristic に引っかかることが
  多いためです。artifact size が実際に問題になった場合は見直す余地が
  あります。

### 下流での利用

これらの binary は、winget（#571）・Homebrew Tap（#572）・standalone な
Tauri desktop bundle（#574）が build の元にする canonical artifact です。
本 document 冒頭の distribution architecture を参照してください。

## 4. winget と Scoop（Windows package manager）

[#571](https://github.com/Eruhitsuji/lifetxt/issues/571) に対応します。
どちらも #570 の standalone Windows binary への薄い adapter であり、
別の build を導入するものではありません。

### winget（主経路）

```powershell
winget install Eruhitsuji.lifetxt
```

winget は現行の Windows に標準搭載されており別途 install が不要なため、
主経路として推奨します。package は `InstallerType: portable`（silent
install switch を持つ `setup.exe` ではなく、そのままの standalone
executable）を使います。winget は manifest の `Commands` field に宣言した
`lifetxt` という command name で、download した binary を PATH へ symlink
します。

**この repository は `microsoft/winget-pkgs` へ自動 submit しません。**
`scripts/generate_winget_manifest.py` は 1 つの release に対して必要な 3 つの
manifest file（version・installer・default-locale。manifest schema
1.6.0）を生成し、`.github/workflows/package-manifests.yml` が GitHub
Release が published されるたびに自動実行して、結果を download 可能な
workflow artifact として upload します。submit 自体は release ごとに手動で
行う 1 回限りの step です：

```sh
# local で、あるrelease の published SHA256SUMS から：
python scripts/generate_winget_manifest.py \
  --version 1.0.0 \
  --installer-url https://github.com/Eruhitsuji/lifetxt/releases/download/v1.0.0/lifetxt-windows-x86_64.exe \
  --sha256 <その release の SHA256SUMS にある sha256>

# または Microsoft 自身の submission tool を同じ release asset に対して使う：
winget install wingetcreate
wingetcreate submit --token <public_repo scope を持つ GitHub token> \
  packaging/winget/generated/Eruhitsuji/lifetxt/1.0.0/
```

`wingetcreate submit` はあなた自身の GitHub identity で
`microsoft/winget-pkgs` へ PR を開きます。あなたの credential なしに
non-interactive に行う方法はなく、これはこの issue で設定した境界と
一致します。

submission が受理された後（winget-pkgs 自体の CI が manifest を検証し、
moderator が merge します。通常数日以内）：

```powershell
winget install Eruhitsuji.lifetxt
winget upgrade Eruhitsuji.lifetxt
winget uninstall Eruhitsuji.lifetxt
lifetxt --version
```

winget は新しい shell の PATH を自動更新します。すでに開いている
terminal では、初回 install を反映するために再起動が必要です。

### Scoop（副経路）

```powershell
scoop bucket add <bucket-name> <bucket-url>   # tap/bucket が公開された後
scoop install lifetxt
```

`scripts/generate_scoop_manifest.py` が同様に `lifetxt.json` を生成し、
こちらも `package-manifests.yml` によって自動生成されます。Scoop の
manifest は「bucket」repository（`.json` file だけの普通の Git repo）に
置かれます。この project はまだ自前の bucket を持っておらず、これは
issue 自体の「Scoop は副経路」という scope guidance と一致します —
生成された manifest は、project 所有の bucket（作成され次第）か、
[`ScoopInstaller/Extras`](https://github.com/ScoopInstaller/Extras) の
ような community bucket への submission、いずれにもそのまま publish
できる状態です。どちらも、この repository が自動では行わない外部の
human identity による操作です。

```powershell
scoop install ./packaging/scoop/generated/lifetxt.json   # local file。manifest 自体の動作確認用
lifetxt --version
scoop uninstall lifetxt
```

## 5. Homebrew Tap

[#572](https://github.com/Eruhitsuji/lifetxt/issues/572) に対応します。

```sh
brew install Eruhitsuji/tap/lifetxt
```

### winget/conda-forge と異なり自動 publish される理由

winget と conda-forge は、この project が所有していない repository
（`microsoft/winget-pkgs`、`conda-forge/staged-recipes`）への PR が必要な
ため、submit は意図的に手動の human identity による操作としています
（section 4・6 参照）。Homebrew Tap は違います：
`brew install Eruhitsuji/tap/lifetxt` は
[`Eruhitsuji/homebrew-tap`](https://github.com/Eruhitsuji/homebrew-tap) ——
この project の maintainer 自身が所有する repository —— に対して動作しま
す。自分自身の release workflow から自分自身の repository へ publish する
ことは、他人の repository へ PR を開くこととは種類が異なる操作であるため、
`.github/workflows/homebrew-tap.yml` は GitHub Release が published される
たびに生成した Formula を自動的に push します。

### Formula の設計

`Formula/lifetxt.rb`（
[`scripts/generate_homebrew_formula.py`](../../scripts/generate_homebrew_formula.py)
が生成）は薄い adapter です：実行中の platform（macOS arm64/x86_64、
Linux arm64/x86_64）に対応する #570 の standalone binary を download し、
そのまま install します —— source からの build も、application logic の
重複もありません。これは issue 自体が挙げている「#570 の canonical で
immutable な release artifact を消費することを優先する」選択肢であり、
Python package ベースの Formula ではありません。

### 一回限りの設定（maintainer 自身の作業）

workflow 実行が受け取る default の `GITHUB_TOKEN` は、それが実行される
repository にしか scope されないため、*別の* repository
（`Eruhitsuji/homebrew-tap`）へ push するには、その repository への
access 権を持つ token が必要です：

1. [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new)
   を、`Eruhitsuji/homebrew-tap` repository のみを対象に、**Contents:
   Read and write** 権限で作成する。
2. それを `Eruhitsuji/lifetxt` の repository secret として
   `HOMEBREW_TAP_TOKEN` という名前で追加する（Settings → Secrets and
   variables → Actions）。

この secret が存在しない間は、`homebrew-tap.yml` の tap checkout step が
cleanly に失敗します（`Eruhitsuji/homebrew-tap` の checkout で
authentication error）—— 部分的に publish されることはありません。

### install 済み Formula の検証

```sh
brew install Eruhitsuji/tap/lifetxt
lifetxt --version
brew upgrade lifetxt
brew uninstall lifetxt
```

### Homebrew Core

最初の slice では追求しません。issue 自体の指針と一致します —— Homebrew
Core にはこの project の release cadence とは独立した独自の
acceptance/notability 要件があります。将来 Core への適格性を見直す issue
が立たない限り、Tap が引き続きサポートされる経路です。

## 6. conda-forge

[#573](https://github.com/Eruhitsuji/lifetxt/issues/573) に対応します。
まず実際の PyPI release が存在する必要があります（section 1）——
issue 自体の scope guidance に従い、recipe は独立した第二の release
origin になるのではなく、PyPI の sdist から build します。

```sh
conda install -c conda-forge lifetxt
```

### recipe の設計

`meta.yaml`（
[`scripts/generate_conda_recipe.py`](../../scripts/generate_conda_recipe.py)
が生成）は `noarch: python` です —— lifetxt の core には compiled
extension も、Windows のみの `tzdata` を除く third-party runtime
dependency もありません（conda の `# [win]` selector で宣言しており、
`pyproject.toml` 自体の `sys_platform == 'win32'` marker と対応します）。
公開された PyPI sdist から `pip install . --no-deps` で install します
（vendored な build step も packaging logic の重複もありません）。
install 後に `lifetxt --version` と `lifetxt check --help` を test します。

### この repository は conda-forge へ自動 submit しません

`conda-forge/staged-recipes` は community 運営の repository です。そこへ
recipe を submit することは、あなた自身の GitHub identity での PR に
なり、winget（section 4）で設定した境界と一致します。
`.github/workflows/conda-recipe.yml` は GitHub Release が published
されるたびに `meta.yaml` を自動生成し、download 可能な workflow
artifact として upload します。submit 自体は手動 step です：

```sh
# 実際の PyPI release が存在した後、その public な sdist から：
python scripts/generate_conda_recipe.py \
  --version 1.0.0 \
  --sha256 <lifetxt-1.0.0.tar.gz の sha256。例えば `pip download --no-deps --no-binary :all:` や release 自体の SHA256SUMS から>

# conda-forge/staged-recipes を fork し：
mkdir -p recipes/lifetxt
cp packaging/conda-forge/generated/recipe/meta.yaml recipes/lifetxt/
# commit・push し、conda-forge/staged-recipes へ PR を開く
```

conda-forge 自身の CI（`linter`・`build`）が PR 上で recipe を検証します。
merge されると、conda-forge の bot が `lifetxt-feedstock` repository を
作成・維持し、以降の version bump の多くを自動的に扱います
（conda-forge maintainer —— つまりあなた —— は、それでも各 bump PR を
review・merge します。この継続的な workflow は feedstock repository 側
で行われるものであり、ここでの話ではありません。詳細は conda-forge 自身
の [maintainer documentation](https://conda-forge.org/docs/maintainer/updating_pkgs.html)
を参照してください）。

### install 済み package の検証

```sh
conda create -n lifetxt-smoke -c conda-forge lifetxt
conda run -n lifetxt-smoke lifetxt --version
conda run -n lifetxt-smoke lifetxt check examples/minimal_life.txt
```

### scope

最初の submission では core package のみを対象とします。issue 自体の
「conda の optional feature/extras 方針を確認する。core package support
が最低要件」という guidance と一致します —— `web`/`tui` extra は最初の
conda-forge recipe には含まれません。将来の recipe 改訂（あるいは別の
`lifetxt-web`/`lifetxt-tui` output）は候補となる follow-up であり、この
slice には含まれません。

## 7. standalone な lifetxt Desktop

[#574](https://github.com/Eruhitsuji/lifetxt/issues/574) に対応します。

### desktop app の対象 UX

```text
installer を download -> lifetxt Desktop を install -> 起動 -> app が表示される
```

事前の Python・pip・uv・Rust・lifetxt CLI の install は不要です。

### 構成：引き続き companion process、bundle された runtime を追加

lifetxt Desktop（[`desktop/`](../../desktop/)、issue #233 の元の design）は、
`lifetxt serve` を child process として spawn し、結果の Web UI を表示する
薄い Tauri window です —— 自身の life.txt logic を持ったことは一度もなく、
本 #574 もそれを変更しません。変わるのは *どの* `lifetxt` を spawn するかです：
app 自身の installer は、section 3 の standalone binary をそのまま自身の
resource directory 配下に bundle するようになり、shell は `PATH` 上の何かより
その bundle された copy を優先します：

```text
backend の解決順序：
  1. <app resource dir>/bin/lifetxt(.exe)   <- この app 自身の installer が bundle（#574）
  2. lifetxt                                 <- PATH。#233 から変更なし
  3. python -m lifetxt                       <- PATH。#233 から変更なし
  4. python3 -m lifetxt                      <- PATH。#233 から変更なし
  5. py -m lifetxt                           <- PATH。#233 から変更なし
```

source build（`resources/bin/` に何も copy していない状態での
`cargo build`/`cargo run`）は bundle された candidate を見つけられず、
そのまま手順 2 へ通過します —— #574 以前の開発者向け workflow は変わりません。
Rust/Tauri 側に lifetxt の application logic は再実装されておらず、bundle
された artifact は section 3 と *同じ* PyInstaller binary であり、第二の
build ではありません。

### installer の build

```sh
pip install ".[web,tui]" pyinstaller
python packaging/tauri-desktop/prepare_bundled_runtime.py   # #570 の binary を build し resources/bin/ へ配置
python scripts/set_tauri_desktop_version.py --version 1.0.0  # installer 自身の version を release と一致させる
cargo install tauri-cli --version "^2" --locked
cd desktop/src-tauri && cargo tauri build
```

`.github/workflows/desktop-installers.yml` は `v*.*.*` の tag ごとに同じ
手順を `windows-latest`・`macos-latest`（arm64）・`ubuntu-latest` 上で native
に実行し、それぞれ MSI/NSIS・dmg・deb/AppImage の artifact（Tauri 自身の
platform ごとの default bundle target）を作成して、対応する GitHub Release
に添付します。

### version の traceability

installer 自身の version（`tauri.conf.json`）は、各 release で bundle される
lifetxt runtime と全く同じ version に設定されます ——
`scripts/set_tauri_desktop_version.py` が両者を 1:1 で結び付け、desktop
shell を独立した version 体系にはしていません。これは issue 自体の
「Desktop と bundle された runtime の version が再現可能で、immutable な
lifetxt release と紐付いている」という要件を、正しさを保ったまま最も単純な
形で満たします。

### data の保存

issue #233 から変更ありません：`life.txt` と configuration は引き続き完全に
外部の、user 所有の file のままです —— app には application 固有の
database がなく、何も自身の内部に閉じ込めません。この slice では、Tauri
shell 自体に初回起動時の file picker・「life.txt を作成/開く」UI は
追加していません（その flow はすでに served される Web UI 側にあり、この
shell はそれをそのまま表示します）。native な同等機能の追加は、暗黙に
欠落しているのではなく、明示的な未実装の follow-up として扱います。

### error の可視化

bundle された runtime・PATH 上の runtime のいずれも見つからない場合、または
見つかった runtime が 15 秒以内に健全にならない場合、window は何を試したか
（bundle された runtime、その後 PATH の候補）を平易な言葉で説明し、空白や
frozen のまま止まることはありません。存在はするが動作しない bundle
（壊れた install、あるいは architecture の不一致）は、そのまま失敗させる
のではなく PATH での discovery へ通過します。そのため、壊れた bundle が
別途 lifetxt を install 済みの user を必ずしも詰ませることにはなりません。

### bundle された runtime について実施した検証

この project 自身の Windows sandbox で：section 3 の standalone binary を
build し、source の `cargo run` がその解決された（dev mode の）resource
path に何も見つけられず正しく PATH へ通過することを確認（#233 の元の
挙動が影響を受けていないことの証明）した上で、Tauri の installer bundler
が実際の install で配置する内容を再現するため、同じ解決済み location へ
binary を配置し、app を起動して、実際の Windows process tree から
`lifetxt_desktop.exe` が child process として
`resources\bin\lifetxt.exe serve --host 127.0.0.1 --port <port>` を
正確に spawn したことを確認しました。実際の installer を生成する完全な
`cargo tauri build` は、この sandbox では完了していません ——
`tauri-cli` の install が、この変更とは無関係な、この sandbox 固有の
既存 toolchain 競合に当たったためです（正確な失敗内容と、GitHub の
clean な runner 上の CI には影響しないと考えられる理由については
[`desktop/README.md`](../../desktop/README.md#verification-performed-for-the-bundled-runtime-path-574)
を参照してください）。これは検証済みと主張せず、未検証の gap として
正直に記録します。

### desktop installer の既知の制限

- code signing / notarization は未実装です。section 3 自体が記録している
  standalone binary についての制限と同じです。
- macOS/Linux の desktop installer build は CI 上に組み込まれていますが、
  この project 自身の（Windows のみの）開発 sandbox では検証していません。
- auto-update・system tray icon・native menu bar は、issue 自体の scope
  に従い、明示的な未実装の follow-up のままです。

### contributor 向け install と end-user 向け install の違い

lifetxt 自体の source を変更する contributor は、引き続き editable install
（`pip install -e ".[dev]"`。
[Development environment](../../readme.md#development-environment) 参照）を
使います。`lifetxt update`/`lifetxt server-update` は、checkout を
fast-forward するためにこの editable な git-backed install に依存します。
`pip install lifetxt`（本ドキュメント）は別の、通常の end-user 向け経路で、
git checkout の存在を前提としません。
