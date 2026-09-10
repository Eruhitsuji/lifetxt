# Design

`get_native_timeline` is a thin adapter: it reads the configured items, delegates
to `native_timeline()`, and attaches the existing source-set revision. The
published Timeline schema permits that optional revision while CLI output stays
unchanged.
