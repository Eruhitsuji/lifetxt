#!/usr/bin/env bash
set -euo pipefail
binary=${1:?usage: measure_lifetxt_mini.sh <binary>}
test -x "$binary"
echo "target: $(rustc -vV | sed -n 's/^host: //p')"
echo "rustc: $(rustc --version)"
echo "binary_size_bytes: $(stat -c '%s' "$binary")"
file "$binary"
ldd "$binary" 2>&1 || true
echo "startup_seconds:"
/usr/bin/time -f '%e' "$binary" done t1 >/dev/null
echo "peak_rss_kib:"
/usr/bin/time -f '%M' "$binary" done t1 >/dev/null
