# Item Links

Two related, host-independent ways to refer to one lifetxt record by its
canonical `id:` value, so a reference does not have to embed a specific
Web deployment's host, port, or path (#835 / #840).

## Canonical identity: the `id:` detail

The `id:` detail on a record (or the configured `ids.key` when a workspace
uses a different key name) is the one stable identity every surface --
CLI, TUI, Web API, Web UI, MCP -- already resolves records by:
`GET /api/items/{id}` ([web.md](web.md)), `lifetxt.ids.resolve_item_by_id`,
MCP `get_item`, and the `?id=` Web deep link below all look the same id up
through the same exact-match resolver.

## `lifetxt://item/<id>` logical URI

```text
lifetxt://item/<id>
```

Example:

```text
lifetxt://item/task-001
```

This is a logical *identity* reference, not an address: it names a record
without saying which deployment, host, or port can resolve it. A Web
deployment translates it to its own local deep-link form
(`/?id=task-001`, see [Record Deep Links](web.md#record-deep-links)); other
clients (a script, a notification, a generated report) may resolve it
through their own item-opening mechanism.

An id requiring encoding (containing `/`, `?`, `#`, or a space) is
percent-encoded in the URI, for example `lifetxt://item/a%20b` for the id
`a b`.

### Parsing / formatting

`lifetxt.item_uri` (Python) is the one shared parser/resolver seam every
client should use rather than hand-parsing the URI independently:

```python
from lifetxt.item_uri import format_item_uri, parse_item_uri, web_deep_link

format_item_uri("task-001")
# -> "lifetxt://item/task-001"

parse_item_uri("lifetxt://item/task-001")
# -> "task-001"

web_deep_link("task-001", base_url="https://lifetxt.example.invalid")
# -> "https://lifetxt.example.invalid/?id=task-001"
```

The same seam is available from the CLI, with no life.txt file required
(this is pure identity translation, never an item lookup):

```sh
python -m lifetxt item-uri format task-001
python -m lifetxt item-uri format task-001 --base-url https://lifetxt.example.invalid
python -m lifetxt item-uri parse "lifetxt://item/task-001"
python -m lifetxt show "lifetxt://item/task-001" life.txt
```

`show` accepts either the ordinary ID or its logical URI, so the last command
is equivalent to `lifetxt show task-001 life.txt`. Malformed `lifetxt:` URIs
are reported as URI errors; a well-formed URI whose ID is absent remains an
ordinary item-not-found error.

### What counts as malformed vs. unknown

`parse_item_uri` (and `item-uri parse`) only validates the URI's own
*shape* -- scheme, a non-empty id segment, no unencoded `/`/`?`/`#` inside
that segment. It never checks whether a record with that id exists. A
syntactically well-formed URI that names a record nothing currently has
(or that a caller is not authorized to see) is a completely separate,
later failure -- "not found" or "forbidden" from whatever lookup the
caller performs next -- and is deliberately never conflated with
"malformed URI" here.

### Design constraints

- The persisted identity remains the ordinary `id:` detail in life.txt.
  This URI is only a portable *representation* of that identity, never a
  new identity system, and it is never written into life.txt itself.
- No OS-wide `lifetxt://` protocol handler is registered by this feature.
- Resolving a `lifetxt://item/<id>` URI never bypasses a caller's normal
  workspace, source, or authorization boundaries: translating the URI to
  an id, and then looking that id up, are two separate steps, and the
  second step is exactly the same lookup an ordinary `id:` reference
  already goes through.

## Record Deep Links (Web)

See [Record Deep Links](web.md#record-deep-links) in web.md for the
`?id=`/`?line=` Web UI deep-link and copy-link behavior (#838/#839).
