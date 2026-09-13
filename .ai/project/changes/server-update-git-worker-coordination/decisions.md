# Decisions

- Keep the change in `server_init.py`; `server_update.py` already provides the
  required active-before-update and restoration semantics.
- Use one shared service-unit helper to prevent configuration/wrapper drift.
- Preserve worker-disabled output and behavior.
