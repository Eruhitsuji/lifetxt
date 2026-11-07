# Shared JavaScript checker

Parent #1358, implementation #1534. One Standard slice delivers a pure .mjs
parser, a read-only Node CLI, and its CI packager. The browser integration can
import the same module and supply the input string without Node APIs.
Output includes ordered details, diagnostic codes and physical line numbers.
Line joins and unknown format versions mark the result incomplete.

Review input bounds, safe handling of user-provided keys, quote/escape behavior,
exit codes and ZIP contents. Use parser unit tests, Python Core comparison over
the documented intersection, and extracted-CLI smoke tests. An ordinary revert
removes the isolated tools and workflow. No user data or deployment migration.
