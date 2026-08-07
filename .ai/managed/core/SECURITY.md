# Security Standard

## Non-Overridable Rules

- Do not commit credentials, API keys, tokens, private keys, or session cookies.
- Do not paste secrets into AI prompts, issues, pull requests, logs, or tests.
- Do not weaken authentication, authorization, input validation, or audit logs
  without explicit approval.
- Do not disable security checks to make CI pass.

## Input and Command Safety

Validate untrusted input before using it in:

- database queries
- shell commands
- file paths
- URLs
- templates
- deserialization

Prefer structured APIs over string-built commands or queries.

## Security Review Triggers

Request focused security review when a change touches:

- authentication or authorization
- secrets handling
- dependency installation
- network access
- file upload/download
- encryption or signing
- GitHub Actions permissions

## Security Viewpoints

Use these viewpoints for design, implementation, and review:

- assets: what data, credentials, systems, or user actions are protected
- trust boundaries: where untrusted input enters the system
- authentication: identity is verified correctly
- authorization: users can access only allowed resources/actions
- input validation: malformed or malicious input is handled safely
- output handling: rendered output cannot inject scripts or commands
- secrets: credentials are stored, transmitted, and logged safely
- dependencies: added packages are necessary and maintained
- data protection: sensitive data is minimized and retained appropriately
- auditability: important security events are traceable
- fail-safe behavior: failures do not grant access or corrupt data
- operational security: CI/CD, scripts, and permissions are least-privilege

## AI-Specific Security Rules

- Do not ask AI tools to handle raw secrets.
- Do not paste production credentials into prompts or issue bodies.
- Do not let AI-generated code bypass validation, authorization, or audit logs.
- Treat AI-generated shell commands, migrations, and workflow changes as
  security-sensitive until reviewed.
- Require human review for security-sensitive changes before merge.

## Runtime Evidence Security

AI development history may contain source code, prompts, tool output, local
paths, environment values, private URLs, and accidentally exposed secrets.

- Keep runtime evidence collection local-first by default.
- Do not attach raw AI transcripts or raw history archives to public issues.
- Redact secrets, local paths, private URLs, and environment values before
  sharing findings.
- Require explicit human approval before enabling automatic upstream reporting.
- Use sanitized findings and stable fingerprints for deduplication.
