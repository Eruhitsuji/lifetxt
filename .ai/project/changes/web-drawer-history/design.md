# Readable drawer history

Keep temporal-timeline-v1 authoritative for order, filtering, completeness and event counts. Reuse drawerDateValue for workspace timestamps; day headings follow the displayed workspace date. Status summaries retain raw status symbols. All unknown codes and payload values are escaped and never translated.

Show All/7d/30d/Custom, Apply and Clear. Custom expands labelled ISO fields without prompts; native details preserves keyboard access. Detailed filter open state is preserved across requests. UI labels are explicit because the drawer subtree protects user-owned data from automatic translation.

Completeness and warnings remain prominent. Known limitation codes get explanations; exact bounds, limitations, invalid events and diagnostic objects remain accessible as escaped JSON. Per-event time, record ID, transaction, revision, sequence and payload remain in technical details.

History loading is independent of Relations. Opening a drawer invalidates requests and resets filters. Requests bind a monotonic token, item identity and mounted panel. This prevents stale responses and errors from replacing newer filters or another record. No mutation request is introduced.
