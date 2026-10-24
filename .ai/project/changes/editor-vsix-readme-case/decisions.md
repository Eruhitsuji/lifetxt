# Decisions

Use the exact lowercase README path emitted by pinned vsce, rather than case-folding all archive entries. This preserves strict inventory and duplicate detection. The test fixture models actual vsce output; missing/tampered README tests now reach the real path. Add a case-collision regression.

No product, version, dependency, workflow, or publication authority change. Independent final-head review and human merge approval remain pending.
