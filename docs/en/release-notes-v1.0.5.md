# v1.0.5

v1.0.5 is the normal release with N=0 (the same release identity as 1.0.5.0). Highlights since v1.0.4.3:

## Highlights

- **Web UI:** Beginner-oriented creation, title-first forms, a purpose-based More menu, basic help and visibility settings, clearer Items labels, keyboard and mobile interactions. ([#1551](https://github.com/Eruhitsuji/lifetxt/pull/1551), [#1587](https://github.com/Eruhitsuji/lifetxt/pull/1587), [#1591](https://github.com/Eruhitsuji/lifetxt/pull/1591), [#1655](https://github.com/Eruhitsuji/lifetxt/pull/1655), [#1667](https://github.com/Eruhitsuji/lifetxt/pull/1667))
- **Task board:** Move, edit and add task cards by status in Items using existing revision-aware writes, with no automatic resend after conflicts or unknown results. URL restoration, mobile column navigation, drag guidance and direct calendar interaction have improved. Manual ordering within columns and custom columns are outside scope. ([#1613](https://github.com/Eruhitsuji/lifetxt/pull/1613), [#1615](https://github.com/Eruhitsuji/lifetxt/pull/1615), [#1629](https://github.com/Eruhitsuji/lifetxt/pull/1629), [#1651](https://github.com/Eruhitsuji/lifetxt/pull/1651))
- **Planning and review:** Improved Agenda/Calendar navigation and request recovery, Stats breakdown and date-range presentation, Graph relationship lists, detail drawers, bulk completion dates and Undo. Habit cues, minimum versions and rest recording are supported. ([#1481](https://github.com/Eruhitsuji/lifetxt/pull/1481), [#1483](https://github.com/Eruhitsuji/lifetxt/pull/1483), [#1557](https://github.com/Eruhitsuji/lifetxt/pull/1557), [#1559](https://github.com/Eruhitsuji/lifetxt/pull/1559), [#1570](https://github.com/Eruhitsuji/lifetxt/pull/1570), [#1576](https://github.com/Eruhitsuji/lifetxt/pull/1576), [#1579](https://github.com/Eruhitsuji/lifetxt/pull/1579), [#1585](https://github.com/Eruhitsuji/lifetxt/pull/1585))
- **Capture and data representation:** Explicit todo.txt capture and preview in CLI/Web/TUI, typed JSON details and state-based requires. A top-level JSON array supplies the value list for every key; nest an array to preserve it as a single value. Existing depends_on/blocks and the json:true literal are preserved. ([#1445](https://github.com/Eruhitsuji/lifetxt/pull/1445), [#1446](https://github.com/Eruhitsuji/lifetxt/pull/1446), [#1447](https://github.com/Eruhitsuji/lifetxt/pull/1447), [#1595](https://github.com/Eruhitsuji/lifetxt/pull/1595), [#1597](https://github.com/Eruhitsuji/lifetxt/pull/1597), [#1599](https://github.com/Eruhitsuji/lifetxt/pull/1599))
- **Desktop and notifications:** Enhanced native notifications; use `lifetxt_desktop --server-url https://example.com/` to open an existing server Web UI without launching a local runtime or exposing local-alert IPC to the remote window. ([#1593](https://github.com/Eruhitsuji/lifetxt/pull/1593), [#1653](https://github.com/Eruhitsuji/lifetxt/pull/1653))
- **Collaboration:** Ordinary Web startup, session controls and write availability follow workspace roles; integration tests cover revision conflicts. Live VPN/browser acceptance remains separate; arbitrary public-network deployment is not certified. ([#1640](https://github.com/Eruhitsuji/lifetxt/pull/1640), [#1644](https://github.com/Eruhitsuji/lifetxt/pull/1644), [#1647](https://github.com/Eruhitsuji/lifetxt/pull/1647))
- **Official website:** Bilingual JavaScript syntax checker, sample entry points and beginner practice. Browser-only checking is not equivalent to all Core validation; Pages publication is separate. ([#1535](https://github.com/Eruhitsuji/lifetxt/pull/1535), [#1538](https://github.com/Eruhitsuji/lifetxt/pull/1538), [#1601](https://github.com/Eruhitsuji/lifetxt/pull/1601), [#1603](https://github.com/Eruhitsuji/lifetxt/pull/1603))

## Upgrade and compatibility

Core and Mini use 1.0.5; Desktop uses the existing packaging synchronization. The independent Editor version is unchanged. Mini remains a strict subset. The version bump itself requires no life.txt migration. Do not assume older versions can process data that uses new typed JSON or requires features.

Back up data and configuration and follow the [distribution guide](distribution.md) for your channel. Verify writes, authentication, backups and restoration in a test environment before upgrading a server.

## Remaining work and verification boundaries

- Web UI improvements and real-environment acceptance remain tracked in [#1386](https://github.com/Eruhitsuji/lifetxt/issues/1386); browser coverage in [#318](https://github.com/Eruhitsuji/lifetxt/issues/318).
- Live workspace/VPN, exhaustive Desktop GUI acceptance, open Remote attachment and revision operational checks are not claimed complete.
- All 14 preflight targets, approval and distribution verification are tracked in [#1668](https://github.com/Eruhitsuji/lifetxt/issues/1668). Generated winget/Scoop/conda submissions are distinct from external registration.

[Full comparison (v1.0.4.3...v1.0.5)](https://github.com/Eruhitsuji/lifetxt/compare/v1.0.4.3...v1.0.5)
