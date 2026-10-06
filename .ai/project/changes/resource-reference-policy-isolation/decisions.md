# Decisions

Owner accepted the concrete parent design on 2026-10-07. #1125 is the
separately tracked S unit from that decomposition. Self-review informational only;
independent latest-head human security/integration and merge approval pending.

- Full-suite config schema parity found that the existing direct v5 generator must expose the same new remote properties as the final v34 bundle. Both now share one helper; existing parity assertions remain unchanged. This is a minimal compatibility repair within the approved schema-generator scope.
