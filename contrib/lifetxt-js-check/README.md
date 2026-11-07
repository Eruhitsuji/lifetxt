# life.txt JavaScript syntax checker

A read-only checker for a subset of Format 1 syntax. The shared `parser.mjs`
module uses browser APIs available in Node.js and takes a string. The Node.js
CLI requires Node.js 22 or later.

```sh
node check.mjs life.txt
```

Exit codes are 0 for no errors in checked syntax, 1 for syntax errors, 2 for
usage or input errors, and 3 for incomplete checks without syntax errors.
Inputs are limited to 16,384 UTF-8 bytes and output to 100 diagnostics.

The checker reads item headers, titles, details, and `|` body lines. It preserves
unknown and repeated detail keys. Joined lines and unsupported format versions
are reported as unchecked. Dates, IDs, references and inferred hierarchy are
outside the checked scope. Use `lifetxt check` for full validation.

The distribution ZIP contains the parser, CLI, this README, and LICENSE.
