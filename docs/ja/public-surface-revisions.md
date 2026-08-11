# Public surface revision contracts

Web API と MCP の life.txt writes は、`lifetxt.mutation` と同じ optimistic-concurrency contract を使えます。

revision-aware client はまず current writable-file revision を読みます。次の write は、その exact revision がまだ一致するときだけ accepted されます。これにより stale browser tab や MCP client が newer file を silent replace することを防ぎます。

## Web API

successful `/api/` read response は次を含みます。

```http
ETag: "<sha256>"
X-Lifetxt-Revision: <sha256>
```

client は `GET /api/revision` または `GET /api/capabilities` で strict revision contract を discover します。supported life.txt write endpoints は `If-Match` または `X-Lifetxt-Expected-Revision` を受け付けます。

legacy client が revision を送らない場合は transition fallback として accepted されますが、warning を返します。この fallback は old local API clients を壊さないための一時互換です。new code は revision を discover して送ってください。

strict write without revision は HTTP 428、stale revision は HTTP 409 conflict shape を返します。lifetxt は automatic three-way merge として扱いません。

## MCP

public JSON-RPC write 前に `get_file_state` を呼び、`file_hash` を保持します。revision-protected tools は `expected_file_hash` を input schema に publish します。successful results は new `revision` と `file_hash` を返します。

MCP は `get_capabilities` と `lifetxt://capabilities` も expose します。format/schema versions、operation matrix、read-only state、writable target、revision-precondition support を report します。

## Format-version mutation guard

shared mutation entry point は current/replacement text の `#! format_version:` を確認します。unsupported declared version は inspection には readable ですが、explicit migration なしの mutation は `UNSUPPORTED_FORMAT_VERSION` で fail します。

## Client implementation checklist

- 最初の write 前に writable revision を discover する。
- supported mutation では毎回 `If-Match` または `expected_file_hash` を送る。
- HTTP 428 は client bug として扱い、revision を取得し、intended change を作り直してから retry する。
- HTTP 409 は real conflict として扱い、reload して user/caller に次の edit を選ばせる。automatic merge はしない。

## Current boundary

timer/attachment operations は life.txt 以外の timer JSON state や attachment storage も modify するため、same atomicity guarantee を主張するには multi-target transaction design が必要です。real terminal, SMTP, browser accessibility, timezone boundary, release-gate CI, legacy fallback removal は separate roadmap items です。
