from __future__ import unicode_literals


DIAGNOSTIC_CONTRACT_FIXTURES = (
    {
        "name": "malformed_line",
        "line": "not an item",
        "exit_code": 1,
        "diagnostics": [
            {
                "severity": "error",
                "code": "E002",
                "category": "syntax",
                "message": "Expected a status such as [ ], [/], [x], [-], [>], [?], or [N].",
                "line": 1,
                "column": 1,
                "hint": "Start item lines with a valid status marker such as [ ], followed by type and title.",
            },
        ],
    },
    {
        "name": "invalid_status",
        "line": "[X] T Bad_status",
        "exit_code": 1,
        "diagnostics": [
            {
                "severity": "error",
                "code": "E003",
                "category": "syntax",
                "message": "Invalid status '[X]'.",
                "line": 1,
                "column": 1,
                "hint": "Use one of [ ], [/], [x], [-], [>], [?], or [N] as the status marker.",
            },
        ],
    },
    {
        "name": "validator_warnings",
        "line": "[ ] T Parent from:not-a-date est:bananas",
        "exit_code": 0,
        "diagnostics": [
            {
                "severity": "warning",
                "code": "W202",
                "category": "time",
                "message": "from: should use YYYY-MM-DDTHH:MM, optionally with :SS, fractional seconds, and timezone.",
                "line": 1,
                "hint": "Rewrite the value as YYYY-MM-DDTHH:MM, optionally adding seconds, fractional seconds, or timezone.",
            },
            {
                "severity": "warning",
                "code": "W226",
                "category": "duration",
                "message": "est: duration 'bananas' is not recognized; use forms like 25m, 1h30m, or 90.",
                "line": 1,
                "hint": "Use a duration such as 25m, 1h30m, or 90.",
            },
        ],
    },
)
