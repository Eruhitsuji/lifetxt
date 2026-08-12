# Oversized File Responsibility Report

Run the informational report with:

```console
python scripts/report_oversized_files.py --output .cache/oversized-file-report.json
```

It compares current byte/line counts with the reviewed baseline from #366 and
retains each file's classification and follow-up. It does not fail on size and
does not treat static resources, fixtures, or intentionally cohesive modules as
defects. Growth is a review signal that must be interpreted with responsibility
and coupling evidence.
