# Mobile-first Planner

The Planner is a separate no-store `/planner` document assembled from packaged
HTML, CSS and JavaScript. It reads the existing `/api/agenda`, `/api/items`,
`/api/health`, `/api/config`, and `/api/command-center` routes. The latter gets
an optional strict ISO `date` query parameter; requests without it retain the
existing workspace-local today behavior. All writes reuse capture, complete,
create and item update routes. A separate manifest gives the Planner its own
launch URL; the Quick Capture manifest remains unchanged. There is no service
worker, offline cache or mutation queue.
