# Decisions

- #1112 owner acceptance adopts Linux optional native helper under documented risks. #1115 continuation adopts Linux official / other OS unofficial and missing-prerequisite denial.
- Header-provided SYS_openat2 instead of guessed numeric syscall or ctypes fallback.
- O_PATH first avoids readable open of FIFO/device; private own-FD procfs conversion avoids original path reopening.
- Reject metadata/identity uncertainty instead of claiming a full hostile-writer snapshot guarantee.
- Runtime integration/packaging and final human approval remain separate. Rollback: revert this source/test/package change; no data mutation.
