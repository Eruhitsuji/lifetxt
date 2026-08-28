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

### contributor 向け install と end-user 向け install の違い

lifetxt 自体の source を変更する contributor は、引き続き editable install
（`pip install -e ".[dev]"`。
[Development environment](../../readme.md#development-environment) 参照）を
使います。`lifetxt update`/`lifetxt server-update` は、checkout を
fast-forward するためにこの editable な git-backed install に依存します。
`pip install lifetxt`（本ドキュメント）は別の、通常の end-user 向け経路で、
git checkout の存在を前提としません。
