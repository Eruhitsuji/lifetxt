# Design

Reuse the existing loopback HTTP Handler and unchanged PoC. Default Playwright
Firefox/WebKit settings, no CSP bypass. Statuses separate blocked prerequisites
from failed page acceptance and passed complete corpus. Chromium runs the
portable harness's positive path, not a substitute engine pass. Evidence records
capture hashes and subsequent harness-only corrections explicitly. Inputs are
synthetic; retained errors omit raw stacks and local profile paths.
