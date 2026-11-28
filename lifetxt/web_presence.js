// Shared presence colors for the Desk and State surfaces.
const WebPresence = (() => {
  "use strict";
  const states = Object.freeze(["available", "busy", "focus", "meeting", "away", "offline", "commuting", "working", "sleeping"]);
  const classes = ["p-available", "p-busy", "p-focus", "p-busy", "p-away", "p-off", "p-away", "p-busy", "p-off"];
  const allowedClasses = new Set([...classes, "p-unknown"]);
  function tone(state, overrides) {
    const value = String(state || "").trim().toLowerCase();
    if (!value) return "p-unknown";
    const override = overrides?.[value];
    if (allowedClasses.has(override)) return override;
    return classes[states.indexOf(value)] || "p-unknown";
  }
  return {states, tone};
})();
