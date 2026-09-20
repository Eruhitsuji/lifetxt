# Decisions

| Decision | Reason |
| --- | --- |
| Keep admission state process-local and bounded | Remote already enforces a single-worker process-local model; durable operation persistence would exceed #870's API/executor boundary. |
| Require an explicit structured runner prefix | No arbitrary unit or command is accepted from the request, while deployments can use their root-owned least-privilege wrapper. |
| Run service control in a daemon thread | `systemctl start` for a oneshot may wait for completion; HTTP admission must return 202 without running backup logic in the web worker. |
| Derive status from the existing backup status contract | It preserves local/remote outcome separation and avoids exposing journal, argv, stderr, paths, or remote targets. |
