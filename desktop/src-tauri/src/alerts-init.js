(() => {
  // Tauri runs this before the served page's scripts. Only the spawned
  // companion's exact origin gets the bridge (and the matching Rust ACL).
  if (window.top === window && location.origin === "__LIFETXT_ORIGIN__") {
    const invoke = (command, args) => window.__TAURI_INTERNALS__.invoke(command, args);
    let enabled = false;
    let failed = false;
    const ready = invoke("desktop_alerts_enabled").then(value => { enabled = value; });
    // Web UI awaits ready before refreshing. Attach a handler immediately so
    // older companion runtimes can load without an unhandled rejection.
    void ready.catch(() => { failed = true; });
    window.lifetxtDesktopAlerts = {
      ready,
      get failed() { return failed; },
      get enabled() { return enabled; },
      async setEnabled(value) {
        await ready;
        await invoke("set_desktop_alerts_enabled", {enabled: value});
        enabled = value;
      },
      async send(test, manual, japanese) {
        await ready;
        return invoke("send_desktop_alert", {test, manual, japanese});
      },
    };
  }
})();
