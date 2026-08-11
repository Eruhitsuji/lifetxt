# Safe process boundaries, directory attachments, and transaction administration

この文書は revision-aware write foundation を external editors、directory/package attachments、versioned transaction policy administration、abrupt-process drills、server-authoritative clock-skew reporting に広げた範囲を説明します。

## Safe external editor sessions

`lifetxt edit` は authoritative file を直接 editor に渡しません。temporary copy を作り、その copy を editor で開き、edited life.txt text を validate し、SHA-256 precondition 付きで replacement を apply します。

```bash
lifetxt edit life.txt --editor "code --wait" --show-diff
```

useful modes:

- `--review-only`: full unified diff を返し write しない
- `--reconcile`: editor 中に source が変わった場合、conservative line-based three-way reconciliation を試す。overlap は reject
- `--keep-temp`: recovery 用に temporary copy を残す
- `--dry-run`: editor command を print し launch しない

TUI と fzf/peco editor handoff も同じ temporary-copy/revision-check contract を使います。

## Directory and package attachments

directory reference と deterministic ZIP package が supported です。

```bash
lifetxt attachment directory-reference life.txt \
  --id T-1 \
  --file ./attachments/specs \
  --require-revisions \
  --item-revision LIFE_SHA256
```

```bash
lifetxt attachment package life.txt \
  --id T-1 \
  --source ./specs \
  --file ./attachments/specs.zip \
  --item-revision LIFE_SHA256 \
  --attachment-revision '<missing>' \
  --require-revisions
```

packages は sorted paths、fixed ZIP metadata、per-file SHA-256 values、embedded `lifetxt-package-manifest.json` を使います。limits は commit 前に enforce され、symlink と non-regular entries は default reject です。

remote/open operations は OS command plan を返します。server は opener を execute しません。

## Transaction administration

`transactions.policy_file` で standalone versioned policy file を supplement できます。

```bash
lifetxt safety transactions policy-write \
  --journal-dir .lifetxt-transactions \
  --operator alice \
  --set max_transactions=750 \
  --pretty
```

administrative operations は bounded, revision-safe audit records を append します。policy writes には operator identity を含めてください。

## Abrupt-process drills and clock skew

`lifetxt safety transactions drill` は child Python process を起動し、selected durable boundary で `os._exit` します。これは abrupt interpreter termination の evidence であり、power loss や storage-controller ordering の evidence ではありません。

`GET /api/time` と MCP `get_clock_status` は server-authoritative UTC time と client skew report を返します。naive timestamps without UTC offset は reject されます。

## Boundary checklist

- external editors は temporary copies を操作します。authoritative file は validation と revision checks の後だけ replace されます。
- directory package creation は review/retry できる deterministic operation ですが、package sources は configured root に confinement されている必要があります。
- transaction policy writes は administrative operations であり、audit records に operator identity を含めるべきです。
