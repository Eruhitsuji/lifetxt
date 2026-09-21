# Decisions

## Fixed systemd D-Bus authorization

Use an opt-in generated Polkit rule instead of privilege escalation inside the
Web process. This preserves `NoNewPrivileges=true` and constrains authority to
one account, one verb, and one unit.

## Separate update and Remote dispatch paths

Keep the existing sudo wrapper for interactive `server-update`. Remote backup
dispatch uses the narrower Polkit/systemd path, avoiding an accidental expansion
of either boundary.
