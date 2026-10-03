# Design

`lifetxt.__init__` retains version, model, parser, and serializer exports only.
The new `lifetxt.core` module exposes the smallest practical shared operations.
The previous installer sequence is moved behind the explicit
`bootstrap_legacy_surfaces()` entrypoint and called by CLI dispatch. A guarded
bootstrap prevents installer re-entry while modules are being initialized.

This is platform-neutral: no Cloudflare, Pyodide, filesystem, or runtime-name
conditional is added to Core.
