# Remaining adoption checks — #1358 / #1366

No check in this document has been marked passed by automation. Use only
synthetic records, a private local test build and an approved test host. Do not
upload real life.txt content or deploy the experimental checker for testing.

## Prepare a local build

```sh
npm ci --prefix contrib/browser_check_poc --ignore-scripts
python contrib/browser_check_poc/build.py --output .cache/manual-check-site
python -m http.server --bind 127.0.0.1 --directory .cache/manual-check-site 8765
```

Open `http://127.0.0.1:8765/`. Use a new output directory for each build. Keep
its `manifest.json`, browser/OS version and the date with the results. Physical
mobile testing needs a separately approved private local-network or secure
tunnel setup; localhost on a phone points to that phone, not the desktop.
Do not expose the experimental artifact publicly as a shortcut.

## Browser and device acceptance

| Check | Procedure | Evidence required | Current state |
| --- | --- | --- | --- |
| Firefox / WebKit | Run ENGINE_MATRIX.md on a supported host with required mode | Complete new matrix, exact probe/manifest hashes and no blocked engine | Blocked in original host; re-execution needed |
| Safari desktop / iPhone | Check lazy startup, Japanese input, warnings, cancel/retry, narrow layout and keyboard/touch | Browser/OS/device, steps and synthetic-only screenshots | Not tested |
| Android browser | Repeat initial and warm checks, switch app then return, cancel/retry | Real device/OS/browser and result | Not tested |
| Real network / memory pressure | Capture cold vs warm runs on a low-memory device and a realistic limited connection | Network conditions, elapsed times, memory measurement scope and failure/recovery | Not tested; paced desktop responses are only a simulation |

## Accessibility and Japanese rendering

Use this synthetic input:

```text
[ ] T "日本語の確認😀" due:wrong
```

1. Confirm the title is readable, Japanese IME composition is not interrupted,
   the W203 diagnostic is readable and nothing overlaps at 320/390px widths.
   The earlier container lacked CJK fonts; parsing success did not accept glyphs.
2. In a **desktop browser's menu**, select 200% zoom. Record the browser menu
   value and test input, Check, cancel and diagnostics. Check clipping, focus
   visibility, scrolling and operation by keyboard. Pinch scaling, CSS zoom,
   device scale factor and a small viewport do not establish this result.
3. With VoiceOver or NVDA (record versions), navigate to the labelled textbox,
   type the sample, activate Check and hear the live status. Navigate to and
   read diagnostics; then cancel, verify the clearing announcement and retry.
   Record actual speech and focus behavior using synthetic content. Automated
   accessibility-tree roles are only prerequisites for this test.

## Distribution and adoption decisions

RUNTIME_INVENTORY.md retains the component/source-delivery gaps. Independent
review must establish exact binary attribution and corresponding-source
delivery (including Pyodide and hiwire MPL portions). Sixteen notice snapshots
and source URLs do not by themselves close that review.

After the evidence above, the Owner decides the initial supported browsers,
parser-only scope, input/diagnostic/time budgets and whether to adopt. A later
implementation issue must define the limited public UI and script/CSP/artifact
allowlist. Human merge and publication/deployment approval stay separate.

## Result template

```text
Gate:
Date:
Artifact manifest SHA-256:
Probe SHA-256 (if automated):
Device / OS / browser / assistive technology versions:
Synthetic case and steps:
Observed result:
Status: passed / failed / blocked / not tested
Evidence reference:
Remaining limitation:
Reviewer:
```

Post sanitized results to #1358. A failed or unavailable check stays open;
neither merging the test harness nor an earlier browser run replaces it.
