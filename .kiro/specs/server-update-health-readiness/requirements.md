# Requirements Document

> **Authoritative copy lives in the change package, not here.**
>
> Distilled to `.ai/project/changes/server-update-health-readiness/`.

## Introduction

`lifetxt server-update` currently performs exactly one HTTP health request after restarting services. On a production Ubuntu Server deployment, systemd reported the Web service as started before Uvicorn began listening, so a fast connection-refused result produced `validated_health_check_failed` even though the service became healthy seconds later. Operators need `server-update` to distinguish normal startup latency from a genuinely unhealthy deployment without weakening any existing update safety gates.

## Boundary Context

- **In scope**: post-restart health readiness retry behavior, bounded timing configuration, health result evidence, tests, and Ubuntu deployment documentation.
- **Out of scope**: changing git update, package reinstall, backup, integrity validation, restart failure classification, automatic rollback, service manager implementations, or production data mutation behavior.
- **Adjacent expectations**: health retry runs only after validation and service restart; restart failures continue to use `validated_restart_incomplete` without attempting health checks.

## Requirements

### Requirement 1: Bounded Post-Restart Readiness

**Objective:** As a production operator, I want `server-update` to wait briefly for a restarted service to become HTTP-ready, so that normal startup latency is not reported as a failed deployment.

#### Acceptance Criteria

1. When a configured health endpoint initially returns a transient connection failure after services restart, the system shall retry within a bounded readiness deadline before reporting failure.
2. When any health attempt succeeds before the readiness deadline, the system shall return the update result as `updated` immediately.
3. If the readiness deadline expires without a healthy response, then the system shall preserve the existing `validated_health_check_failed` status.
4. If service restart itself fails, then the system shall preserve the existing `validated_restart_incomplete` behavior and shall not run health retry.

### Requirement 2: Health Evidence and Configuration

**Objective:** As a production operator, I want the health report and documentation to expose readiness timing, so that startup problems can be diagnosed and tuned safely.

#### Acceptance Criteria

1. When health checking runs, the system shall include attempts, elapsed seconds, and final status or error evidence in `health_check`.
2. The system shall provide conservative default retry timing and allow operators to configure the delay between failed attempts.
3. When a dry run reports an update is available, the system shall expose the health URL and readiness timing that would apply after restart.
4. The Ubuntu Server deployment documentation shall explain the readiness behavior and configuration.
