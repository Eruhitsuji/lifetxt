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

### contributor 向け install と end-user 向け install の違い

lifetxt 自体の source を変更する contributor は、引き続き editable install
（`pip install -e ".[dev]"`。
[Development environment](../../readme.md#development-environment) 参照）を
使います。`lifetxt update`/`lifetxt server-update` は、checkout を
fast-forward するためにこの editable な git-backed install に依存します。
`pip install lifetxt`（本ドキュメント）は別の、通常の end-user 向け経路で、
git checkout の存在を前提としません。
