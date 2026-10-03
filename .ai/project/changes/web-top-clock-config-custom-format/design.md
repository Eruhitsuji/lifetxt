# Design

Reuse cap-web-surface-structure. A small web_clock_config module validates and publishes six allowlisted fields, plus resolved main timezone metadata. The startup config path is captured once. /api/config reloads clock presentation values only; startup main timezone/auth/workspaces stay authoritative. File errors return a generic 503. In-memory callers keep their supplied config.

Intl produces calendar parts for IANA zones; a bounded greedy token parser renders textContent. Main local/host uses the server offset at page reload. ISO week-year is computed from the displayed calendar date. Formats use bracket literals; long text wraps. Kiosk retains its viewer-local formatter and shares the existing timer.

Verification covers actual API payload to JavaScript, CLI persistence on the same server, safety publication, DST/midnight/ISO year/leap boundaries, timer lifecycle and schema/registry alignment. Independent integration/browser review remains required before merge.
