Warning: truncated output (original token count: 165498)
Total output lines: 18805

import argparse
import collections
import contextlib
import datetime
import html
import hashlib
import io
import json
import os
import re
import sys
import types
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .atomic import atomic_write_bytes as _shared_atomic_write_bytes
from .atomic import atomic_write_text as _shared_atomic_write_text
from .atomic import write_console_text as _write_console_text
from .config import (
    config_notification_recipient,
    config_paths,
    config_section,
    config_tag_aliases,
    config_template_text,
    config_team_aliases,
    config_team_members,
    config_templates,
    config_user_aliases,
    config_user_name,
    config_write_file,
    load_config,
)
from .agenda import (
    agenda_records,
    agenda_records_to_json,
    agenda_records_to_jsonl,
    agenda_records_to_life,
    filter_agenda_records,
    filter_items,
    format_match_time,
    format_agenda_table,
    parse_agenda_range,
    parse_optional_time_range,
    _format_table_row as _agenda_format_table_row,
    _table_cell as _agenda_table_cell,
    _first_detail_value,
    next_repeat_occurrence,
)
from .assist import (
    DETAIL_FLAGS,
    build_item_from_args,
    has_update_fields,
    item_to_assisted_line,
    prompt_item,
    update_text,
)
from .csvio import items_from_csv_text, items_to_csv
from .conversion import (
    conversion_capabilities,
    decode_text as decode_conversion_text,
    encode_items as encode_conversion_items,
    ensure_supported_pair as ensure_supported_conversion_pair,
)
from .demo import DEFAULT_COUNT as DEMO_DEFAULT_COUNT
from .demo import demo_text, parse_demo_base_datetime, parse_demo_types
from .diagnostic_contract import (
    DIAGNOSTIC_CATEGORIES,
    diagnostic_category,
    diagnostic_to_output_dict,
)
from .diagnostic_cascade import classify_cascade_roles
from .sarif import render_sarif
from .diagnostic_render import render_diagnostic_rich, render_diagnostics_summary
from .cli_taxonomy import render_success_guidance as _render_success_guidance
from .i18n import register_messages as _register_messages, translate as _t
from .ics import items_from_ics_text
from .init_presets import DEFAULT_PRESET as _INIT_DEFAULT_PRESET
from .init_presets import (
    preset_names,
    render_life_text as _render_init_life_text,
    validate_preset,
)
from .ids import (
    auto_ids_enabled,
    collect_item_ids,
    duplicate_id_diagnostics,
    ensure_item_id,
    id_audit,
    id_key_from_config,
    id_prefix_for_item,
)
from .links import (
    LinksCycleError,
    critical_path,
    dependency_blocker_records,
    dependency_chain_records,
    dependency_chains_to_dot,
    dependency_chains_to_mermaid,
    format_dependency_chain,
    format_link_table,
    link_records,
    links_to_dot,
    links_to_json,
    links_to_jsonl,
    links_to_mermaid,
    reference_diagnostics,
    shortest_path,
    topological_order,
)
from .markdown import markdown_to_html, markdown_to_plain
from .model import Diagnostic, Item
from . import native_codec
from . import sqlite_codec
from . import lifetxtz_codec
from .timezone_policy import local_now_naive, today as timezone_today
from .timeutil import format_datetime, parse_date_or_datetime, relative_time
from .notifier import (
    format_notification_email,
    format_notification_table,
    notification_email_subject,
    notification_records,
    records_to_json as notifications_to_json,
    records_to_jsonl as notifications_to_jsonl,
    watch_notifications,
)
from .parser import parse_directives, parse_line, parse_text
from .paths import expand_paths
from .serializer import (
    item_to_line,
    items_from_json_text,
    items_from_jsonl_text,
    items_to_json,
    items_to_jsonl,
)
from .status_summary import (
    format_status_table,
    latest_status_records,
    status_records_to_json,
    status_records_to_jsonl,
)
from .validator import validate_item
from .vm import DEFAULT_MAX_STEPS as VM_DEFAULT_MAX_STEPS


#: Human-readable text for a bounded set of beginner/daily commands
#: (`init`, `today`, `done`, `complete`), localized to English/Japanese
#: (#631/#632). Command names, options, and Format 1.0 syntax never
#: translate; only fixed labels/headings do. Every other command's plain
#: output stays exactly as it was.
_register_messages(
    {
        "init.overwrite_prompt": {
            "en": "File(s) already exist: {files}",
            "ja": "既にファイルが存在します: {files}",
        },
        "init.overwrite_confirm": {
            "en": "Overwrite? [y/N] ",
            "ja": "上書きしますか? [y/N] ",
        },
        "init.aborted": {"en": "Aborted.", "ja": "中止しました。"},
        "init.name_prompt": {
            "en": "Your name (for S presence records) [self]: ",
            "ja": "あなたの名前 (S presence 記録用) [self]: ",
        },
        "init.timezone_prompt": {
            "en": "Timezone (e.g. Asia/Tokyo, UTC) [UTC]: ",
            "ja": "タイムゾーン (例: Asia/Tokyo, UTC) [UTC]: ",
        },
        "init.project_prompt": {
            "en": "Default project name (leave blank to skip): ",
            "ja": "既定のプロジェクト名 (空欄で省略): ",
        },
        "init.preset_prompt": {
            "en": "Starter preset [{presets}] (leave blank for minimal): ",
            "ja": "Starter preset [{presets}] (空欄で minimal): ",
        },
        "init.wrote": {"en": "Wrote {path}", "ja": "書き込みました: {path}"},
        "init.next": {"en": "Next: {command}", "ja": "次に: {command}"},
        "today.brief_for": {
            "en": "{mode} brief for {date}",
            "ja": "{date} の{mode}ブリーフ",
        },
        "today.brief": {"en": "{mode} brief", "ja": "{mode}ブリーフ"},
        "today.mode.today": {"en": "Today", "ja": "今日"},
        "today.config_error": {
            "en": "  ! config has {n} error(s)",
            "ja": "  ! 設定に {n} 件のエラーがあります",
        },
        "today.now": {"en": "NOW", "ja": "現在"},
        "today.attention": {"en": "ATTENTION", "ja": "注意"},
        "today.projects_attention": {
            "en": "  Projects needing attention ({n}):",
            "ja": "  注意が必要なプロジェクト ({n}件):",
        },
        "today.tickets_attention": {
            "en": "  Tickets needing attention ({n}):",
            "ja": "  注意が必要なチケット ({n}件):",
        },
        "today.today_heading": {"en": "TODAY", "ja": "今日"},
        "today.next_actions": {"en": "NEXT ACTIONS", "ja": "次のアクション"},
        "today.next_actions_already_listed": {
            "en": "  (already listed above)",
            "ja": "  (上に表示済み)",
        },
        "today.next_actions_none": {
            "en": "  Nothing actionable.",
            "ja": "  実行可能な項目はありません。",
        },
        "today.blocked": {"en": "BLOCKED", "ja": "ブロック中"},
        "today.waiting_prefix": {"en": "(waiting)", "ja": "(待機中)"},
        "today.habits": {"en": "HABITS", "ja": "習慣"},
        "today.upcoming": {"en": "Upcoming ({n}d)", "ja": "今後の予定 ({n}日)"},
        "today.inbox": {"en": "INBOX", "ja": "受信箱"},
        "today.inbox_pending": {
            "en": "  {n} pending item(s)",
            "ja": "  未処理の項目 {n} 件",
        },
        "today.inbox_message": {
            "en": "  message: {title}",
            "ja": "  メッセージ: {title}",
        },
        "today.inbox_capture": {
            "en": "  capture: {title}",
            "ja": "  キャプチャ: {title}",
        },
        "today.all_clear": {"en": "All clear.", "ja": "問題ありません。"},
        "done.already": {
            "en": "Already done: {title}",
            "ja": "既に完了しています: {title}",
        },
        "done.done": {"en": "Done: {line}", "ja": "完了しました: {line}"},
        "done.logged": {
            "en": "Logged: {line} (streak: {streak} day(s))",
            "ja": "記録しました: {line} (連続 {streak} 日)",
        },
        "done.dry_run_would_mark": {
            "en": "[dry-run] Would mark done: {line}",
            "ja": "[dry-run] 完了としてマークする予定: {line}",
        },
        "done.dry_run_would_log": {
            "en": "[dry-run] Would log habit completion: {line} (streak: {streak} day(s))",
            "ja": "[dry-run] 習慣の完了を記録する予定: {line} (連続 {streak} 日)",
        },
        # Beginner-facing diagnostics (#633): check/lint/doctor's own
        # fixed labels and next-step guidance. Individual parser/validator
        # diagnostic hint text (hundreds of W/E codes) is out of scope for
        # this bounded slice and stays English-only; every diagnostic's raw
        # code, severity, and location data never localizes.
        "check.ok": {"en": "OK: {n} item(s)", "ja": "OK: {n} 件"},
        "check.ok_no_matching_diagnostics": {
            "en": "OK: {n} item(s), 0 matching diagnostic(s)",
            "ja": "OK: {n} 件、該当する diagnostic は 0 件",
        },
        "lint.no_issues": {
            "en": "No lint issues found.",
            "ja": "lint の問題は見つかりませんでした。",
        },
        "lint.typo_key": {
            "en": "Key {key!r} looks like a typo for {canonical!r}.",
            "ja": "キー {key!r} は {canonical!r} の typo の可能性があります。",
        },
        "lint.bad_casing": {
            "en": "Key {key!r} uses non-standard casing; expected {expected!r}.",
            "ja": "キー {key!r} の大文字/小文字表記が標準的ではありません "
            "(期待値: {expected!r})。",
        },
        "lint.duplicate_key": {
            "en": "Duplicate key {key!r} ({n} values). Consider using a "
            "multi-value list.",
            "ja": "キー {key!r} が重複しています ({n} 件の値)。"
            "複数値のリストとして扱うことを検討してください。",
        },
        "lint.fixed_summary": {
            "en": "Fixed {fixed} issue(s) in {files} file(s).",
            "ja": "{files} 個のファイルで {fixed} 件の問題を修正しました。",
        },
        "doctor.python_ok": {
            "en": "Python {major}.{minor}",
            "ja": "Python {major}.{minor}",
        },
        "doctor.python_fail": {
            "en": "Python {major}.{minor} (3.10+ required)",
            "ja": "Python {major}.{minor} (3.10 以上が必要です)",
        },
        "doctor.life_not_found": {
            "en": "Not found: {path} -- run: lifetxt init",
            "ja": "見つかりません: {path} -- 実行してください: lifetxt init",
        },
        "doctor.life_not_readable": {
            "en": "Not readable: {path}",
            "ja": "読み取れません: {path}",
        },
        "doctor.life_found": {"en": "Found: {path}", "ja": "見つかりました: {path}"},
        "doctor.config_not_found": {
            "en": "Not found: {path} -- run: lifetxt config init",
            "ja": "見つかりません: {path} -- 実行してください: lifetxt config init",
        },
        "doctor.config_found": {
            "en": "Found: {path}",
            "ja": "見つかりました: {path}",
        },
        "doctor.disk_warn": {
            "en": "{free_mib:.1f} MiB free on {dir} (below the 100 MiB safety floor)",
            "ja": "{dir} の空き容量は {free_mib:.1f} MiB です "
            "(安全ラインの 100 MiB を下回っています)",
        },
        "doctor.disk_ok": {
            "en": "{free_mib:.1f} MiB free on {dir}",
            "ja": "{dir} の空き容量は {free_mib:.1f} MiB です",
        },
        "doctor.check_fail": {
            "en": "{n} error(s) -- run: lifetxt check {path}",
            "ja": "{n} 件のエラー -- 実行してください: lifetxt check {path}",
        },
        "doctor.check_warn": {
            "en": "{n} warning(s) -- run: lifetxt check {path}",
            "ja": "{n} 件の警告 -- 実行してください: lifetxt check {path}",
        },
        "doctor.check_ok": {
            "en": "{n} item(s), no errors",
            "ja": "{n} 件、エラーなし",
        },
    }
)


def main(argv=None):
    from .cli_error_guidance import render_value_error_text

    try:
        argv, config_path, workspace_name = _extract_config_arg(argv)
    except ValueError as exc:
        sys.stderr.write(render_value_error_text(exc))
        return 1
    if argv and argv[0] == "fzf-preview":
        if len(argv) != 2:
            sys.stderr.write("ERROR: fzf-preview requires one token.\n")
            return 2
        from .fzf_helper import cmd_fzf_preview

        return cmd_fzf_preview(argparse.Namespace(token=argv[1]))
    parser = build_parser()
    args = parser.parse_args(argv)
    args.config = config_path
    args.workspace = workspace_name
    try:
        args.config_data = load_config(config_path)
    except ValueError as exc:
        sys.stderr.write(render_value_error_text(exc))
        return 1
    try:
        _maybe_apply_workspace(args)
    except ValueError as exc:
        sys.stderr.write(render_value_error_text(exc))
        return 1
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except ValueError as exc:
        sys.stderr.write(render_value_error_text(exc))
        return 1


def _extract_config_arg(argv):
    if argv is None:
        raw = list(sys.argv[1:])
    else:
        raw = list(argv)

    config_path = None
    workspace_name = None
    cleaned = []
    index = 0
    while index < len(raw):
        value = raw[index]
        if value == "--config":
            if index + 1 >= len(raw):
                raise ValueError("--config requires a path.")
            config_path = raw[index + 1]
            index += 2
            continue
        if value.startswith("--config="):
            config_path = value.split("=", 1)[1]
            index += 1
            continue
        if value == "--workspace":
            if index + 1 >= len(raw):
                raise ValueError("--workspace requires a name.")
            workspace_name = raw[index + 1]
            index += 2
            continue
        if value.startswith("--workspace="):
            workspace_name = value.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(value)
        index += 1
    return cleaned, config_path, workspace_name


def build_parser():
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="python -m lifetxt",
        description="Parser, validator, converter, and input helper for life.txt.",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version="lifetxt %s" % __version__,
    )
    parser.add_argument(
        "--config",
        help="External JSON config file. May also be set with LIFETXT_CONFIG.",
    )
    parser.add_argument(
        "--workspace",
        help="Named workspace to resolve inputs and write target from.",
    )
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="Check life.txt syntax and warnings.")
    _add_input_paths(check)
    check.add_argument(
        "--verify-files",
        action="store_true",
        help="Also verify file:/dir: content hashes. Reads every referenced file.",
    )
    check.add_argument(
        "--no-files",
        action="store_true",
        help="Skip file:/dir: attachment checks entirely.",
    )
    check.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="Diagnostic output format. sarif emits a SARIF 2.1.0 document "
        "(#644), built from the same filtered diagnostics as text/json.",
    )
    check.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )
    check.add_argument(
        "--ignore",
        action="append",
        dest="ignore_codes",
        metavar="CODE",
        help="Suppress a diagnostic code, e.g. W225. Can be repeated or comma-separated.",
    )
    check.add_argument(
        "--severity",
        dest="diagnostic_severities",
        action="append",
        help="Only show diagnostics with this severity, such as error or warning. Can be repeated or comma-separated.",
    )
    check.add_argument(
        "--code",
        dest="diagnostic_codes",
        action="append",
        help="Only show diagnostics with this code, such as E010 or W213. Can be repeated or comma-separated.",
    )
    check.add_argument(
        "--category",
        dest="diagnostic_categories",
        action="append",
        help="Only show diagnostics in this category: %s. Can be repeated or comma-separated."
        % ", ".join(DIAGNOSTIC_CATEGORIES),
    )
    check.set_defaults(func=command_check)

    integrity = subparsers.add_parser(
        "integrity",
        help="Run a read-only aggregate data-integrity report.",
    )
    _add_input_paths(integrity)
    integrity.add_argument(
        "--json",
        action="store_true",
        help="Emit the integrity report as JSON.",
    )
    integrity.add_argument(
        "--verify-files",
        action="store_true",
        help="Also verify file:/dir: content hashes. Reads every referenced file.",
    )
    integrity.add_argument(
        "--ai-context",
        action="store_true",
        help="Also run read-only AI-safe workspace and Personal AI Memory checks.",
    )
    integrity.add_argument(
        "--graph",
        action="store_true",
        help="Also run read-only relation-graph health checks: orphan "
        "items, most-referenced hubs, connected components, and the "
        "longest depends_on/blocks chain.",
    )
    integrity.add_argument(
        "--profile",
        choices=("default", "strict"),
        default="default",
        help="Severity profile for effective_severity mapping.",
    )
    integrity.add_argument(
        "--expected-revision",
        help="Required by `integrity apply`; expected current source revision.",
    )
    integrity.add_argument(
        "--confirm",
        action="store_true",
        help="Required by `integrity apply` before any write is performed.",
    )
    integrity.add_argument(
        "--prefix",
        help="Optional ID prefix for `integrity apply` missing-ID assignment.",
    )
    integrity.set_defaults(func=command_integrity)

    ids_command = subparsers.add_parser(
        "ids",
        help="Audit id details, missing IDs, and duplicate IDs.",
    )
    _add_input_paths(ids_command)
    ids_command.add_argument(
        "--key",
        help="Detail key to audit. Defaults to ids.key, api.id_key, or id.",
    )
    ids_command.add_argument(
        "--only",
        choices=("all", "present", "missing", "duplicates"),
        default="all",
        help="Limit the audit output. Defaults to all.",
    )
    ids_command.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    ids_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    ids_command.add_argument(
        "--assign",
        action="store_true",
        help="Assign IDs to items missing the selected ID key.",
    )
    ids_command.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned ID assignments without writing files.",
    )
    ids_command.add_argument(
        "--backup",
        action="store_true",
        help="Write a .bak backup before changing files with --assign.",
    )
    ids_command.add_argument(
        "--prefix",
        help="ID prefix to use with --assign. Defaults to the type-specific configured prefix.",
    )
    ids_command.set_defaults(func=command_ids)

    links_command = subparsers.add_parser(
        "links",
        help="Inspect id-based references such as parent:, ref:, depends_on:, blocks:, and related:.",
    )
    _add_input_paths(links_command)
    links_command.add_argument(
        "--id",
        dest="item_id",
        help="Show links connected to this id. Defaults to all links.",
    )
    links_command.add_argument(
        "--chain",
        metavar="ID",
        help="Show the dependency blocker chain for this item ID.",
    )
    links_command.add_argument(
        "--direction",
        choices=("incoming", "outgoing", "both"),
        default="both",
        help="Direction when --id is used. Defaults to both.",
    )
    links_command.add_argument(
        "--relation",
        action="append",
        help="Limit links to a relation key such as depends_on, blocks, parent, ref, or related. Can be repeated or comma-separated.",
    )
    links_command.add_argument(
        "--topo",
        action="store_true",
        help="Print a topological order over the depends_on/blocks graph "
        "(or the --relation subset). Refuses loudly on a cycle.",
    )
    links_command.add_argument(
        "--critical-path",
        action="store_true",
        help="Print the longest depends_on/blocks chain (or the --relation "
        "subset), optionally rooted at --chain ID.",
    )
    links_command.add_argument(
        "--path",
        nargs=2,
        metavar=("FROM", "TO"),
        help="Print the shortest chain of relations connecting two item IDs.",
    )
    links_command.add_argument(
        "--key",
        help="Detail key to use as the item ID. Defaults to ids.key, api.id_key, or id.",
    )
    links_command.add_argument(
        "--format",
        choices=("text", "json", "jsonl", "mermaid", "dot"),
        default="text",
        help="Output format.",
    )
    links_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    links_command.set_defaults(func=command_links)

    sources_command = subparsers.add_parser(
        "sources",
        help="Report which source file owns each parsed item.",
    )
    _add_input_paths(sources_command)
    sources_command.add_argument(
        "--key",
        help="Detail key to display as the item ID. Defaults to ids.key, api.id_key, or id.",
    )
    sources_command.add_argument(
        "--missing-id",
        action="store_true",
        help="Only show items missing the selected ID key.",
    )
    sources_command.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    sources_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    sources_command.set_defaults(func=command_sources)

    to_json = subparsers.add_parser("to-json", help="Convert life.txt to JSON array.")
    _add_input_paths(to_json)
    to_json.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    to_json.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    _add_item_filter_arguments(to_json)
    _add_occurrence_export_arguments(to_json)
    to_json.set_defaults(func=command_to_json)

    to_jsonl = subparsers.add_parser("to-jsonl", help="Convert life.txt to JSONL.")
    _add_input_paths(to_jsonl)
    to_jsonl.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(to_jsonl)
    _add_occurrence_export_arguments(to_jsonl)
    to_jsonl.set_defaults(func=command_to_jsonl)

    to_csv = subparsers.add_parser("to-csv", help="Convert life.txt to CSV.")
    _add_input_paths(to_csv)
    to_csv.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(to_csv)
    _add_occurrence_export_arguments(to_csv)
    to_csv.set_defaults(func=command_to_csv)

    demo = subparsers.add_parser(
        "demo",
        help="Generate a valid demo life.txt file.",
        description="Generate a valid demo life.txt file for testing CLI, Web UI, and API features.",
    )
    demo.add_argument(
        "-n",
        "--count",
        type=int,
        default=DEMO_DEFAULT_COUNT,
        help="Number of item records to generate. Defaults to %(default)s.",
    )
    demo.add_argument(
        "--date",
        help="Base date or datetime for generated records. Defaults to the current datetime.",
    )
    demo.add_argument(
        "--types",
        action="append",
        help="Comma-separated item types to generate, e.g. T,E,S,M,J. Defaults to all supported types.",
    )
    demo.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Deterministic seed for demo variation. Defaults to %(default)s.",
    )
    demo.add_argument(
        "--project",
        default="demo",
        help="Project detail value for generated project-aware records. Defaults to %(default)s.",
    )
    demo.add_argument(
        "--person",
        action="append",
        help="Person name for generated assignee/attendee/sender/recipient/status records. Can be repeated.",
    )
    demo.add_argument(
        "--start-index",
        type=int,
        help="First numeric suffix for demo IDs. Defaults to 1, or the next demo ID when --append is used.",
    )
    demo.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    demo.add_argument(
        "--append",
        action="store_true",
        help="Append to --output instead of overwriting it.",
    )
    demo.add_argument(
        "--no-check",
        action="store_true",
        help="Skip validation of generated demo text before output.",
    )
    demo.set_defaults(func=command_demo)

    markdown_command = subparsers.add_parser(
        "markdown",
        help="Render the safe life.txt Markdown subset from selected fields.",
    )
    _add_input_paths(markdown_command)
    markdown_command.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    markdown_command.add_argument(
        "--format",
        choices=("html", "text", "json", "jsonl"),
        default="html",
        help="Output format. Defaults to html.",
    )
    markdown_command.add_argument(
        "--field",
        action="append",
        help="Field to render: title, body, note, or all. Can be repeated or comma-separated. Defaults to body.",
    )
    markdown_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    _add_item_filter_arguments(markdown_command)
    markdown_command.set_defaults(func=command_markdown)

    import_ics = subparsers.add_parser(
        "import-ics",
        help="Convert iCalendar .ics VEVENT entries to life.txt event items.",
    )
    _add_import_core_arguments(import_ics)
    import_ics.add_argument(
        "--preset",
        choices=tuple(IMPORT_PRESETS),
        default="ics",
        help=(
            "Source preset. Default 'ics' converts VEVENT entries; "
            "'markdown' imports Markdown task lists, 'todoist' imports Todoist CSV exports, "
            "'github' imports GitHub Issues JSON exports, and 'life' parses/validates native "
            "life.txt through the authoritative parser before writing."
        ),
    )
    import_ics.set_defaults(func=command_import_ics)

    import_command = subparsers.add_parser(
        "import",
        help="Unified entry point for import-ics's presets: ics/markdown/todoist/github/life/...",
        description=(
            "Routing-only dispatcher over the existing import-ics implementation: "
            "no second ICS/Markdown/Todoist/GitHub/native conversion. A .ics input "
            "infers --preset ics, a .md/.markdown input infers --preset markdown, "
            "and a *.life.txt input infers --preset life; every other input "
            "(including .csv and .json) requires an explicit --preset."
        ),
    )
    _add_import_core_arguments(import_command)
    import_command.add_argument(
        "--preset",
        choices=tuple(IMPORT_PRESETS),
        default=None,
        help=(
            "Source preset. Inferred from the input file extension when omitted: "
            "'ics' for .ics, 'markdown' for .md/.markdown, 'life' for *.life.txt. "
            "Required for every other input, including .csv (todoist) and .json "
            "(github)."
        ),
    )
    import_command.set_defaults(func=command_import)

    export_command = subparsers.add_parser(
        "export",
        help="Unified entry point for exporting life.txt to json/jsonl/csv/markdown/life.",
        description=(
            "Routing-only dispatcher over the existing to-json/to-jsonl/to-csv/"
            "share exporters: no second JSON/JSONL/CSV/Markdown serializer. "
            "See EXPORT_FORMAT_HANDLERS for the small registration seam other "
            "formats (native life, sqlite, lifetxtz) extend."
        ),
    )
    _add_input_paths(export_command)
    export_command.add_argument(
        "--format",
        required=True,
        choices=sorted(EXPORT_FORMAT_HANDLERS),
        help="Output format.",
    )
    export_command.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout for text formats."
    )
    export_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON."
    )
    export_command.add_argument(
        "--canonical",
        action="store_true",
        help="For --format life: rewrite indentation as explicit parent: links.",
    )
    export_command.add_argument("--title", help="For --format markdown: report title.")
    export_command.add_argument(
        "--week",
        action="store_true",
        help="For --format markdown: restrict range label to the current ISO week.",
    )
    export_command.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="For --format markdown: restrict range label to a specific calendar month.",
    )
    _add_item_filter_arguments(export_command)
    _add_occurrence_export_arguments(export_command)
    export_command.set_defaults(func=command_export)

    convert_command = subparsers.add_parser(
        "convert",
        help="Convert explicitly between supported text formats.",
        description=(
            "Stateless source-to-target conversion through the shared lifetxt "
            "item model. Use --capabilities for the machine-readable format matrix."
        ),
    )
    convert_command.add_argument(
        "--from", dest="source_format", help="Explicit source format."
    )
    convert_command.add_argument(
        "--to", dest="target_format", help="Explicit target format."
    )
    convert_command.add_argument(
        "paths", nargs="*", help="Input path(s); defaults to stdin."
    )
    convert_command.add_argument(
        "-o", "--output", help="Output file; defaults to stdout."
    )
    convert_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    convert_command.add_argument(
        "--canonical",
        action="store_true",
        help="For life output, render explicit parent: links and remove indentation.",
    )
    convert_command.add_argument(
        "--calendar-name",
        default="lifetxt",
        help="For ICS output, set X-WR-CALNAME.",
    )
    convert_command.add_argument(
        "--capabilities",
        action="store_true",
        help="Print the conversion capability matrix as JSON and exit.",
    )
    convert_command.set_defaults(func=command_convert)

    sync_ics = subparsers.add_parser(
        "sync-ics",
        help="Fetch iCalendar .ics URLs and write generated life.txt event items.",
    )
    sync_ics.add_argument(
        "--url",
        action="append",
        default=[],
        help="iCalendar URL to fetch. Can be repeated.",
    )
    sync_ics.add_argument(
        "--url-env",
        action="append",
        default=[],
        help="Environment variable containing an iCalendar URL. Can be repeated.",
    )
    sync_ics.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    sync_ics.add_argument(
        "--cache-dir",
        help="Directory for raw downloaded .ics snapshots.",
    )
    sync_ics.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print generated life.txt without writing output or cache files.",
    )
    sync_ics.add_argument(
        "--merge-existing",
        action="store_true",
        help="Merge generated events into the existing output file by id: instead of replacing the file.",
    )
    sync_ics.add_argument(
        "--soft-delete-missing",
        action="store_true",
        help="With --merge-existing, mark existing source:ics events missing from the feed as canceled.",
    )
    sync_ics.add_argument(
        "--project",
        help="Add this project: detail to every synced event.",
    )
    sync_ics.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Add this tag: detail to every synced event. Can be repeated.",
    )
    sync_ics.add_argument(
        "--expand-rrule",
        action="store_true",
        help="Write one record per occurrence instead of a single record with repeat:RRULE:.",
    )
    sync_ics.add_argument(
        "--expand-until",
        help="Expand occurrences up to this date. Defaults to one year out.",
    )
    sync_ics.add_argument(
        "--expand-count",
        type=int,
        help="Maximum occurrences per recurring event. Capped at 500.",
    )
    sync_ics.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Fetch timeout in seconds. Defaults to 30.",
    )
    sync_ics.add_argument(
        "--user-agent",
        default="lifetxt/ics-sync",
        help="HTTP User-Agent header.",
    )
    sync_ics.set_defaults(func=command_sync_ics)

    serve = subparsers.add_parser(
        "serve",
        help="Run the optional FastAPI REST API and browser GUI.",
        description="Run the optional FastAPI REST API and browser GUI.",
    )
    _add_serve_core_arguments(serve)
    serve.add_argument(
        "--mcp",
        action="store_true",
        help="Run the stdio MCP server instead of the FastAPI HTTP server.",
    )
    serve.set_defaults(func=command_serve)

    web_command = subparsers.add_parser(
        "web",
        help="Start the local lifetxt Web UI and open it in your browser.",
        description=(
            "Convenience launcher for the existing Web UI: starts the same "
            "server as `serve` and opens your default browser to it. Use "
            "`serve` directly for server/deployment-oriented options such "
            "as --mcp."
        ),
    )
    _add_serve_core_arguments(web_command)
    web_command.add_argument(
        "--no-open",
        action="store_true",
        help="Start the server without opening a browser.",
    )
    web_command.set_defaults(func=command_web)

    mcp = subparsers.add_parser(
        "mcp",
        help="Run the stdio MCP server for AI clients.",
        description="Run a JSON-RPC stdio MCP server exposing life.txt tools.",
    )
    mcp.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to read. Defaults to life.txt or config paths.",
    )
    mcp.add_argument(
        "--write-file",
        help="File used for create, update, and delete tools. Defaults to config write_file or the first path.",
    )
    mcp.add_argument(
        "--read-only",
        action="store_true",
        help="Disable MCP write tools. Equivalent to --profile read.",
    )
    mcp.add_argument(
        "--profile",
        choices=["read", "assist", "full"],
        default=None,
        help=(
            "MCP permission profile. 'read' allows only non-mutating tools "
            "(equivalent to --read-only); 'assist' additionally allows "
            "stage_proposal (Unified Inbox proposal staging), nothing else; "
            "'full' is today's unrestricted default. Conflicts with "
            "--read-only unless --profile read is also given."
        ),
    )
    mcp.add_argument(
        "--no-open-world",
        action="store_true",
        help=(
            "Deny every open-world tool (one that makes an outbound "
            "network call, e.g. remote_test_connection/"
            "remote_list_resources/remote_get_resource) regardless of "
            "--profile. Independent of and combinable with any profile."
        ),
    )
    mcp.set_defaults(func=command_mcp)

    ai_command = subparsers.add_parser(
        "ai",
        help="AI client integration helpers.",
    )
    ai_subparsers = ai_command.add_subparsers(dest="ai_command")
    ai_setup = ai_subparsers.add_parser(
        "setup",
        help="Print ready-to-use AI client setup information.",
    )
    ai_setup_subparsers = ai_setup.add_subparsers(dest="ai_setup_command")
    ai_setup_generic = ai_setup_subparsers.add_parser(
        "generic",
        help=(
            "Print the lifetxt mcp command and a generic MCP client "
            "configuration for the current workspace. Writes nothing."
        ),
    )
    ai_setup_generic.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to reference. Defaults to life.txt or config paths.",
    )
    ai_setup_generic.add_argument(
        "--write-file",
        help="File the printed command uses as its write target.",
    )
    ai_setup_generic.add_argument(
        "--profile",
        choices=["read", "assist", "full"],
        default="read",
        help="Permission profile to emit. Defaults to 'read'.",
    )
    ai_setup_generic.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. Defaults to text.",
    )
    ai_setup_generic.set_defaults(func=command_ai_setup_generic)

    ai_setup_claude = ai_setup_subparsers.add_parser(
        "claude",
        help=(
            "Print Claude Desktop and Claude Code setup information "
            "for the current workspace. Writes nothing."
        ),
    )
    ai_setup_claude.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to reference. Defaults to life.txt or config paths.",
    )
    ai_setup_claude.add_argument(
        "--write-file",
        help="File the printed command uses as its write target.",
    )
    ai_setup_claude.add_argument(
        "--profile",
        choices=["read", "assist", "full"],
        default="read",
        help="Permission profile to emit. Defaults to 'read'.",
    )
    ai_setup_claude.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. Defaults to text.",
    )
    ai_setup_claude.set_defaults(func=command_ai_setup_claude)

    ai_setup_gemini = ai_setup_subparsers.add_parser(
        "gemini",
        help=(
            "Print Gemini CLI setup information for the current "
            "workspace. Writes nothing."
        ),
    )
    ai_setup_gemini.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to reference. Defaults to life.txt or config paths.",
    )
    ai_setup_gemini.add_argument(
        "--write-file",
        help="File the printed command uses as its write target.",
    )
    ai_setup_gemini.add_argument(
        "--profile",
        choices=["read", "assist", "full"],
        default="read",
        help="Permission profile to emit. Defaults to 'read'.",
    )
    ai_setup_gemini.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. Defaults to text.",
    )
    ai_setup_gemini.set_defaults(func=command_ai_setup_gemini)

    ai_doctor = ai_subparsers.add_parser(
        "doctor",
        help=(
            "Check whether the workspace will load and resolve a write "
            "target cleanly for a direct MCP connection. Writes nothing."
        ),
    )
    ai_doctor.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to check. Defaults to life.txt or config paths.",
    )
    ai_doctor.add_argument(
        "--write-file",
        help="File to check as the write target.",
    )
    ai_doctor.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. Defaults to text.",
    )
    ai_doctor.set_defaults(func=command_ai_doctor)

    config_command = subparsers.add_parser(
        "config",
        help="Create or inspect an external JSON config file.",
    )
    config_subparsers = config_command.add_subparsers(dest="config_command")
    config_init = config_subparsers.add_parser(
        "init",
        help="Write a starter config file.",
    )
    config_init.add_argument(
        "-o",
        "--output",
        default=".lifetxt.json",
        help="Config file to write. Defaults to .lifetxt.json.",
    )
    config_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    config_init.set_defaults(func=command_config_init)
    config_show = config_subparsers.add_parser(
        "show",
        help="Print the loaded config as JSON.",
    )
    config_show.set_defaults(func=command_config_show)

    config_effective = config_subparsers.add_parser(
        "effective",
        help="Print effective config after defaults, profile, and env precedence.",
    )
    config_effective.add_argument("--profile", help="Named profile to apply.")
    config_effective.set_defaults(func=command_config_effective)

    config_sources = config_subparsers.add_parser(
        "sources",
        help="Show each effective key with its value and provenance.",
    )
    config_sources.add_argument("--profile", help="Named profile to apply.")
    config_sources.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON rows."
    )
    config_sources.set_defaults(func=command_config_sources)

    config_get = config_subparsers.add_parser(
        "get", help="Print one effective value by dotted path (a.b.c)."
    )
    config_get.add_argument("path", help="Dotted config path, e.g. defaults.timezone.")
    config_get.add_argument("--profile", help="Named profile to apply.")
    config_get.set_defaults(func=command_config_get)

    config_set = config_subparsers.add_parser(
        "set", help="Set one config value by dotted path and write the file."
    )
    config_set.add_argument("path", help="Dotted config path, e.g. web.port.")
    config_set.add_argument("value", help="New value (parsed as JSON, else string).")
    config_set.add_argument(
        "-o", "--output", help="Config file to write. Defaults to the loaded file."
    )
    config_set.add_argument(
        "--expected-revision",
        help="Refuse the write unless the file still has this revision "
        "(see: lifetxt config revision).",
    )
    config_set.set_defaults(func=command_config_set)

    config_unset = config_subparsers.add_parser(
        "unset", help="Remove one config value by dotted path and write the file."
    )
    config_unset.add_argument("path", help="Dotted config path to remove.")
    config_unset.add_argument(
        "-o", "--output", help="Config file to write. Defaults to the loaded file."
    )
    config_unset.add_argument(
        "--expected-revision",
        help="Refuse the write unless the file still has this revision "
        "(see: lifetxt config revision).",
    )
    config_unset.set_defaults(func=command_config_unset)

    config_revision_cmd = config_subparsers.add_parser(
        "revision",
        help="Print the exact revision of the configuration file.",
    )
    config_revision_cmd.add_argument(
        "-o", "--output", help="Config file to inspect. Defaults to the loaded file."
    )
    config_revision_cmd.set_defaults(func=command_config_revision)

    config_explain = config_subparsers.add_parser(
        "explain", help="Explain a config key using the authoritative registry."
    )
    config_explain.add_argument("path", help="Dotted config path to explain.")
    config_explain.set_defaults(func=command_config_explain)

    config_check = config_subparsers.add_parser(
        "check", help="Validate the config against config-v1 and the credential policy."
    )
    config_check.add_argument("--json", action="store_true", help="Emit JSON.")
    config_check.set_defaults(func=command_config_check)

    config_migrate = config_subparsers.add_parser(
        "migrate",
        help="Migrate legacy paths/write_file into the versioned workspace model.",
    )
    config_migrate.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing."
    )
    config_migrate.add_argument(
        "-o", "--output", help="Config file to write. Defaults to the loaded file."
    )
    config_migrate.add_argument(
        "--expected-revision",
        help="Refuse the write unless the file still has this revision "
        "(see: lifetxt config revision).",
    )
    config_migrate.set_defaults(func=command_config_migrate)

    workspace_command = subparsers.add_parser(
        "workspace",
        help="Inspect and validate named workspaces and their source manifests.",
    )
    workspace_subparsers = workspace_command.add_subparsers(dest="workspace_command")
    ws_list = workspace_subparsers.add_parser(
        "list", help="List configured workspaces."
    )
    ws_list.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_list.set_defaults(func=command_workspace_list)

    ws_show = workspace_subparsers.add_parser(
        "show", help="Show one workspace's resolved source manifest."
    )
    ws_show.add_argument(
        "name", nargs="?", help="Workspace name. Defaults to the default workspace."
    )
    ws_show.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_show.set_defaults(func=command_workspace_show)

    ws_files = workspace_subparsers.add_parser(
        "files", help="List the files a workspace resolves to."
    )
    ws_files.add_argument(
        "name", nargs="?", help="Workspace name. Defaults to the default workspace."
    )
    ws_files.add_argument(
        "--resolved",
        action="store_true",
        help="Show role, mode, origin, and resolved path for each file.",
    )
    ws_files.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_files.set_defaults(func=command_workspace_files)

    ws_validate = workspace_subparsers.add_parser(
        "validate", help="Validate a workspace and report diagnostics."
    )
    ws_validate.add_argument(
        "name", nargs="?", help="Workspace name. Defaults to the default workspace."
    )
    ws_validate.add_argument(
        "--all", action="store_true", help="Validate every workspace."
    )
    ws_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_validate.set_defaults(func=command_workspace_validate)

    ws_doctor = workspace_subparsers.add_parser(
        "doctor", help="Aggregate health of every workspace and shared files."
    )
    ws_doctor.add_argument("--json", action="store_true", help="Emit JSON.")
    ws_doctor.set_defaults(func=command_workspace_doctor)

    project_command = subparsers.add_parser(
        "project",
        help="List, inspect, and manage projects built from project: records.",
    )
    project_subparsers = project_command.add_subparsers(dest="project_command")

    proj_list = project_subparsers.add_parser(
        "list", help="List projects with progress and health."
    )
    _add_input_paths(proj_list)
    proj_list.add_argument(
        "--all", action="store_true", help="Include archived projects."
    )
    proj_list.add_argument("--area", help="Only projects in this area.")
    proj_list.add_argument("--owner", help="Only projects with this owner.")
    proj_list.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_list.set_defaults(func=command_project_list)

    proj_show = project_subparsers.add_parser(
        "show", help="Show one project's aggregated hub."
    )
    proj_show.add_argument("name", help="Project name.")
    _add_input_paths(proj_show)
    proj_show.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_show.set_defaults(func=command_project_show)

    proj_health = project_subparsers.add_parser(
        "health", help="Show project health with formula."
    )
    proj_health.add_argument("name", nargs="?", help="Project name; omit with --all.")
    proj_health.add_argument(
        "--all", action="store_true", help="Health for every project."
    )
    _add_input_paths(proj_health)
    proj_health.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_health.set_defaults(func=command_project_health)

    proj_timeline = project_subparsers.add_parser(
        "timeline", help="Show dated project items in order."
    )
    proj_timeline.add_argument("name", help="Project name.")
    _add_input_paths(proj_timeline)
    proj_timeline.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_timeline.set_defaults(func=command_project_timeline)

    proj_workload = project_subparsers.add_parser(
        "workload", help="Show per-assignee workload."
    )
    proj_workload.add_argument("name", help="Project name.")
    _add_input_paths(proj_workload)
    proj_workload.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_workload.set_defaults(func=command_project_workload)

    proj_risks = project_subparsers.add_parser(
        "risks", help="List project risks by severity."
    )
    proj_risks.add_argument("name", help="Project name.")
    _add_input_paths(proj_risks)
    proj_risks.add_argument("--json", action="store_true", help="Emit JSON.")
    proj_risks.set_defaults(func=command_project_risks)

    proj_new = project_subparsers.add_parser(
        "new", help="Append a project metadata record."
    )
    proj_new.add_argument("name", help="Project name.")
    proj_new.add_argument("--owner", help="Project owner.")
    proj_new.add_argument("--area", help="Project area.")
    proj_new.add_argument(
        "--state", default="active", help="Project state. Default active."
    )
    proj_new.add_argument("--due", help="Target/due date.")
    proj_new.add_argument("--start", help="Start date.")
    proj_new.add_argument("--visibility", help="Visibility classification.")
    proj_new.add_argument(
        "--to", help="File to append to. Defaults to the write target."
    )
    proj_new.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    proj_new.set_defaults(func=command_project_new)

    proj_add = project_subparsers.add_parser(
        "add", help="Append a milestone/risk/decision/meeting record."
    )
    proj_add.add_argument(
        "record_type", choices=["milestone", "risk", "decision", "meeting"]
    )
    proj_add.add_argument("project", help="Project name.")
    proj_add.add_argument("title", help="Record title.")
    proj_add.add_argument("--due", help="Due date (milestone).")
    proj_add.add_argument(
        "--severity", default="medium", help="Risk severity. Default medium."
    )
    proj_add.add_argument("--state", default="open", help="Risk state. Default open.")
    proj_add.add_argument("--owner", help="Owner/assignee.")
    proj_add.add_argument("--on", help="Decision/meeting date.")
    proj_add.add_argument("--at", help="Meeting time.")
    proj_add.add_argument(
        "--to", help="File to append to. Defaults to the write target."
    )
    proj_add.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    proj_add.set_defaults(func=command_project_add)

    proj_archive = project_subparsers.add_parser(
        "archive",
        help="Move a project's done/canceled records to the workspace's archive source.",
    )
    proj_archive.add_argument("name", help="Project name.")
    _add_input_paths(proj_archive)
    proj_archive.add_argument(
        "--dest",
        help="Archive file to append items to. Defaults to the active workspace's "
        "role: archive source.",
    )
    proj_archive.add_argument(
        "--revision",
        action="append",
        default=[],
        metavar="PATH=SHA256",
        help="Expected revision for a source or destination path. Can be repeated.",
    )
    proj_archive.add_argument(
        "--status",
        action="append",
        dest="statuses",
        metavar="STATUS",
        help=(
            "Only archive items with this status. Can be repeated or comma-separated. "
            "Defaults to done,canceled."
        ),
    )
    proj_archive.add_argument(
        "--before",
        metavar="DATE",
        help="Only archive items whose done: or updated: date is before DATE (YYYY-MM-DD).",
    )
    proj_archive.add_argument(
        "--max-items",
        type=int,
        dest="max_items",
        metavar="N",
        help="Maximum number of items to archive.",
    )
    proj_archive.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show which items would be archived without writing any changes.",
    )
    proj_archive.add_argument(
        "--copy",
        action="store_true",
        help="Copy items to the archive without removing them from the source file.",
    )
    proj_archive.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    proj_archive.add_argument(
        "--orphan-children",
        dest="orphan_children",
        choices=("block", "adopt", "promote"),
        default="block",
        help=(
            "How to handle open children of archived parents: "
            "block (default) refuses to archive, "
            "adopt archives open children together (marking them [-]), "
            "promote archives the parent only and removes parent: from orphaned children."
        ),
    )
    proj_archive.add_argument(
        "--preserve-structure",
        action="store_true",
        dest="preserve_structure",
        help=(
            "Copy comment lines and blank lines verbatim to both the archive file "
            "and the source remainder so section headings remain intact."
        ),
    )
    proj_archive.add_argument(
        "--block-on-external-refs",
        action="store_true",
        dest="block_on_external_refs",
        help=(
            "Treat cross-file or intra-file references to archived items as errors "
            "instead of warnings. Requires --dry-run or a live run to check."
        ),
    )
    proj_archive.add_argument(
        "--emit-plan",
        metavar="PATH",
        dest="emit_plan",
        help=(
            "Write a schema-valid archive-plan-v1 JSON document to PATH instead "
            "of writing any change. Requires --dry-run. See lifetxt project "
            "archive --apply-plan to review and later apply the plan."
        ),
    )
    proj_archive.add_argument(
        "--apply-plan",
        metavar="PLAN",
        dest="apply_plan",
        help=(
            "Verify PLAN (an archive-plan-v1 document from --emit-plan) against "
            "current state and, if nothing has drifted, archive using the "
            "plan's frozen parameters. Mutually exclusive with --revision."
        ),
    )
    proj_archive.set_defaults(func=command_project_archive)

    portfolio_command = subparsers.add_parser(
        "portfolio", help="Compare projects by state, progress, risk, and workload."
    )
    _add_input_paths(portfolio_command)
    portfolio_command.add_argument(
        "--all", action="store_true", help="Include archived projects."
    )
    portfolio_command.add_argument("--json", action="store_true", help="Emit JSON.")
    portfolio_command.set_defaults(func=command_portfolio)

    today_command = subparsers.add_parser(
        "today",
        help="Daily command center: overdue, due, blocked, messages, and project attention.",
    )
    _add_input_paths(today_command)
    today_command.add_argument(
        "--mode",
        choices=["today", "morning", "evening"],
        default="today",
        help="Brief mode label. Default today.",
    )
    today_command.add_argument(
        "--horizon", type=int, default=3, help="Upcoming horizon in days. Default 3."
    )
    today_command.add_argument(
        "--person", help="Scope unacknowledged messages to a recipient."
    )
    today_scope = today_command.add_mutually_exclusive_group()
    today_scope.add_argument(
        "--saved-view",
        dest="saved_view",
        metavar="NAME",
        help=(
            "Scope today to one configured saved view instead of every item "
            "(see `lifetxt view list`). Mutually exclusive with --area."
        ),
    )
    today_scope.add_argument(
        "--area",
        metavar="NAME",
        help=(
            "Scope today to one life area instead of every item "
            "(see `lifetxt area list`). Mutually exclusive with --saved-view."
        ),
    )
    today_command.add_argument("--json", action="store_true", help="Emit JSON.")
    today_command.set_defaults(func=command_today)

    area_command = subparsers.add_parser(
        "area", help="Group tasks and projects by area:."
    )
    area_subparsers = area_command.add_subparsers(dest="area_command")
    area_list = area_subparsers.add_parser("list", help="List areas with progress.")
    _add_input_paths(area_list)
    area_list.add_argument("--json", action="store_true", help="Emit JSON.")
    area_list.set_defaults(func=command_area_list)
    area_show = area_subparsers.add_parser(
        "show", help="Show one area's projects and open work."
    )
    area_show.add_argument("name", help="Area name.")
    _add_input_paths(area_show)
    area_show.add_argument("--json", action="store_true", help="Emit JSON.")
    area_show.set_defaults(func=command_area_show)

    backlinks_command = subparsers.add_parser(
        "backlinks", help="Show items that reference a given ID (incoming links)."
    )
    backlinks_command.add_argument("id", help="Target item ID.")
    _add_input_paths(backlinks_command)
    backlinks_command.add_argument("--json", action="store_true", help="Emit JSON.")
    backlinks_command.set_defaults(func=command_backlinks)

    temporal_command = subparsers.add_parser(
        "temporal",
        help="Show one item's derived temporal context: overdue/due/staleness "
        "and nearby dated items.",
    )
    temporal_command.add_argument("id", help="Target item ID.")
    _add_input_paths(temporal_command)
    temporal_command.add_argument(
        "--window",
        type=int,
        default=7,
        help="Days on either side of the target's own date to consider for "
        "same_day/before/after. Default 7.",
    )
    temporal_command.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum related items returned. Default 20.",
    )
    temporal_command.add_argument(
        "--stale-after",
        type=int,
        default=None,
        help="Days of inactivity before stale_since applies. Default 14.",
    )
    temporal_command.add_argument("--json", action="store_true", help="Emit JSON.")
    temporal_command.set_defaults(func=command_temporal)

    timeline_command = subparsers.add_parser(
        "timeline",
        help="Show one item's bounded native semantic history without Git composition.",
    )
    timeline_command.add_argument("id", nargs="?", help="Target item ID.")
    timeline_command.add_argument(
        "--workspace-timeline",
        action="store_true",
        help="Show one bounded chronological stream across workspace items.",
    )
    timeline_command.add_argument(
        "--project", help="Workspace Timeline project filter (current evidence only)."
    )
    _add_input_paths(timeline_command)
    timeline_command.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum valid events returned (0-500). Default 100.",
    )
    timeline_command.add_argument(
        "--since",
        help="Include events at/after this offset-aware ISO date-time.",
    )
    timeline_command.add_argument(
        "--until",
        help="Include events at/before this offset-aware ISO date-time.",
    )
    timeline_command.add_argument(
        "--event",
        help="Include only this normalized event type.",
    )
    timeline_command.add_argument(
        "--as-of",
        metavar="TIMESTAMP",
        help=(
            "Reconstruct known/partial/unavailable field state at this "
            "offset-aware RFC3339 timestamp (semantic-as-of-v1), alongside "
            "the bounded event list. Cannot be combined with --summary, "
            "an analysis flag, or --compare-window/--to-window."
        ),
    )
    timeline_command.add_argument(
        "--compare-window",
        metavar="START..END",
        help="Compare this inclusive window with --to-window.",
    )
    timeline_command.add_argument(
        "--to-window",
        metavar="START..END",
        help="Second inclusive window for lifecycle comparison.",
    )
    timeline_command.add_argument(
        "--summary",
        action="store_true",
        help="Summarize filtered valid lifecycle events.",
    )
    for _flag, _help in (
        ("duration", "Analyze created-to-completed duration."),
        ("status-dwell", "Analyze closed status dwell intervals."),
        ("schedule-analysis", "Analyze schedule revisions."),
        ("relation-analysis", "Analyze lifecycle relation churn."),
        ("completion-cycles", "Analyze completion and reopen cycles."),
        ("transitions", "Analyze status transition pairs."),
        ("gaps", "Analyze captured-event gaps."),
        ("cadence", "Analyze captured-event cadence."),
        ("oscillation", "Analyze status oscillations."),
        ("provenance-analysis", "Analyze event provenance."),
        ("progress-analysis", "Analyze progress velocity."),
        ("effort", "Analyze recorded ticket effort."),
        ("schedule-lead-time", "Analyze schedule-change lead time."),
        ("due-variance", "Analyze due-versus-completion variance."),
    ):
        timeline_command.add_argument("--" + _flag, action="store_true", help=_help)
    timeline_command.add_argument("--json", action="store_true", help="Emit JSON.")
    timeline_command.set_defaults(func=command_timeline)

    history_check_command = subparsers.add_parser(
        "history-check",
        help="Verify Native History against bounded Git semantic evidence.",
    )
    _add_input_paths(history_check_command)
    history_check_command.add_argument(
        "--id", dest="item_id", help="Limit verification to one item ID."
    )
    history_check_command.add_argument(
        "--commit-limit",
        type=int,
        default=100,
        help="Maximum path-affecting Git commits examined (1-500). Default 100.",
    )
    history_check_command.add_argument("--json", action="store_true", help="Emit JSON.")
    history_check_command.set_defaults(func=command_history_check)

    thread_command = subparsers.add_parser(
        "thread",
        help="Show one item's explicit lifecycle thread plus derived temporal context.",
    )
    thread_command.add_argument("id", help="Target item ID.")
    _add_input_paths(thread_command)
    thread_command.add_argument(
        "--depth",
        type=int,
        default=8,
        help="Maximum explicit traversal depth. Default 8.",
    )
    thread_command.add_argument(
        "--nodes",
        type=int,
        default=50,
        help="Maximum explicit nodes returned. Default 50.",
    )
    thread_command.add_argument(
        "--window", type=int, default=7, help="Derived date window in days. Default 7."
    )
    thread_command.add_argument(
        "--limit", type=int, default=20, help="Maximum derived neighbors. Default 20."
    )
    thread_command.add_argument(
        "--stale-after",
        type=int,
        default=None,
        help="Staleness threshold in days. Default 14.",
    )
    historical_mode = thread_command.add_mutually_exclusive_group()
    historical_mode.add_argument(
        "--revision",
        metavar="REV",
        help="Read tracked inputs from one exact Git commit-ish.",
    )
    historical_mode.add_argument(
        "--diff",
        metavar="REV_A..REV_B",
        help="Compare the target's temporal thread between two exact Git revisions.",
    )
    historical_mode.add_argument(
        "--as-of",
        metavar="RFC3339",
        help="Select the newest reachable commit at or before an offset-aware timestamp.",
    )
    thread_command.add_argument(
        "--ref",
        metavar="REF",
        help="Git history root for --as-of. Defaults to HEAD.",
    )
    thread_command.add_argument(
        "--metrics",
        action="store_true",
        help="Summarize bounded explicit graph metrics.",
    )
    thread_command.add_argument(
        "--replacement-analysis",
        action="store_true",
        help="Summarize bounded replacement relations.",
    )
    thread_command.add_argument(
        "--consistency-summary",
        action="store_true",
        help="Summarize existing consistency warnings.",
    )
    thread_command.add_argument(
        "--realization-analysis",
        action="store_true",
        help="Compare realizes plan and actual temporal evidence.",
    )
    thread_command.add_argument("--json", action="store_true", help="Emit JSON.")
    thread_command.set_defaults(func=command_thread)

    freebusy_command = subparsers.add_parser(
        "freebusy",
        help="Show busy/free time intervals and overlap conflicts for "
        "E/R items with from:/to:/at:/on: within a datetime range.",
    )
    _add_input_paths(freebusy_command)
    freebusy_command.add_argument(
        "--from",
        dest="start",
        help="Range start: now, YYYY-MM-DD, or ISO-like datetime with optional seconds, fraction, and timezone.",
    )
    freebusy_command.add_argument(
        "--to",
        dest="end",
        help="Range end: now, YYYY-MM-DD, or ISO-like datetime with optional seconds, fraction, and timezone.",
    )
    freebusy_command.add_argument(
        "--around",
        help="Center of a range: now, YYYY-MM-DD, or ISO-like datetime. Defaults to now.",
    )
    freebusy_command.add_argument(
        "--window",
        default="1h",
        help="Half-width for --around, e.g. 30m, 2h, 1d, 1w, 1mo, or 1y.",
    )
    freebusy_command.add_argument(
        "--day-start",
        metavar="HH:MM",
        help="Restrict reported free intervals to this daily start time. "
        "Requires --day-end.",
    )
    freebusy_command.add_argument(
        "--day-end",
        metavar="HH:MM",
        help="Restrict reported free intervals to this daily end time. "
        "Requires --day-start.",
    )
    freebusy_command.add_argument("--json", action="store_true", help="Emit JSON.")
    freebusy_command.set_defaults(func=command_freebusy)

    vm_command = subparsers.add_parser(
        "vm",
        help="Opt-in, isolated lifetxt VM: run a Turing-complete 2-counter "
        "machine encoded in valid life.txt records. Never runs from any "
        "other command.",
    )
    vm_subparsers = vm_command.add_subparsers(dest="vm_command")
    vm_run_command = vm_subparsers.add_parser(
        "run",
        help="Execute a lifetxt VM program from an explicit entry instruction.",
    )
    _add_input_paths(vm_run_command)
    vm_run_command.add_argument(
        "--entry",
        required=True,
        metavar="ID",
        help="id: of the instruction to start execution at.",
    )
    vm_run_command.add_argument(
        "--max-steps",
        type=int,
        default=VM_DEFAULT_MAX_STEPS,
        metavar="N",
        help="Maximum instructions to execute before failing loudly instead "
        "of looping forever. 0 means unlimited execution (explicit "
        "opt-in). Default %d." % VM_DEFAULT_MAX_STEPS,
    )
    vm_run_command.add_argument("--json", action="store_true", help="Emit JSON.")
    vm_run_command.set_defaults(func=command_vm_run)

    vm_graph_command = vm_subparsers.add_parser(
        "graph",
        help="Render a lifetxt VM program's counters and instructions as a "
        "directed control-flow graph (mermaid or dot). Static only; never "
        "executes the program.",
    )
    _add_input_paths(vm_graph_command)
    vm_graph_command.add_argument(
        "--entry",
        metavar="ID",
        default=None,
        help="Optional id: of an instruction to highlight as the entry point.",
    )
    vm_graph_command.add_argument(
        "--format",
        choices=("mermaid", "dot"),
        default="mermaid",
        help="Output format. Defaults to mermaid.",
    )
    vm_graph_command.set_defaults(func=command_vm_graph)

    backup_command = subparsers.add_parser(
        "backup",
        help="Disaster-recovery backup snapshots (lifetxt-backup-v1): "
        "create/status/verify/restore/prune, distinct from the periodic "
        "local Git-commit worker.",
    )
    backup_subparsers = backup_command.add_subparsers(dest="backup_command")

    backup_create_command = backup_subparsers.add_parser(
        "create", help="Create one backup snapshot now."
    )
    backup_create_command.add_argument(
        "sources", nargs="*", help="Source paths to back up (or backup.sources)."
    )
    backup_create_command.add_argument("--destination", help="Backup directory.")
    backup_create_command.add_argument("--json", action="store_true")
    backup_create_command.set_defaults(func=command_backup_create)

    backup_status_command = backup_subparsers.add_parser(
        "status", help="Report local/remote backup attempt and result history."
    )
    backup_status_command.add_argument("--destination", help="Backup directory.")
    backup_status_command.add_argument("--json", action="store_true")
    backup_status_command.set_defaults(func=command_backup_status)

    backup_verify_command = backup_subparsers.add_parser(
        "verify", help="Verify one backup archive's format and integrity."
    )
    backup_verify_command.add_argument(
        "path", nargs="?", help="Path to a .ltbackup file."
    )
    backup_verify_command.add_argument(
        "--latest",
        action="store_true",
        help="Verify the newest complete backup in --destination/config.",
    )
    backup_verify_command.add_argument("--destination", help="Backup directory.")
    backup_verify_command.add_argument("--json", action="store_true")
    backup_verify_command.set_defaults(func=command_backup_verify)

    backup_restore_command = backup_subparsers.add_parser(
        "restore", help="Restore a backup archive's files to a destination directory."
    )
    backup_restore_command.add_argument("path", help="Path to a .ltbackup file.")
    backup_restore_command.add_argument(
        "destination_dir", help="Directory to restore files into."
    )
    backup_restore_command.add_argument(
        "--overwrite", action="store_true", help="Allow overwriting existing files."
    )
    backup_restore_command.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    backup_restore_command.add_argument("--json", action="store_true")
    backup_restore_command.set_defaults(func=command_backup_restore)

    backup_prune_command = backup_subparsers.add_parser(
        "prune", help="Delete older backups beyond a retention count."
    )
    backup_prune_command.add_argument("--destination", help="Backup directory.")
    backup_prune_command.add_argument(
        "--keep-last", type=int, required=True, metavar="N"
    )
    backup_prune_command.add_argument(
        "--dry-run", action="store_true", help="Preview without deleting."
    )
    backup_prune_command.add_argument("--json", action="store_true")
    backup_prune_command.set_defaults(func=command_backup_prune)

    backup_run_scheduled_command = backup_subparsers.add_parser(
        "run-scheduled",
        help="Run the unattended backup flow (create, optional remote "
        "upload, optional prune) guarded by backup.enabled.",
    )
    backup_run_scheduled_command.add_argument("--json", action="store_true")
    backup_run_scheduled_command.set_defaults(func=command_backup_run_scheduled)

    item_uri_command = subparsers.add_parser(
        "item-uri",
        help="Format/parse the host-independent lifetxt://item/<id> "
        "logical record link (#840). Pure identity translation only: "
        "never touches a life.txt file, never checks whether the id "
        "exists, and never bypasses workspace/authorization boundaries.",
    )
    item_uri_subparsers = item_uri_command.add_subparsers(dest="item_uri_command")
    item_uri_format_command = item_uri_subparsers.add_parser(
        "format",
        help="Build the lifetxt://item/<id> URI (and, with --base-url, "
        "the equivalent #838 Web deep link) for a canonical id.",
    )
    item_uri_format_command.add_argument("id", help="Canonical item id.")
    item_uri_format_command.add_argument(
        "--base-url",
        default="",
        help="Deployment origin (e.g. https://lifetxt.example.invalid) to "
        "also print the #838 Web deep-link form. Omit for a root-relative "
        "link.",
    )
    item_uri_format_command.add_argument(
        "--json", action="store_true", help="Emit JSON."
    )
    item_uri_format_command.set_defaults(func=command_item_uri_format)

    item_uri_parse_command = item_uri_subparsers.add_parser(
        "parse",
        help="Decode a lifetxt://item/<id> URI back to its canonical id, "
        "rejecting anything malformed.",
    )
    item_uri_parse_command.add_argument("uri", help="lifetxt://item/<id> URI.")
    item_uri_parse_command.add_argument(
        "--json", action="store_true", help="Emit JSON."
    )
    item_uri_parse_command.set_defaults(func=command_item_uri_parse)

    query_command = subparsers.add_parser(
        "query", help="Filter items with the shared query language."
    )
    query_command.add_argument(
        "query", help="Query string, e.g. 'open project:web due<2026-08-01'."
    )
    _add_input_paths(query_command)
    query_command.add_argument(
        "--sort", help="Sort key (line, due, status, title, ...)."
    )
    query_command.add_argument(
        "--order", default="asc", choices=["asc", "desc"], help="Sort order."
    )
    query_command.add_argument("--limit", type=int, help="Maximum items to return.")
    query_command.add_argument(
        "--format",
        default="life",
        choices=["life", "json", "jsonl", "table"],
        help="Output format.",
    )
    query_command.add_argument(
        "--explain",
        action="store_true",
        help="Show how the query is interpreted instead of matching items.",
    )
    query_command.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON."
    )
    query_command.add_argument(
        "--canonical", action="store_true", help="Canonical life.txt output."
    )
    query_command.add_argument("--width", type=int, default=0, help="Table width.")
    query_command.add_argument(
        "-o", "--output", help="Write to a file instead of stdout."
    )
    query_command.add_argument(
        "--revision",
        help="Evaluate the query against the tracked bytes at this exact Git "
        "revision instead of the current working tree (#726/#730). Never "
        "falls back to current state.",
    )
    query_command.add_argument(
        "--as-of",
        dest="as_of",
        help="Evaluate the query against the newest commit at or before this "
        "offset-aware RFC3339 timestamp, reusing the shared committer-time "
        "selector (#760). Mutually exclusive with --revision.",
    )
    query_command.add_argument(
        "--ref",
        help="Branch/ref to select --as-of history from (default HEAD). "
        "Only valid together with --as-of.",
    )
    query_command.set_defaults(func=command_query)

    view_command = subparsers.add_parser(
        "view", help="List, inspect, and run saved views (named queries)."
    )
    view_subparsers = view_command.add_subparsers(dest="view_command")
    view_list = view_subparsers.add_parser("list", help="List saved views.")
    view_list.add_argument("--json", action="store_true", help="Emit JSON.")
    view_list.set_defaults(func=command_view_list)
    view_show = view_subparsers.add_parser(
        "show", help="Show one saved view definition."
    )
    view_show.add_argument("name", help="Saved view name.")
    view_show.add_argument("--json", action="store_true", help="Emit JSON.")
    view_show.set_defaults(func=command_view_show)
    view_validate = view_subparsers.add_parser(
        "validate", help="Validate saved view queries."
    )
    view_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    view_validate.set_defaults(func=command_view_validate)
    view_run = view_subparsers.add_parser("run", help="Run a saved view.")
    view_run.add_argument("name", help="Saved view name.")
    _add_input_paths(view_run)
    view_run.add_argument(
        "--format",
        default="life",
        choices=["life", "json", "jsonl", "table"],
        help="Output format.",
    )
    view_run.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    view_run.add_argument(
        "--canonical", action="store_true", help="Canonical life.txt output."
    )
    view_run.add_argument("--width", type=int, default=0, help="Table width.")
    view_run.add_argument("-o", "--output", help="Write to a file instead of stdout.")
    view_run.set_defaults(func=command_view_run)

    group_command = subparsers.add_parser(
        "group", help="Inspect and validate messaging groups."
    )
    group_subparsers = group_command.add_subparsers(dest="group_command")
    group_list = group_subparsers.add_parser(
        "list", help="List groups with member counts."
    )
    group_list.add_argument("--json", action="store_true", help="Emit JSON.")
    group_list.set_defaults(func=command_group_list)
    group_show = group_subparsers.add_parser(
        "show", help="Show one group's resolved members."
    )
    group_show.add_argument("name", help="Group name.")
    group_show.add_argument("--json", action="store_true", help="Emit JSON.")
    group_show.set_defaults(func=command_group_show)
    group_validate = group_subparsers.add_parser(
        "validate", help="Validate all groups."
    )
    group_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    group_validate.set_defaults(func=command_group_validate)

    message_command = subparsers.add_parser(
        "message", help="Compose messages and inspect recipients and delivery state."
    )
    message_subparsers = message_command.add_subparsers(dest="message_command")

    msg_recipients = message_subparsers.add_parser(
        "recipients", help="Preview the resolved recipient set for references."
    )
    msg_recipients.add_argument("to", help="Comma-separated people/teams/groups.")
    msg_recipients.add_argument("--json", action="store_true", help="Emit JSON.")
    msg_recipients.set_defaults(func=command_message_recipients)

    msg_send = message_subparsers.add_parser(
        "send", help="Append a message item with resolved recipients."
    )
    msg_send.add_argument("title", help="Message title.")
    msg_send.add_argument(
        "--sender", help="Sender person. Defaults to the config user."
    )
    msg_send.add_argument(
        "--to", required=True, help="Comma-separated people/teams/groups."
    )
    msg_send.add_argument(
        "--ack-policy",
        default="any",
        help="Acknowledgement policy: any, all, or a count.",
    )
    msg_send.add_argument("--body", help="Message body.")
    msg_send.add_argument(
        "--output", help="File to append to. Defaults to the write target."
    )
    msg_send.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    msg_send.set_defaults(func=command_message_send)

    msg_status = message_subparsers.add_parser(
        "status", help="Show per-recipient delivery state."
    )
    msg_status.add_argument("--id", help="Restrict to one message ID.")
    _add_input_paths(msg_status)
    msg_status.add_argument("--policy", help="Override the acknowledgement policy.")
    msg_status.add_argument("--json", action="store_true", help="Emit JSON.")
    msg_status.set_defaults(func=command_message_status)

    person_command = subparsers.add_parser(
        "person",
        help="Overview of a person's work, messages, meetings, and memberships.",
    )
    person_subparsers = person_command.add_subparsers(dest="person_command")
    person_list = person_subparsers.add_parser("list", help="List people with counts.")
    _add_input_paths(person_list)
    person_list.add_argument("--json", action="store_true", help="Emit JSON.")
    person_list.set_defaults(func=command_person_list)
    person_show = person_subparsers.add_parser(
        "show", help="Show one person's overview."
    )
    person_show.add_argument("name", help="Person name or alias.")
    _add_input_paths(person_show)
    person_show.add_argument("--json", action="store_true", help="Emit JSON.")
    person_show.set_defaults(func=command_person_show)
    person_group = person_subparsers.add_parser(
        "group", help="Overview of a group's members."
    )
    person_group.add_argument("name", help="Group name.")
    _add_input_paths(person_group)
    person_group.add_argument("--json", action="store_true", help="Emit JSON.")
    person_group.set_defaults(func=command_person_group)

    proposal_command = subparsers.add_parser(
        "proposal",
        help="Unified Inbox: review, edit, accept, or reject staged proposals.",
    )
    proposal_subparsers = proposal_command.add_subparsers(dest="proposal_command")

    prop_list = proposal_subparsers.add_parser("list", help="List staged proposals.")
    prop_list.add_argument(
        "--status",
        choices=["pending", "accepted", "rejected", "deferred"],
        help="Filter by status.",
    )
    prop_list.add_argument("--json", action="store_true", help="Emit JSON.")
    prop_list.set_defaults(func=command_proposal_list)

    prop_add = proposal_subparsers.add_parser("add", help="Stage a create proposal.")
    prop_add.add_argument("title", help="Item title.")
    prop_add.add_argument("--kind", default="T", help="Item type. Default T.")
    prop_add.add_argument("--project", help="project: value.")
    prop_add.add_argument("--due", help="due: value.")
    prop_add.add_argument("--assignee", help="assignee: value.")
    prop_add.add_argument("--priority", help="priority: value.")
    prop_add.add_argument("--tag", action="append", help="tag: value (repeatable).")
    prop_add.add_argument(
        "--source", default="manual", help="Proposal source. Default manual."
    )
    prop_add.set_defaults(func=command_proposal_add)

    prop_show = proposal_subparsers.add_parser("show", help="Show one proposal.")
    prop_show.add_argument("id", help="Proposal ID.")
    prop_show.set_defaults(func=command_proposal_show)

    prop_edit = proposal_subparsers.add_parser("edit", help="Edit a pending proposal.")
    prop_edit.add_argument("id", help="Proposal ID.")
    prop_edit.add_argument("--title", help="New title.")
    prop_edit.add_argument("--kind", help="New type.")
    prop_edit.add_argument("--project", help="project: value.")
    prop_edit.add_argument("--due", help="due: value.")
    prop_edit.add_argument("--assignee", help="assignee: value.")
    prop_edit.add_argument("--priority", help="priority: value.")
    prop_edit.set_defaults(func=command_proposal_edit)

    prop_accept = proposal_subparsers.add_parser(
        "accept", help="Accept and append a proposal."
    )
    prop_accept.add_argument("ids", nargs="+", help="Proposal ID(s).")
    prop_accept.add_argument("--to", help="Target file. Defaults to the write target.")
    prop_accept.set_defaults(func=command_proposal_accept)

    prop_reject = proposal_subparsers.add_parser("reject", help="Reject a proposal.")
    prop_reject.add_argument("id", help="Proposal ID.")
    prop_reject.set_defaults(func=command_proposal_reject)

    prop_defer = proposal_subparsers.add_parser("defer", help="Defer a proposal.")
    prop_defer.add_argument("id", help="Proposal ID.")
    prop_defer.set_defaults(func=command_proposal_defer)

    find_command = subparsers.add_parser(
        "find",
        help="Global search across items, projects, people, groups, areas, and proposals.",
    )
    find_command.add_argument("term", help="Case-insensitive search term.")
    _add_input_paths(find_command)
    find_command.add_argument(
        "--type",
        dest="types",
        action="append",
        help="Limit to an entity type (item, project, person, group, area, proposal). Repeatable.",
    )
    find_command.add_argument(
        "--limit", type=int, help="Maximum results per entity type."
    )
    find_command.add_argument(
        "--fuzzy",
        action="store_true",
        help="Also match a small typo/edit distance of term, not only an exact "
        "substring. Exact matches are always ranked ahead of approximate ones.",
    )
    find_command.add_argument("--json", action="store_true", help="Emit JSON.")
    find_command.set_defaults(func=command_find)

    ticket_command = subparsers.add_parser(
        "ticket",
        help="Development tickets (record:ticket): new, list, show, edit, transitions, links.",
    )
    ticket_subparsers = ticket_command.add_subparsers(dest="ticket_command")

    tk_new = ticket_subparsers.add_parser("new", help="Create a ticket.")
    tk_new.add_argument("subject", help="Ticket subject.")
    tk_new.add_argument("--tracker", help="Tracker (bug, feature, task, support).")
    tk_new.add_argument("--priority", help="Priority.")
    tk_new.add_argument("--severity", help="Severity.")
    tk_new.add_argument("--assignee", help="Assignee.")
    tk_new.add_argument("--reporter", help="Reporter.")
    tk_new.add_argument("--component", help="Component.")
    tk_new.add_argument("--version", help="Target version.")
    tk_new.add_argument("--sprint", help="Sprint.")
    tk_new.add_argument("--project", help="Project.")
    tk_new.add_argument("--due", help="Due date.")
    tk_new.add_argument("--est", help="Estimate.")
    tk_new.add_argument(
        "--status", default="new", help="Initial ticket_status. Default new."
    )
    tk_new.add_argument("--watcher", action="append", help="Watcher (repeatable).")
    tk_new.add_argument(
        "--id", help="Explicit ticket id. Defaults to the next generated id."
    )
    tk_new.add_argument("--to", help="Target file. Defaults to the write target.")
    tk_new.add_argument(
        "--dry-run", action="store_true", help="Print the line without writing."
    )
    _add_input_paths(tk_new)
    tk_new.set_defaults(func=command_ticket_new)

    tk_list = ticket_subparsers.add_parser("list", help="List tickets.")
    _add_input_paths(tk_list)
    for flag in (
        "tracker",
        "status",
        "priority",
        "severity",
        "assignee",
        "component",
        "version",
        "sprint",
        "project",
    ):
        tk_list.add_argument("--%s" % flag, help="Filter by %s." % flag)
    tk_list.add_argument(
        "--open", dest="open_only", action="store_true", help="Only open tickets."
    )
    tk_list.add_argument("--json", action="store_true", help="Emit JSON.")
    tk_list.set_defaults(func=command_ticket_list)

    tk_show = ticket_subparsers.add_parser(
        "show", help="Show one ticket with relations."
    )
    tk_show.add_argument("id", help="Ticket id.")
    _add_input_paths(tk_show)
    tk_show.add_argument("--json", action="store_true", help="Emit JSON.")
    tk_show.set_defaults(func=command_ticket_show)

    tk_edit = ticket_subparsers.add_parser("edit", help="Set or unset ticket fields.")
    tk_edit.add_argument("id", help="Ticket id.")
    tk_edit.add_argument(
        "--set",
        dest="set_fields",
        action="append",
        metavar="KEY=VALUE",
        help="Set a field (repeatable).",
    )
    tk_edit.add_argument(
        "--unset", action="append", metavar="KEY", help="Remove a field (repeatable)."
    )
    _add_input_paths(tk_edit)
    tk_edit.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    tk_edit.set_defaults(func=command_ticket_edit)

    tk_assign = ticket_subparsers.add_parser("assign", help="Assign a ticket.")
    tk_assign.add_argument("id", help="Ticket id.")
    tk_assign.add_argument("assignee", help="Assignee person.")
    _add_input_paths(tk_assign)
    tk_assign.set_defaults(func=command_ticket_assign)

    tk_close = ticket_subparsers.add_parser("close", help="Close/resolve a ticket.")
    tk_close.add_argument("id", help="Ticket id.")
    tk_close.add_argument(
        "--status",
        default="closed",
        help="Terminal status: closed, resolved, rejected, duplicate, wont_fix.",
    )
    tk_close.add_argument("--resolution", help="Resolution note.")
    tk_close.add_argument(
        "--by", help="Actor recorded as closed_by. Defaults to config user."
    )
    _add_input_paths(tk_close)
    tk_close.set_defaults(func=command_ticket_close)

    tk_reopen = ticket_subparsers.add_parser("reopen", help="Reopen a ticket.")
    tk_reopen.add_argument("id", help="Ticket id.")
    tk_reopen.add_argument(
        "--status", default="new", help="Reopen status. Default new."
    )
    _add_input_paths(tk_reopen)
    tk_reopen.set_defaults(func=command_ticket_reopen)

    tk_link = ticket_subparsers.add_parser("link", help="Add a relation to a ticket.")
    tk_link.add_argument("id", help="Ticket id.")
    tk_link.add_argument(
        "relation",
        choices=[
            "parent",
            "depends_on",
            "blocks",
            "related",
            "duplicate_of",
            "replaced_by",
            "follows",
            "realizes",
        ],
    )
    tk_link.add_argument("target", help="Target id.")
    _add_input_paths(tk_link)
    tk_link.set_defaults(func=command_ticket_link)

    tk_unlink = ticket_subparsers.add_parser(
        "unlink", help="Remove a relation from a ticket."
    )
    tk_unlink.add_argument("id", help="Ticket id.")
    tk_unlink.add_argument(
        "relation",
        choices=[
            "parent",
            "depends_on",
            "blocks",
            "related",
            "duplicate_of",
            "replaced_by",
            "follows",
            "realizes",
        ],
    )
    tk_unlink.add_argument("target", help="Target id to remove.")
    _add_input_paths(tk_unlink)
    tk_unlink.set_defaults(func=command_ticket_unlink)

    tk_validate = ticket_subparsers.add_parser("validate", help="Validate all tickets.")
    _add_input_paths(tk_validate)
    tk_validate.add_argument("--json", action="store_true", help="Emit JSON.")
    tk_validate.set_defaults(func=command_ticket_validate)

    tui = subparsers.add_parser(
        "tui",
        help="Run a terminal dashboard for tasks, agenda, and status.",
    )
    tui.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to read. Defaults to config paths or life.txt.",
    )
    tui.add_argument(
        "--theme",
        choices=("auto", "dark", "light", "mono"),
        help="TUI color theme. Defaults to config tui.theme or auto.",
    )
    tui.add_argument(
        "--keymap",
        choices=("prompt", "vim", "arrows"),
        help="TUI keymap preset. prompt keeps the input bar focused; vim uses single-key navigation. Defaults to config tui.keymap or prompt.",
    )
    tui.add_argument(
        "--glyphs",
        choices=("auto", "unicode", "ascii"),
        help="Box-drawing character set. Defaults to config tui.glyphs or auto.",
    )
    tui.add_argument(
        "--plain",
        action="store_true",
        help="Print one plain-text dashboard snapshot instead of running the interactive workspace.",
    )
    tui.add_argument(
        "--limit",
        type=int,
        help="Maximum rows per TUI section. Defaults to config tui.limit or 10.",
    )
    tui.add_argument(
        "--agenda-window",
        help="Agenda window around now, such as 6h, 12h, 1d. Defaults to config tui.agenda_window or 12h.",
    )
    tui.add_argument(
        "--remote-url",
        dest="remote_url",
        help="Run the interactive TUI against a remote `lifetxt serve` "
        "workspace over HTTP(S) instead of local files (#677). Example: "
        "https://example.internal or http://127.0.0.1:8765.",
    )
    tui.add_argument(
        "--remote-user",
        dest="remote_user",
        help="HTTP Basic Auth username for --remote-url (for example, an "
        "Apache reverse-proxy login). The password is never a literal "
        "argument; see --remote-password-env.",
    )
    tui.add_argument(
        "--remote-password-env",
        dest="remote_password_env",
        help="Environment variable holding the --remote-user password. "
        "Defaults to LIFETXT_REMOTE_TUI_PASSWORD.",
    )
    tui.add_argument(
        "--allow-insecure-remote-http",
        dest="allow_insecure_remote_http",
        action="store_true",
        help="Permit plain HTTP to a non-loopback --remote-url host. Only "
        "appropriate when the connection is already secured by another "
        "layer, such as a WireGuard tunnel; HTTPS remains the safer "
        "general default.",
    )
    tui.add_argument(
        "--remote-cache",
        dest="remote_cache",
        action="store_true",
        help="Opt in to a read-only offline cache (#681) for --remote-url: "
        "after a successful read, persist a bounded last-known snapshot "
        "under ~/.cache/lifetxt/remote-tui/ so a disconnected session can "
        "show stale-but-labeled data instead of only a connection error. "
        "Off by default; never caches credentials. Mutation commands are "
        "refused while showing cached data.",
    )
    tui.add_argument(
        "--remote-clear-cache",
        dest="remote_clear_cache",
        action="store_true",
        help="Delete the offline cache for --remote-url (and --remote-user, "
        "if given), then exit without starting the TUI.",
    )
    tui.set_defaults(func=command_tui)

    fzf = subparsers.add_parser(
        "fzf",
        help="Select filtered items with fzf or peco and run an action.",
    )
    _add_input_paths(fzf)
    _add_item_filter_arguments(fzf)
    fzf.add_argument(
        "--action",
        choices=("done", "edit", "delete", "show"),
        help="Action to run on selected items. Defaults to an interactive prompt.",
    )
    fzf.add_argument(
        "--tool",
        choices=("fzf", "peco"),
        help="Selection tool. Defaults to fzf or peco from PATH.",
    )
    fzf.add_argument(
        "--preview",
        dest="preview",
        action="store_true",
        default=True,
        help="Enable fzf preview. This is the default.",
    )
    fzf.add_argument(
        "--no-preview",
        dest="preview",
        action="store_false",
        help="Disable fzf preview.",
    )
    fzf.add_argument(
        "--print-query",
        action="store_true",
        help="Print only the fzf query string.",
    )
    fzf.set_defaults(func=command_fzf)

    timer = subparsers.add_parser(
        "timer",
        help="Start, stop, inspect, or summarize a single task timer.",
    )
    timer_subparsers = timer.add_subparsers(dest="timer_command")
    timer_start = timer_subparsers.add_parser(
        "start", help="Start a timer for an item ID."
    )
    timer_start.add_argument("path", help="life.txt file containing the item.")
    timer_start.add_argument(
        "--id", dest="item_id", required=True, help="Item ID to time."
    )
    timer_start.add_argument("--note", help="Optional note stored in timer state.")
    timer_start.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    timer_start.add_argument(
        "--timer-revision",
        help="Expected timer-state revision; use <missing> when idle.",
    )
    timer_start.set_defaults(func=command_timer)
    timer_pause = timer_subparsers.add_parser("pause", help="Pause the running timer.")
    timer_pause.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_pause.set_defaults(func=command_timer)
    timer_resume = timer_subparsers.add_parser("resume", help="Resume a paused timer.")
    timer_resume.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_resume.set_defaults(func=command_timer)
    timer_stop = timer_subparsers.add_parser("stop", help="Stop the running timer.")
    timer_stop.add_argument(
        "path",
        nargs="?",
        help="life.txt file. Defaults to the file stored in timer state.",
    )
    timer_stop.add_argument("--id", dest="item_id", help="Expected running item ID.")
    timer_stop.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    timer_stop.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_stop.set_defaults(func=command_timer)
    timer_status = timer_subparsers.add_parser("status", help="Show the running timer.")
    timer_status.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="Optional life.txt files used to resolve the title.",
    )
    timer_status.set_defaults(func=command_timer)
    timer_summary = timer_subparsers.add_parser(
        "summary", help="Summarize elapsed: details."
    )
    timer_summary.add_argument(
        "paths", nargs="+", metavar="path", help="life.txt file(s) to summarize."
    )
    timer_summary.add_argument("--from", dest="start", help="Start date or datetime.")
    timer_summary.add_argument("--to", dest="end", help="End date or datetime.")
    timer_summary.add_argument("--project", help="Filter by project.")
    timer_summary.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    timer_summary.set_defaults(func=command_timer)
    timer_cancel = timer_subparsers.add_parser(
        "cancel", help="Cancel the running timer without updating an item."
    )
    timer_cancel.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    timer_cancel.set_defaults(func=command_timer)

    stats = subparsers.add_parser(
        "stats",
        help="Show task, habit, mood, project, and progress-delta statistics.",
    )
    _add_input_paths(stats)
    stats.add_argument(
        "--from", dest="start", help="Start date. Defaults to 29 days before --to."
    )
    stats.add_argument("--to", dest="end", help="End date. Defaults to today.")
    stats.add_argument(
        "--progress-delta",
        metavar="ID",
        help="Show authoritative progress change between --from/--to boundaries.",
    )
    _add_item_filter_arguments(stats)
    stats.add_argument(
        "--group",
        choices=("daily", "weekly", "monthly"),
        default="daily",
        help="Aggregation bucket size.",
    )
    stats.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    stats.add_argument(
        "--width", type=int, help="Render text output for a specific terminal width."
    )
    stats.set_defaults(func=command_stats)

    lifecycle_stats = subparsers.add_parser(
        "lifecycle-stats",
        help="Summarize bounded Native lifecycle analytics across workspace items.",
    )
    _add_input_paths(lifecycle_stats)
    lifecycle_stats.add_argument("--since")
    lifecycle_stats.add_argument("--until")
    lifecycle_stats.add_argument("--duration", action="store_true")
    lifecycle_stats.add_argument("--coverage", action="store_true")
    lifecycle_stats.add_argument("--limit", type=int, default=500)
    lifecycle_stats.add_argument("--json", action="store_true")
    lifecycle_stats.set_defaults(func=command_lifecycle_stats)

    git_hook = subparsers.add_parser(
        "git-hook",
        help="Install, uninstall, or inspect lifetxt Git hooks.",
    )
    git_hook_subparsers = git_hook.add_subparsers(dest="git_hook_command")
    git_hook_install = git_hook_subparsers.add_parser(
        "install", help="Install Git hooks."
    )
    git_hook_install.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository root. Defaults to current directory.",
    )
    git_hook_install.add_argument(
        "--files", nargs="*", help="life.txt files checked by hooks."
    )
    git_hook_install.add_argument(
        "--no-commit-msg", action="store_true", help="Do not install commit-msg hook."
    )
    git_hook_install.add_argument(
        "--force", action="store_true", help="Overwrite non-lifetxt hooks."
    )
    git_hook_install.set_defaults(func=command_git_hook)
    git_hook_uninstall = git_hook_subparsers.add_parser(
        "uninstall", help="Uninstall lifetxt Git hooks."
    )
    git_hook_uninstall.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository root. Defaults to current directory.",
    )
    git_hook_uninstall.set_defaults(func=command_git_hook)
    git_hook_status = git_hook_subparsers.add_parser(
        "status", help="Show Git hook installation status."
    )
    git_hook_status.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository root. Defaults to current directory.",
    )
    git_hook_status.add_argument(
        "--files", nargs="*", help="life.txt files checked by hooks."
    )
    git_hook_status.set_defaults(func=command_git_hook)

    from .completion import add_completion_parsers

    add_completion_parsers(subparsers, command_completion)

    filter_command = subparsers.add_parser(
        "filter",
        aliases=["f"],
        help="Filter life.txt items and output life.txt, JSON, or JSONL.",
    )
    _add_input_paths(filter_command)
    _add_item_filter_arguments(filter_command)
    filter_command.add_argument(
        "--format",
        choices=("life", "json", "jsonl", "table"),
        default="life",
        help="Output format. Defaults to life.",
    )
    filter_command.add_argument(
        "--width",
        type=int,
        default=0,
        metavar="N",
        help="Table column width in characters (0 = detect terminal width). Only used with --format table.",
    )
    filter_command.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    filter_command.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    filter_command.add_argument(
        "--canonical",
        action="store_true",
        help="Regenerate unindented life.txt lines with explicit parent: links where inferable.",
    )
    filter_command.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Return at most N items (0 = no limit).",
    )
    filter_command.set_defaults(func=command_filter)

    status = subparsers.add_parser(
        "status",
        help="Show the latest status / presence item for each person.",
    )
    _add_input_paths(status)
    status.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    status.add_argument(
        "--person",
        help="Only show the latest status for this person. Missing person: defaults to self.",
    )
    status.add_argument(
        "--active",
        action="store_true",
        help="Only consider active status items without to:.",
    )
    status.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    status.set_defaults(func=command_status)

    notify = subparsers.add_parser(
        "notify",
        help="Show or watch due message notifications.",
    )
    _add_input_paths(notify)
    notify.add_argument(
        "--recipient",
        help="Notification recipient. Defaults to notifications.recipient or user.name.",
    )
    notify.add_argument(
        "--lookahead",
        help="Future notification window, e.g. 0m, 5m, or 1h.",
    )
    notify.add_argument(
        "--grace",
        help="Past grace window for missed notifications, e.g. 2m.",
    )
    notify.add_argument(
        "--watch",
        action="store_true",
        help="Stay running and poll for notifications.",
    )
    notify.add_argument(
        "--once",
        action="store_true",
        help="With --watch, poll once, emit new notifications, update seen-state, and exit.",
    )
    notify.add_argument(
        "--interval",
        type=int,
        help="Watch poll interval in seconds.",
    )
    notify.add_argument(
        "--desktop",
        action="store_true",
        help="Also show a simple desktop notification when supported.",
    )
    notify.add_argument(
        "--email",
        action="store_true",
        help="Also send due notifications as a plain-text email batch.",
    )
    notify.add_argument(
        "--email-to",
        help="Recipient email address(es), comma-separated. Defaults to notifications.email.to.",
    )
    notify.add_argument(
        "--email-subject",
        help="Base subject for notification email. Defaults to notifications.email.subject.",
    )
    notify.add_argument(
        "--smtp-host-env",
        metavar="ENVVAR",
        help="Environment variable with the SMTP host for --email.",
    )
    notify.add_argument(
        "--smtp-user-env",
        metavar="ENVVAR",
        help="Environment variable with the SMTP username for --email.",
    )
    notify.add_argument(
        "--smtp-pass-env",
        metavar="ENVVAR",
        help="Environment variable with the SMTP password for --email.",
    )
    notify.add_argument(
        "--smtp-port",
        type=int,
        metavar="PORT",
        help=(
            "Explicit SMTP port for --email, e.g. 587 for STARTTLS submission. "
            "Defaults to notifications.email.smtp_port, or the existing default port."
        ),
    )
    notify.add_argument(
        "--dry-run",
        action="store_true",
        help="For --email, print the email that would be sent without using SMTP.",
    )
    notify.add_argument(
        "--state-file",
        help="Persist seen notification IDs in this JSON file when watching.",
    )
    notify.add_argument(
        "--no-state",
        action="store_true",
        help="Do not persist seen notification IDs when watching.",
    )
    notify.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format for one-shot mode.",
    )
    notify.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    notify.set_defaults(func=command_notify)

    agenda = subparsers.add_parser(
        "agenda",
        aliases=["a"],
        help="Show items related to a datetime range.",
    )
    _add_input_paths(agenda)
    agenda.add_argument(
        "--from",
        dest="start",
        help="Range start: now, YYYY-MM-DD, or ISO-like datetime with optional seconds, fraction, and timezone.",
    )
    agenda.add_argument(
        "--to",
        dest="end",
        help="Range end: now, YYYY-MM-DD, or ISO-like datetime with optional seconds, fraction, and timezone.",
    )
    agenda.add_argument(
        "--around",
        help="Center of a range: now, YYYY-MM-DD, or ISO-like datetime. Defaults to now.",
    )
    agenda.add_argument(
        "--window",
        default="1h",
        help="Half-width for --around, e.g. 30m, 2h, 1d, 1w, 1mo, or 1y.",
    )
    agenda.add_argument(
        "--width",
        type=int,
        help="Render text output for a specific terminal width.",
    )
    agenda.add_argument(
        "--format",
        choices=("text", "life", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    agenda.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    _add_item_filter_arguments(agenda)
    agenda.add_argument(
        "--blocked",
        nargs="?",
        const="only",
        choices=("only", "hide", "all", "true", "false"),
        help=(
            "Filter dependency-blocked records: --blocked or --blocked only "
            "shows blocked records, --blocked hide hides them, --blocked all "
            "shows all records."
        ),
    )
    agenda.add_argument(
        "--unblocked",
        action="store_true",
        help="Backward-compatible alias for --blocked hide.",
    )
    agenda.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    agenda.set_defaults(func=command_agenda)

    from_json = subparsers.add_parser("from-json", help="Convert JSON to life.txt.")
    _add_input_paths(from_json)
    from_json.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_json.add_argument(
        "--canonical",
        action="store_true",
        help="Write explicit parent: links and remove indentation from output.",
    )
    from_json.set_defaults(func=command_from_json)

    from_jsonl = subparsers.add_parser("from-jsonl", help="Convert JSONL to life.txt.")
    _add_input_paths(from_jsonl)
    from_jsonl.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_jsonl.add_argument(
        "--canonical",
        action="store_true",
        help="Write explicit parent: links and remove indentation from output.",
    )
    from_jsonl.set_defaults(func=command_from_jsonl)

    from_csv = subparsers.add_parser("from-csv", help="Convert CSV to life.txt.")
    _add_input_paths(from_csv)
    from_csv.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    from_csv.add_argument(
        "--canonical",
        action="store_true",
        help="Write explicit parent: links and remove indentation from output.",
    )
    from_csv.set_defaults(func=command_from_csv)

    assist = subparsers.add_parser(
        "assist", help="Create a life.txt line interactively or from flags."
    )
    assist.add_argument(
        "-i", "--interactive", action="store_true", help="Prompt for fields."
    )
    assist.add_argument(
        "-s", "--status", help="Status or alias, e.g. '[ ]', done, note."
    )
    assist.add_argument(
        "-t",
        "--type",
        dest="kind",
        help="Type or alias, e.g. T, task, event, note, diary.",
    )
    assist.add_argument("--title", help="Item title.")
    assist.add_argument(
        "-d",
        "--detail",
        action="append",
        default=[],
        help="Detail as key=value or key:value. Can be repeated.",
    )
    assist.add_argument(
        "-o",
        "--output",
        help="Append generated line to a file. With --update, write the updated file.",
    )
    assist.add_argument("--append", help="Append the generated line to a file.")
    assist.add_argument(
        "--update",
        help="Update an existing life.txt file in-place, unless --output is also set.",
    )
    assist.add_argument("--line", type=int, help="Line number to update with --update.")
    assist.add_argument(
        "--match-id", help="Update the item whose id: contains this value."
    )
    assist.add_argument(
        "--add-detail",
        action="append",
        default=[],
        help="Append detail as key=value or key:value when updating. Can be repeated.",
    )
    assist.add_argument(
        "--remove-detail",
        action="append",
        default=[],
        help="Remove all values for a detail key when updating. Can be repeated.",
    )
    assist.add_argument(
        "--no-check",
        action="store_true",
        help="Do not validate the generated line before output.",
    )
    assist.add_argument(
        "--no-completion",
        action="store_true",
        help="Disable interactive completion and line editing helpers.",
    )
    assist.add_argument(
        "--body-file",
        action="append",
        help="Read a body: detail from a UTF-8 text file. Can be repeated.",
    )
    assist.add_argument(
        "--body-stdin",
        action="store_true",
        help="Read a body: detail from standard input.",
    )
    assist.add_argument(
        "--rrule",
        action="append",
        help="Set repeat:RRULE:...; accepts either FREQ=... or RRULE:FREQ=.... Can be repeated.",
    )
    for key in DETAIL_FLAGS:
        dest = "from_" if key == "from" else key
        option_strings = ["--" + key]
        if "_" in key:
            option_strings.append("--" + key.replace("_", "-"))
        assist.add_argument(
            *option_strings,
            dest=dest,
            action="append",
            help="Set %s: detail. Can be repeated." % key,
        )
    assist.set_defaults(func=command_assist)

    archive = subparsers.add_parser(
        "archive",
        help="Move or copy completed/canceled items to a separate archive file.",
    )
    archive.add_argument(
        "paths", nargs="+", metavar="path", help="Source life.txt file(s)."
    )
    archive.add_argument(
        "--dest", required=True, metavar="DEST", help="Archive file to append items to."
    )
    archive.add_argument(
        "--revision",
        action="append",
        default=[],
        metavar="PATH=SHA256",
        help="Expected revision for a source or destination path. Can be repeated.",
    )
    archive.add_argument(
        "--status",
        action="append",
        dest="statuses",
        metavar="STATUS",
        help=(
            "Only archive items with this status. Can be repeated or comma-separated. "
            "Defaults to done,canceled."
        ),
    )
    archive.add_argument(
        "--before",
        metavar="DATE",
        help="Only archive items whose done: or updated: date is before DATE (YYYY-MM-DD).",
    )
    archive.add_argument(
        "--max-items",
        type=int,
        dest="max_items",
        metavar="N",
        help="Maximum number of items to archive.",
    )
    archive.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show which items would be archived without writing any changes.",
    )
    archive.add_argument(
        "--copy",
        action="store_true",
        help="Copy items to the archive without removing them from the source file.",
    )
    archive.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    archive.add_argument(
        "--orphan-children",
        dest="orphan_children",
        choices=("block", "adopt", "promote"),
        default="block",
        help=(
            "How to handle open children of archived parents: "
            "block (default) refuses to archive, "
            "adopt archives open children together (marking them [-]), "
            "promote archives the parent only and removes parent: from orphaned children."
        ),
    )
    archive.add_argument(
        "--preserve-structure",
        action="store_true",
        dest="preserve_structure",
        help=(
            "Copy comment lines and blank lines verbatim to both the archive file "
            "and the source remainder so section headings remain intact."
        ),
    )
    archive.add_argument(
        "--block-on-external-refs",
        action="store_true",
        dest="block_on_external_refs",
        help=(
            "Treat cross-file or intra-file references to archived items as errors "
            "instead of warnings. Requires --dry-run or a live run to check."
        ),
    )
    archive.set_defaults(func=command_archive)

    quick = subparsers.add_parser(
        "quick",
        aliases=["q", "add"],
        help="Quickly capture a new item and append it to a file.",
    )
    quick.add_argument(
        "title",
        help=(
            "Item title. Use - to read a single line from stdin. Capture shorthand is "
            "expanded: @project #tag !priority ^due."
        ),
    )
    quick.add_argument(
        "--no-shorthand",
        action="store_true",
        help="Keep @ # ! ^ tokens in the title instead of expanding them into details.",
    )
    quick.add_argument(
        "--type",
        dest="kind",
        default=None,
        help="Item type. Defaults to T (task).",
    )
    quick.add_argument(
        "--append",
        metavar="FILE",
        help="File to append the new item to. Defaults to write_file in config.",
    )
    quick.add_argument(
        "--revision", help="Expected SHA-256 revision of the append target."
    )
    quick.add_argument(
        "--no-check",
        action="store_true",
        dest="no_check",
        help="Skip validation before writing.",
    )
    quick.add_argument("--status", default=None, help=argparse.SUPPRESS)
    quick.add_argument(
        "--preset",
        default=None,
        help=(
            "Apply capture.presets.NAME's type/status/project/tags/priority "
            "defaults before capture shorthand and explicit flags, which "
            "still win over the preset for the same field. See `lifetxt "
            "config explain capture.presets`."
        ),
    )
    for key in DETAIL_FLAGS:
        dest = "from_" if key == "from" else key
        quick.add_argument(
            "--" + key,
            dest=dest,
            action="append",
            help="Set %s: detail. Can be repeated. Accepts relative dates for due/do/until (today, tomorrow, friday, next_week)."
            % key,
        )
    quick.set_defaults(
        func=command_quick, detail=None, add_detail=None, remove_detail=None
    )

    done_cmd = subparsers.add_parser(
        "done",
        aliases=["d"],
        help=(
            "Mark a task as complete and append done:TODAY. For habit (H) items, "
            "append done:DATE to the completion log instead of changing status."
        ),
    )
    done_cmd.add_argument("path", help="life.txt file containing the item.")
    done_cmd.add_argument(
        "id",
        nargs="?",
        default=None,
        help="ID of the item to mark done.",
    )
    done_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    done_cmd.add_argument("--text", default=None, help="Title substring to search for.")
    done_cmd.add_argument(
        "--date",
        default=None,
        help="Completion date (YYYY-MM-DD). Defaults to today.",
    )
    done_cmd.add_argument(
        "--now",
        action="store_true",
        help="Record done: with the current time, not just the date.",
    )
    done_cmd.add_argument(
        "--date-only",
        action="store_true",
        help="Record done: with the date only, overriding config done.precision.",
    )
    done_cmd.add_argument(
        "--force",
        action="store_true",
        help="Allow logging a duplicate same-day habit completion.",
    )
    done_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    done_cmd.set_defaults(func=command_done)

    files_cmd = subparsers.add_parser(
        "files",
        help="Inspect, verify, and hash file: and dir: attachments.",
    )
    _add_input_paths(files_cmd)
    files_cmd.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when an attachment is missing, changed, or the wrong type.",
    )
    files_cmd.add_argument(
        "--update",
        action="store_true",
        help="Write or refresh the #sha256= hash on every resolvable attachment.",
    )
    files_cmd.add_argument(
        "--problems",
        action="store_true",
        help="Only show attachments that are missing, changed, or non-portable.",
    )
    files_cmd.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip hashing; only resolve and check existence. Much faster on large trees.",
    )
    files_cmd.add_argument(
        "--id",
        dest="item_id",
        default=None,
        help="Only inspect attachments on this item id.",
    )
    files_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    files_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="With --update, show what would change without writing.",
    )
    files_cmd.set_defaults(func=command_files)

    rrule_cmd = subparsers.add_parser(
        "rrule",
        help="Expand a recurrence rule into concrete occurrences.",
    )
    rrule_cmd.add_argument(
        "rule",
        nargs="?",
        default=None,
        help='Rule to expand, such as daily or "RRULE:FREQ=WEEKLY;BYDAY=MO,WE".',
    )
    rrule_cmd.add_argument(
        "--path",
        default=None,
        help="life.txt file to read a rule from instead of passing one.",
    )
    rrule_cmd.add_argument(
        "--id",
        dest="item_id",
        default=None,
        help="Expand the repeat: of this item id (requires --path).",
    )
    rrule_cmd.add_argument(
        "--from",
        dest="start",
        default=None,
        help="Series start (YYYY-MM-DD or with a time). Defaults to today, or the item's due/do/from.",
    )
    rrule_cmd.add_argument(
        "--after", default=None, help="Only show occurrences on or after this date."
    )
    rrule_cmd.add_argument(
        "--before", default=None, help="Only show occurrences on or before this date."
    )
    rrule_cmd.add_argument(
        "--count",
        type=int,
        default=None,
        help="Maximum occurrences to print. Defaults to 10.",
    )
    rrule_cmd.add_argument(
        "--format",
        choices=("text", "json", "life"),
        default="text",
        help="Output format. life emits one deadline record per occurrence.",
    )
    rrule_cmd.add_argument(
        "--type",
        dest="kind",
        default="D",
        help="Item type for --format life. Defaults to D.",
    )
    rrule_cmd.add_argument(
        "--title",
        default=None,
        help="Title for --format life. Defaults to the source item's title.",
    )
    rrule_cmd.set_defaults(func=command_rrule)

    state_cmd = subparsers.add_parser(
        "state",
        aliases=["s"],
        help=(
            "Record a presence status, closing the previous open one. "
            "Use `status` to read the current state."
        ),
    )
    state_cmd.add_argument(
        "state",
        nargs="?",
        default=None,
        help="New presence state, such as busy, focus, away, or offline.",
    )
    state_cmd.add_argument(
        "path",
        nargs="?",
        default=None,
        help="life.txt file to write to. Defaults to config write_file.",
    )
    state_cmd.add_argument(
        "--title", default=None, help="Status title. Defaults to the state name."
    )
    state_cmd.add_argument(
        "--person", default=None, help="Person the status belongs to. Defaults to self."
    )
    state_cmd.add_argument(
        "--note", default=None, help="Free-text note stored as note:."
    )
    state_cmd.add_argument(
        "--project", default=None, help="Associated project stored as project:."
    )
    state_cmd.add_argument(
        "--service", default=None, help="Service stored as service:."
    )
    state_cmd.add_argument(
        "--visibility", default=None, help="Visibility stored as visibility:."
    )
    state_cmd.add_argument(
        "--at",
        default=None,
        help="Transition time (YYYY-MM-DDTHH:MM). Defaults to now.",
    )
    state_cmd.add_argument(
        "--end",
        action="store_true",
        help="Close the current status without opening a new one.",
    )
    state_cmd.add_argument(
        "--force",
        action="store_true",
        help="Record a new record even when the state is already open.",
    )
    state_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    state_cmd.set_defaults(func=command_state)

    start_cmd = subparsers.add_parser(
        "start",
        help="Start work on a task: set it in progress, start the timer, and set presence.",
    )
    start_cmd.add_argument("path", help="life.txt file containing the item.")
    start_cmd.add_argument(
        "id", nargs="?", default=None, help="ID of the item to start."
    )
    start_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    start_cmd.add_argument(
        "--text", default=None, help="Title substring to search for."
    )
    start_cmd.add_argument(
        "--state",
        default="busy",
        help="Presence state to record while working. Defaults to busy.",
    )
    start_cmd.add_argument(
        "--no-presence",
        action="store_true",
        help="Do not record a presence status.",
    )
    start_cmd.add_argument(
        "--no-timer",
        action="store_true",
        help="Do not start the task timer.",
    )
    start_cmd.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    start_cmd.add_argument(
        "--timer-revision",
        help="Expected timer-state revision; use <missing> when idle.",
    )
    start_cmd.add_argument(
        "--require-revisions",
        action="store_true",
        help="Reject missing item/timer revisions.",
    )
    start_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    start_cmd.set_defaults(func=command_start)

    stop_cmd = subparsers.add_parser(
        "stop",
        help="Stop work: stop the timer, write elapsed:, close presence, and optionally finish the task.",
    )
    stop_cmd.add_argument(
        "path",
        nargs="?",
        default=None,
        help="life.txt file. Defaults to the file recorded by the running timer.",
    )
    stop_cmd.add_argument(
        "--done",
        action="store_true",
        help="Also mark the task complete and record done:.",
    )
    stop_cmd.add_argument(
        "--no-presence",
        action="store_true",
        help="Leave the presence status open.",
    )
    stop_cmd.add_argument(
        "--item-revision", help="Expected SHA-256 revision of life.txt."
    )
    stop_cmd.add_argument(
        "--timer-revision", help="Expected timer-state SHA-256 revision."
    )
    stop_cmd.add_argument(
        "--require-revisions",
        action="store_true",
        help="Reject missing item/timer revisions.",
    )
    stop_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    stop_cmd.set_defaults(func=command_stop)

    progress_cmd = subparsers.add_parser(
        "progress",
        help="Increment/decrement or directly set an item's progress: value "
        "(#660, #665).",
    )
    progress_cmd.add_argument("path", help="life.txt file containing the item.")
    progress_group = progress_cmd.add_mutually_exclusive_group(required=True)
    progress_group.add_argument(
        "--delta",
        help=(
            "Signed delta: +N/-N changes a fraction's current (total is kept), "
            "+N%%/-N%% changes a percentage's value. Representation kind is "
            "always preserved. A negative value must use --delta=-N (with '='); "
            "'--delta -N' is parsed as an unknown flag by argparse. Requires "
            "an existing progress: value."
        ),
    )
    progress_group.add_argument(
        "--set",
        dest="set_value",
        help=(
            "Directly set progress: to VALUE (e.g. 75%% or 3/10), replacing "
            "any existing value as-is with no fraction/percentage "
            "conversion. Works even when the item has no progress: yet. "
            "Mutually exclusive with --delta."
        ),
    )
    progress_cmd.add_argument(
        "id", nargs="?", default=None, help="ID of the item to update."
    )
    progress_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    progress_cmd.add_argument(
        "--text", default=None, help="Title substring to search for."
    )
    progress_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    progress_cmd.set_defaults(func=command_progress)

    clone_cmd = subparsers.add_parser(
        "clone",
        help="Create a new item derived from an existing one, resetting "
        "identity/history details (#659).",
    )
    clone_cmd.add_argument("path", help="life.txt file containing the source item.")
    clone_cmd.add_argument(
        "id", nargs="?", default=None, help="ID of the item to clone."
    )
    clone_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    clone_cmd.add_argument(
        "--text", default=None, help="Title substring to search for."
    )
    clone_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the generated item without writing it.",
    )
    clone_cmd.set_defaults(func=command_clone)

    reopen_cmd = subparsers.add_parser(
        "reopen",
        help="Undo an item's completion: remove done: and restore its "
        "kind-aware open status (#664).",
    )
    reopen_cmd.add_argument("path", help="life.txt file containing the item.")
    reopen_cmd.add_argument(
        "id", nargs="?", default=None, help="ID of the item to reopen."
    )
    reopen_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    reopen_cmd.add_argument(
        "--text", default=None, help="Title substring to search for."
    )
    reopen_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    reopen_cmd.set_defaults(func=command_reopen)

    due_cmd = subparsers.add_parser(
        "due",
        help="Set, replace, or clear an item's due: date (#666).",
    )
    due_cmd.add_argument("path", help="life.txt file containing the item.")
    due_cmd.add_argument("id", help="ID of the item to update.")
    due_cmd.add_argument(
        "date",
        nargs="?",
        default=None,
        help="New due date: YYYY-MM-DD, today, tomorrow, yesterday, a "
        "weekday, next_week, or an offset such as +3d/-1w/+2m. Omit when "
        "using --clear.",
    )
    due_cmd.add_argument(
        "--clear",
        action="store_true",
        help="Remove due: from the item instead of setting one.",
    )
    due_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    due_cmd.set_defaults(func=command_due)

    complete_cmd = subparsers.add_parser(
        "complete",
        help=(
            "Complete a repeat-enabled task instance and materialize the next occurrence "
            "(Taskwarrior-style). Non-repeating items behave like `done`."
        ),
    )
    complete_cmd.add_argument("path", help="life.txt file containing the item.")
    complete_cmd.add_argument(
        "id",
        nargs="?",
        default=None,
        help="ID of the item to complete.",
    )
    complete_cmd.add_argument(
        "--line", type=int, default=None, help="Line number of the item."
    )
    complete_cmd.add_argument(
        "--text", default=None, help="Title substring to search for."
    )
    complete_cmd.add_argument(
        "--date",
        default=None,
        help="Completion date (YYYY-MM-DD), used as the repeat_base:done anchor. Defaults to today.",
    )
    complete_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the file.",
    )
    complete_cmd.set_defaults(func=command_complete)

    batch_cmd = subparsers.add_parser(
        "batch",
        help="Apply a simple item command across multiple life.txt files.",
    )
    batch_cmd.add_argument(
        "action",
        choices=("done", "assign", "tag-rename", "tag-merge", "migrate"),
        help="Action to apply.",
    )
    batch_cmd.add_argument(
        "paths", nargs="+", help="Input file(s), directories, or glob patterns."
    )
    batch_cmd.add_argument(
        "--id", action="append", dest="ids", help="Item ID to target. Can be repeated."
    )
    batch_cmd.add_argument(
        "--text",
        action="append",
        dest="texts",
        help="Title substring to target. Can be repeated.",
    )
    batch_cmd.add_argument("--to", help="Assignee for action=assign.")
    batch_cmd.add_argument("--old", help="Old tag value for tag-rename/tag-merge.")
    batch_cmd.add_argument("--new", help="New tag value for tag-rename/tag-merge.")
    batch_cmd.add_argument(
        "--migration",
        action="append",
        dest="migrations",
        help="Migration to apply for action=migrate. Can be repeated.",
    )
    batch_cmd.add_argument(
        "--backup",
        action="store_true",
        help="Write backups for actions that support it.",
    )
    batch_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview actions without writing."
    )
    batch_cmd.set_defaults(func=command_batch)

    summary = subparsers.add_parser(
        "summary",
        help="Show a fast overview of a life.txt file.",
    )
    summary.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s). Reads stdin when omitted.",
    )
    summary.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    summary.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    summary.add_argument(
        "--compare",
        metavar="PATH",
        help="Compare summary of this file against a second file side-by-side.",
    )
    summary.set_defaults(func=command_summary)

    init_cmd = subparsers.add_parser(
        "init",
        help="Interactive first-time setup: create life.txt and .lifetxt.json.",
    )
    init_cmd.add_argument(
        "--file",
        default="life.txt",
        help="life.txt file to create. Defaults to life.txt.",
    )
    init_cmd.add_argument(
        "--config-output",
        dest="config_output",
        default=".lifetxt.json",
        help="Config file to create. Defaults to .lifetxt.json.",
    )
    init_cmd.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting.",
    )
    init_cmd.add_argument("--name", help="Your name (for #! self: directive).")
    init_cmd.add_argument(
        "--timezone", help="Your timezone (for #! timezone: directive)."
    )
    init_cmd.add_argument(
        "--project", help="Default project name (for #! project: directive)."
    )
    init_cmd.add_argument(
        "--preset",
        choices=preset_names(),
        default=None,
        help="Starter section skeleton for a common use case. Defaults to "
        "minimal (today's plain single-task starter, unchanged).",
    )
    init_cmd.add_argument(
        "--yes",
        action="store_true",
        help="Run fully non-interactively using defaults (self, UTC, no project).",
    )
    init_cmd.set_defaults(func=command_init)

    doctor_cmd = subparsers.add_parser(
        "doctor",
        help="Check Python version, files, dependencies, and data issues.",
    )
    doctor_cmd.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to check. Defaults to config paths or life.txt.",
    )
    doctor_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    doctor_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    doctor_cmd.add_argument(
        "--check-update",
        action="store_true",
        help=(
            "Also check GitHub for a newer lifetxt release or tag "
            "(read-only network request; adds an 'update' row). Off by "
            "default so plain doctor never requires network access."
        ),
    )
    doctor_cmd.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help=(
            "Repository --check-update queries. Overrides the "
            "update.repository config key and the built-in default "
            "(Eruhitsuji/lifetxt). Ignored without --check-update."
        ),
    )
    doctor_cmd.add_argument(
        "--update-timeout",
        type=int,
        default=5,
        metavar="SECONDS",
        help="Network timeout for --check-update (default 5).",
    )
    doctor_cmd.set_defaults(func=command_doctor)

    update_check_cmd = subparsers.add_parser(
        "update-check",
        help="Check GitHub for a newer lifetxt release or tag (read-only).",
    )
    update_check_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    update_check_cmd.add_argument(
        "--timeout",
        type=int,
        default=10,
        metavar="SECONDS",
        help="Network timeout for the GitHub API request.",
    )
    update_check_cmd.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help=(
            "GitHub repository to check, e.g. a fork's own owner/name. "
            "Overrides the update.repository config key and the built-in "
            "default (Eruhitsuji/lifetxt)."
        ),
    )
    update_check_cmd.set_defaults(func=command_update_check)

    update_cmd = subparsers.add_parser(
        "update",
        help=(
            "Fast-forward the running lifetxt git install to a newer "
            "release, tag, or ref. Requires git; dry-run by default."
        ),
    )
    update_cmd.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Actually fast-forward the working tree. Without this, update "
            "only fetches and reports what would happen."
        ),
    )
    update_cmd.add_argument(
        "--ref",
        metavar="REF",
        help=(
            "Git ref (tag, branch, or commit) to update to. Defaults to "
            "the latest published GitHub release or tag."
        ),
    )
    update_cmd.add_argument(
        "--remote",
        metavar="NAME",
        help="Local git remote to fetch from. Defaults to 'origin'.",
    )
    update_cmd.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help=(
            "GitHub repository to look up the latest release/tag from "
            "(read-only; does not change which git remote is fetched). "
            "Overrides the update.repository config key and the built-in "
            "default (Eruhitsuji/lifetxt)."
        ),
    )
    update_cmd.add_argument(
        "--timeout",
        type=int,
        default=10,
        metavar="SECONDS",
        help="Timeout for the GitHub API request and each git subprocess.",
    )
    update_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    update_cmd.set_defaults(func=command_update)

    server_update_cmd = subparsers.add_parser(
        "server-update",
        help=(
            "Guarded production update for a systemd-managed install: "
            "backup, service stop/start, reinstall, hash/integrity "
            "verification, health check. See docs/deployment/ubuntu-server.md."
        ),
    )
    server_update_cmd.add_argument(
        "--server-config",
        metavar="PATH",
        required=True,
        help=(
            "Deployment config JSON file (distinct from the global "
            "--config application config.json) naming the target python "
            "environment, backup paths, services, and integrity checks."
        ),
    )
    server_update_cmd.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Actually apply the update. Without this, server-update only "
            "fetches and reports what would happen."
        ),
    )
    server_update_cmd.add_argument(
        "--approve",
        metavar="SHA",
        help=(
            "Apply an update that server-update flagged as high-impact, "
            "bound to the exact resolved target commit (copy-pasted from "
            "the printed review block's approved_command line). Implies "
            "--yes. Refused if the target has moved since the SHA was "
            "reviewed."
        ),
    )
    server_update_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    server_update_cmd.set_defaults(func=command_server_update)

    server_init_cmd = subparsers.add_parser(
        "server-init",
        help=(
            "Plan-first Ubuntu Server bootstrap for a production deployment. "
            "Dry-run by default; use --yes to apply the generated plan."
        ),
    )
    server_init_cmd.add_argument(
        "--server-config",
        metavar="PATH",
        required=True,
        help=(
            "Deployment bootstrap JSON file (distinct from the global "
            "--config application config.json)."
        ),
    )
    server_init_cmd.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Apply the bootstrap plan. Without this, server-init only reports "
            "what would be created or validated."
        ),
    )
    server_init_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    server_init_cmd.set_defaults(func=command_server_init)

    assign_cmd = subparsers.add_parser(
        "assign",
        help="Change the assignee: on an existing item.",
    )
    assign_cmd.add_argument("path", help="life.txt file containing the item.")
    assign_cmd.add_argument("id", nargs="?", help="ID of the item to reassign.")
    assign_cmd.add_argument(
        "--text",
        metavar="QUERY",
        help="Select item by title substring instead of ID.",
    )
    assign_cmd.add_argument(
        "--to",
        required=True,
        metavar="PERSON",
        help="New assignee name.",
    )
    assign_cmd.add_argument(
        "--notify",
        action="store_true",
        help="Append an M notification item to the new assignee.",
    )
    assign_cmd.add_argument(
        "--from-user",
        dest="from_user",
        metavar="NAME",
        help="Override sender name in --notify M-items (default: config user name).",
    )
    assign_cmd.set_defaults(func=command_assign)

    health_cmd = subparsers.add_parser(
        "health",
        help="Operational sanity checks: stale tasks, missed habits, upcoming deadlines.",
    )
    _add_input_paths(health_cmd)
    health_cmd.add_argument(
        "--since",
        type=int,
        default=30,
        metavar="DAYS",
        help="Days threshold for stale-task and habit checks. Defaults to 30.",
    )
    health_cmd.add_argument(
        "--lookahead",
        type=int,
        default=7,
        metavar="DAYS",
        help="Days lookahead for upcoming deadlines. Defaults to 7.",
    )
    health_cmd.add_argument(
        "--ignore",
        action="append",
        help="Suppress a health code, e.g. W301. Can be repeated or comma-separated.",
    )
    health_cmd.add_argument(
        "--type",
        action="append",
        dest="health_types",
        metavar="TYPE",
        help="Restrict checks to items of this type (T, H, E, etc.). Can be repeated or comma-separated.",
    )
    health_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    health_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    health_cmd.set_defaults(func=command_health)

    inbox_cmd = subparsers.add_parser(
        "inbox",
        help="List open tasks with no project, due date, or assignee.",
    )
    _add_input_paths(inbox_cmd)
    inbox_cmd.add_argument(
        "--type",
        dest="kinds",
        action="append",
        help="Filter by type. Defaults to T (task). Can be repeated or comma-separated.",
    )
    inbox_cmd.add_argument(
        "--text",
        help="Case-insensitive title substring filter.",
    )
    inbox_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    inbox_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    inbox_cmd.add_argument(
        "--process",
        action="store_true",
        help="Interactive one-by-one triage: prompts for project, due, and assignee for each inbox item.",
    )
    inbox_cmd.add_argument(
        "--fzf",
        action="store_true",
        help="Select an inbox item with fzf or peco and print the selected record.",
    )
    inbox_cmd.set_defaults(func=command_inbox)

    cleanup_cmd = subparsers.add_parser(
        "cleanup",
        help="Guided file-maintenance navigator: report issues and suggest next commands.",
    )
    _add_input_paths(cleanup_cmd)
    cleanup_cmd.add_argument(
        "--ignore",
        action="append",
        help="Suppress a diagnostic code. Can be repeated or comma-separated.",
    )
    cleanup_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    cleanup_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    cleanup_cmd.set_defaults(func=command_cleanup)

    undo_cmd = subparsers.add_parser(
        "undo",
        help="Restore a file to its state before the most recent write operation.",
    )
    undo_cmd.add_argument("path", help="life.txt file to restore.")
    undo_cmd.add_argument(
        "--revision", help="Expected current SHA-256 revision before restoring."
    )
    undo_cmd.add_argument(
        "--list",
        action="store_true",
        help="List the undo stack with timestamps and operation names.",
    )
    undo_cmd.set_defaults(func=command_undo)

    review_cmd = subparsers.add_parser(
        "review",
        help="Human-readable period summary: completed tasks, habits, mood, and elapsed time.",
    )
    _add_input_paths(review_cmd)
    review_cmd.add_argument(
        "--week",
        action="store_true",
        help="Review the current ISO week (Monday to today).",
    )
    review_cmd.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Review a specific calendar month.",
    )
    review_cmd.add_argument(
        "--from",
        dest="from_date",
        metavar="DATE",
        help="Start date for custom range (YYYY-MM-DD).",
    )
    review_cmd.add_argument(
        "--to",
        dest="to_date",
        metavar="DATE",
        help="End date for custom range (YYYY-MM-DD).",
    )
    review_cmd.add_argument(
        "--project",
        help="Restrict review to a specific project.",
    )
    review_cmd.add_argument(
        "--temporal",
        action="store_true",
        help="Use the deterministic Temporal Life Review.",
    )
    review_cmd.add_argument(
        "--since", help="Temporal review start (RFC3339 or YYYY-MM-DD)."
    )
    review_cmd.add_argument(
        "--until", help="Temporal review end (RFC3339 or YYYY-MM-DD)."
    )
    review_cmd.add_argument(
        "--limit", type=int, default=100, help="Maximum timeline events to return."
    )
    review_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl", "markdown", "html"),
        default="text",
        help="Output format.",
    )
    review_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    review_cmd.set_defaults(func=command_review)

    who_cmd = subparsers.add_parser(
        "who",
        help="Team presence summary: latest active S item per person across loaded files.",
    )
    _add_input_paths(who_cmd)
    who_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    who_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    who_cmd.set_defaults(func=command_who)

    search_cmd = subparsers.add_parser(
        "search",
        help="Search life.txt items by substring or regex match in title or field values.",
    )
    _add_input_paths(search_cmd)
    search_cmd.add_argument("pattern", help="Substring or regex pattern to match.")
    search_cmd.add_argument(
        "--regex",
        action="store_true",
        help="Treat pattern as a regular expression (case-insensitive).",
    )
    search_cmd.add_argument(
        "--in",
        dest="in_fields",
        action="append",
        metavar="FIELD",
        help="Scope search to a detail field (e.g. title, body, note). Can be repeated or comma-separated.",
    )
    search_cmd.add_argument(
        "--format",
        choices=("text", "life", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    search_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    search_cmd.add_argument(
        "--highlight",
        action="store_true",
        help="Highlight matched text with ANSI color in text output.",
    )
    search_cmd.add_argument(
        "--count",
        action="store_true",
        help="Print only the count of matching items, not the items themselves.",
    )
    search_cmd.add_argument(
        "--fuzzy",
        action="store_true",
        help="Also match a field within a small typo/edit distance of pattern, "
        "not only an exact substring. Cannot be combined with --regex.",
    )
    search_cmd.set_defaults(func=command_search)

    snapshot_cmd = subparsers.add_parser(
        "snapshot",
        help="Copy a life.txt file to a timestamped snapshot for point-in-time backups.",
    )
    snapshot_cmd.add_argument("path", help="Source life.txt file to snapshot.")
    snapshot_cmd.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Output path. Defaults to <dir>/snapshots/YYYY-MM-DD_<basename>.",
    )
    snapshot_cmd.add_argument(
        "--dir",
        dest="snapshot_dir",
        default=None,
        help="Directory to write the snapshot. Defaults to a 'snapshots/' subdir next to the source.",
    )
    snapshot_cmd.add_argument(
        "--diff",
        action="store_true",
        help="Show a semantic diff between the new snapshot and the most recent previous snapshot in the same directory.",
    )
    snapshot_cmd.set_defaults(func=command_snapshot)

    lint_cmd = subparsers.add_parser(
        "lint",
        help="Check life.txt for style issues: key-name typos, tag casing, and duplicate keys.",
    )
    _add_input_paths(lint_cmd)
    lint_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    lint_cmd.add_argument(
        "--fix",
        action="store_true",
        help="Auto-correct safe issues in-place (writes to the writable path only).",
    )
    lint_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="With --fix, show what would change without writing anything.",
    )
    lint_cmd.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    lint_cmd.add_argument(
        "--ruleset",
        dest="ruleset",
        metavar="FILE",
        help="JSON file with custom rules (list of {pattern, replacement, message}).",
    )
    lint_cmd.set_defaults(func=command_lint)

    # diff command
    diff_cmd = subparsers.add_parser(
        "diff",
        help="Semantic diff between two life.txt files: added, removed, status-changed, detail-changed.",
    )
    diff_cmd.add_argument("before", help="Base life.txt file (older state).")
    diff_cmd.add_argument("after", help="Updated life.txt file (newer state).")
    diff_cmd.add_argument(
        "--format",
        choices=("text", "json", "jsonl"),
        default="text",
        help="Output format.",
    )
    diff_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    diff_cmd.add_argument(
        "--type",
        dest="kinds",
        action="append",
        help="Filter diff by item type. Can be repeated.",
    )
    diff_cmd.add_argument(
        "--project",
        action="append",
        help="Filter diff by project. Can be repeated.",
    )
    diff_cmd.add_argument(
        "--status",
        dest="change_types",
        action="append",
        choices=(
            "added",
            "removed",
            "completed",
            "canceled",
            "status-changed",
            "detail-changed",
        ),
        help="Limit output to specific change types. Can be repeated.",
    )
    diff_cmd.add_argument(
        "--since",
        metavar="DATE",
        help="Auto-select the most recent snapshot from this date (YYYY-MM-DD) as the base file.",
    )
    diff_cmd.set_defaults(func=command_diff)

    # plot command
    plot_cmd = subparsers.add_parser(
        "plot",
        help="Render task/habit/mood/elapsed statistics as Unicode bar charts.",
    )
    _add_input_paths(plot_cmd)
    plot_cmd.add_argument(
        "--chart",
        choices=("tasks", "habits", "mood", "elapsed", "deadlines", "all"),
        default="all",
        help="Which chart to render (default: all).",
    )
    plot_cmd.add_argument(
        "--sparkline",
        action="store_true",
        help="Output sparklines (single-row Unicode trend) instead of full bar charts.",
    )
    plot_cmd.add_argument(
        "--group",
        choices=("daily", "weekly", "monthly"),
        default="weekly",
        help="Time bucket size for trend charts.",
    )
    plot_cmd.add_argument(
        "--from", dest="start", metavar="DATE", help="Start date (YYYY-MM-DD)."
    )
    plot_cmd.add_argument(
        "--to", dest="end", metavar="DATE", help="End date (YYYY-MM-DD)."
    )
    plot_cmd.add_argument("--project", help="Restrict to a single project.")
    plot_cmd.add_argument(
        "--width",
        type=int,
        default=0,
        help="Chart width in characters (0 = auto-detect terminal width).",
    )
    plot_cmd.add_argument(
        "--format",
        choices=("text", "svg", "png"),
        default="text",
        help="Output format. SVG is dependency-free; PNG requires matplotlib.",
    )
    plot_cmd.add_argument(
        "-o", "--output", help="Output file for SVG/PNG. Text defaults to stdout."
    )
    plot_cmd.set_defaults(func=command_plot)

    heatmap_cmd = subparsers.add_parser(
        "export-heatmap",
        help="Export task or habit activity as a dependency-free SVG heatmap.",
    )
    _add_input_paths(heatmap_cmd)
    heatmap_cmd.add_argument(
        "--from", dest="start", metavar="DATE", help="Start date (YYYY-MM-DD)."
    )
    heatmap_cmd.add_argument(
        "--to", dest="end", metavar="DATE", help="End date (YYYY-MM-DD)."
    )
    heatmap_cmd.add_argument(
        "--type",
        dest="kind",
        choices=("task", "habit", "all"),
        default="all",
        help="Activity source: task done dates, habit done dates, or all.",
    )
    heatmap_cmd.add_argument("--project", help="Restrict to a single project.")
    heatmap_cmd.add_argument("--title", default="lifetxt activity", help="SVG title.")
    heatmap_cmd.add_argument(
        "-o", "--output", help="Output SVG file. Defaults to stdout."
    )
    heatmap_cmd.set_defaults(func=command_export_heatmap)

    # migrate command
    migrate_cmd = subparsers.add_parser(
        "migrate",
        help="Apply in-place format migrations to a life.txt file.",
    )
    migrate_cmd.add_argument("path", help="File to migrate.")
    migrate_cmd.add_argument(
        "--migration",
        action="append",
        dest="migrations",
        metavar="NAME[=ARG]",
        help=(
            "Migration to apply. Can be repeated. "
            "Built-in names: normalize-elapsed, rename-key OLD=NEW, add-id, "
            "normalize-status, strip-empty-details, canonicalize-dates."
        ),
    )
    migrate_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the file.",
    )
    migrate_cmd.add_argument(
        "--backup",
        action="store_true",
        help="Write a .bak file before modifying.",
    )
    migrate_cmd.set_defaults(func=command_migrate)

    # from-markdown command
    frommd_cmd = subparsers.add_parser(
        "from-markdown",
        help="Convert a Markdown task list (- [ ] title) to life.txt items.",
    )
    _add_input_paths(frommd_cmd)
    frommd_cmd.add_argument("-o", "--output", help="Output file (default: stdout).")
    frommd_cmd.add_argument("--project", help="Assign project: to all imported items.")
    frommd_cmd.add_argument(
        "--type",
        dest="kind",
        default="T",
        help="Item type for imported items (default: T).",
    )
    frommd_cmd.add_argument(
        "--append",
        action="store_true",
        help="Append to output file instead of overwrite.",
    )
    frommd_cmd.add_argument(
        "--preset",
        choices=("github",),
        help="Source format preset. 'github' maps GitHub Issues Markdown (checkbox lists with #NNN refs) to life.txt items with ref: set to the issue number.",
    )
    frommd_cmd.set_defaults(func=command_from_markdown)

    # deps command
    deps_cmd = subparsers.add_parser(
        "deps",
        help="Show dependency chains (depends_on:/blocks:) as an indented tree.",
    )
    _add_input_paths(deps_cmd)
    deps_cmd.add_argument(
        "--blocked",
        action="store_true",
        help="Only show items with unresolved (open) blockers.",
    )
    deps_cmd.add_argument(
        "--root",
        metavar="ID",
        help="Trace dependency chain from a specific item ID.",
    )
    deps_cmd.add_argument(
        "--format",
        choices=("text", "json", "mermaid", "dot"),
        default="text",
        help="Output format (default: text).",
    )
    deps_cmd.add_argument(
        "--depth",
        type=int,
        help="Maximum dependency depth to render. Depth 0 shows only root nodes.",
    )
    deps_cmd.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output."
    )
    deps_cmd.set_defaults(func=command_deps)

    # tag command
    tag_cmd = subparsers.add_parser("tag", help="Tag management: list, rename.")
    tag_subparsers = tag_cmd.add_subparsers(dest="tag_action")
    tag_list_cmd = tag_subparsers.add_parser("list", help="List all tags with counts.")
    _add_input_paths(tag_list_cmd)
    tag_list_cmd.add_argument("--format", choices=("text", "json"), default="text")
    tag_list_cmd.set_defaults(func=command_tag_list)
    tag_rename_cmd = tag_subparsers.add_parser("rename", help="Rename a tag in-place.")
    tag_rename_cmd.add_argument("old", help="Old tag value.")
    tag_rename_cmd.add_argument("new", help="New tag value.")
    tag_rename_cmd.add_argument("path", help="File to update.")
    tag_rename_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    tag_rename_cmd.set_defaults(func=command_tag_rename)
    tag_merge_cmd = tag_subparsers.add_parser(
        "merge", help="Rename a tag in-place and record alias in config."
    )
    tag_merge_cmd.add_argument("old", help="Old tag value to merge away.")
    tag_merge_cmd.add_argument("new", help="Canonical tag value to merge into.")
    tag_merge_cmd.add_argument("path", help="File to update.")
    tag_merge_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    tag_merge_cmd.add_argument("--revision", help="Expected life.txt SHA-256 revision.")
    tag_merge_cmd.add_argument(
        "--config-revision", help="Expected config JSON SHA-256 revision."
    )
    tag_merge_cmd.set_defaults(func=command_tag_merge)
    tag_cmd.set_defaults(func=lambda args: tag_cmd.print_help())

    # watch command
    watch_cmd = subparsers.add_parser(
        "watch",
        help="Watch life.txt files for changes and re-run a command on each change.",
    )
    _add_input_paths(watch_cmd)
    watch_cmd.add_argument(
        "--run",
        metavar="CMD",
        default="summary",
        help="lifetxt sub-command to re-run on change (default: summary).",
    )
    watch_cmd.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0).",
    )
    watch_cmd.add_argument(
        "--clear", action="store_true", help="Clear screen before each re-run."
    )
    watch_cmd.add_argument(
        "--timestamp",
        action="store_true",
        help="Print a timestamped header before each run.",
    )
    watch_cmd.add_argument(
        "--notify",
        action="store_true",
        help="Send a desktop notification or terminal bell when command exit status changes.",
    )
    watch_cmd.set_defaults(func=command_watch)

    # encrypt command
    encrypt_cmd = subparsers.add_parser(
        "encrypt",
        help="Encrypt selected field values in-place using a passphrase.",
    )
    encrypt_cmd.add_argument("path", help="File to encrypt.")
    encrypt_cmd.add_argument(
        "--field",
        action="append",
        dest="fields",
        metavar="FIELD",
        help="Field key to encrypt (e.g. body, note). Can be repeated.",
    )
    encrypt_cmd.add_argument(
        "--type",
        action="append",
        dest="kinds",
        metavar="TYPE",
        help="Only encrypt items of this type (e.g. J, M). Can be repeated.",
    )
    encrypt_cmd.add_argument(
        "--key-env",
        metavar="ENVVAR",
        default="LIFETXT_KEY",
        help="Environment variable containing the passphrase (default: LIFETXT_KEY).",
    )
    encrypt_cmd.add_argument(
        "--key-file",
        help="Read the passphrase from a UTF-8 text file. Overrides --key-env.",
    )
    encrypt_cmd.add_argument(
        "--algorithm",
        choices=("xsk", "aesgcm"),
        default="xsk",
        help="Encryption algorithm. xsk is dependency-free; aesgcm requires cryptography.",
    )
    encrypt_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    encrypt_cmd.add_argument(
        "--backup", action="store_true", help="Write .bak before modifying."
    )
    encrypt_cmd.set_defaults(func=command_encrypt)

    # decrypt command
    decrypt_cmd = subparsers.add_parser(
        "decrypt",
        help="Decrypt enc:-tagged field values in-place using a passphrase.",
    )
    decrypt_cmd.add_argument("path", help="File to decrypt.")
    decrypt_cmd.add_argument(
        "--field",
        action="append",
        dest="fields",
        metavar="FIELD",
        help="Field key to decrypt. Can be repeated (default: all enc: fields).",
    )
    decrypt_cmd.add_argument(
        "--key-env",
        metavar="ENVVAR",
        default="LIFETXT_KEY",
        help="Environment variable containing the passphrase (default: LIFETXT_KEY).",
    )
    decrypt_cmd.add_argument(
        "--key-file",
        help="Read the passphrase from a UTF-8 text file. Overrides --key-env.",
    )
    decrypt_cmd.add_argument(
        "--algorithm",
        choices=("auto", "xsk", "aesgcm"),
        default="auto",
        help="Expected algorithm. auto dispatches from the enc: tag.",
    )
    decrypt_cmd.add_argument(
        "--dry-run", action="store_true", help="Preview without writing."
    )
    decrypt_cmd.add_argument(
        "--backup", action="store_true", help="Write .bak before modifying."
    )
    decrypt_cmd.set_defaults(func=command_decrypt)

    # share command
    share_cmd = subparsers.add_parser(
        "share",
        help="Export a self-contained HTML or Markdown report combining filtered items and charts.",
    )
    _add_input_paths(share_cmd)
    _add_item_filter_arguments(share_cmd)
    share_cmd.add_argument(
        "--week",
        action="store_true",
        help="Restrict range label to the current ISO week (Monday to today).",
    )
    share_cmd.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Restrict range label to a specific calendar month.",
    )
    share_cmd.add_argument(
        "--format",
        choices=("html", "markdown"),
        default="html",
        help="Output format. Defaults to html.",
    )
    share_cmd.add_argument(
        "-o", "--output", help="Output file. Defaults to share.html or share.md."
    )
    share_cmd.add_argument(
        "--title", help="Report title. Defaults to 'lifetxt share report'."
    )
    share_cmd.set_defaults(func=command_share)

    # digest command
    digest_cmd = subparsers.add_parser(
        "digest",
        help="Deliver a review summary to Slack, email, or a local file.",
    )
    _add_input_paths(digest_cmd)
    digest_cmd.add_argument(
        "--week",
        action="store_true",
        help="Digest the current ISO week (Monday to today).",
    )
    digest_cmd.add_argument(
        "--month", metavar="YYYY-MM", help="Digest a specific calendar month."
    )
    digest_cmd.add_argument("--project", help="Restrict digest to a specific project.")
    digest_cmd.add_argument(
        "--report",
        metavar="NAME",
        help=(
            "Use a configured `lifetxt report` profile as the digest message "
            "source instead of the built-in review summary. --week/--month/"
            "--project are ignored when --report is given."
        ),
    )
    digest_cmd.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="With --report: generate the period containing this date instead of today.",
    )
    digest_cmd.add_argument(
        "--previous",
        action="store_true",
        help="With --report: generate the immediately completed previous period.",
    )
    digest_cmd.add_argument(
        "--format",
        dest="channel",
        choices=("slack-webhook", "email", "file"),
        required=True,
        help="Delivery channel.",
    )
    digest_cmd.add_argument(
        "--url-env",
        metavar="ENVVAR",
        help="Environment variable with the Slack incoming webhook URL (--format slack-webhook).",
    )
    digest_cmd.add_argument("--to", help="Recipient email address (--format email).")
    digest_cmd.add_argument(
        "--smtp-host-env",
        metavar="ENVVAR",
        default="LIFETXT_SMTP_HOST",
        help="Environment variable with the SMTP host (--format email).",
    )
    digest_cmd.add_argument(
        "--smtp-user-env",
        metavar="ENVVAR",
        default="LIFETXT_SMTP_USER",
        help="Environment variable with the SMTP username (--format email).",
    )
    digest_cmd.add_argument(
        "--smtp-pass-env",
        metavar="ENVVAR",
        default="LIFETXT_SMTP_PASS",
        help="Environment variable with the SMTP password (--format email).",
    )
    digest_cmd.add_argument(
        "--smtp-port",
        type=int,
        metavar="PORT",
        help="Explicit SMTP port, e.g. 587 for STARTTLS submission (--format email).",
    )
    digest_cmd.add_argument(
        "--path",
        dest="digest_path",
        help="Local file to append Markdown to (--format file).",
    )
    digest_cmd.add_argument(
        "--revision", help="Expected SHA-256 revision of the local digest file."
    )
    digest_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the digest and print what would be sent without making a network request or writing.",
    )
    digest_cmd.set_defaults(func=command_digest)

    # template command
    template_cmd = subparsers.add_parser(
        "template",
        help="List and apply reusable named item templates from config.",
    )
    template_subparsers = template_cmd.add_subparsers(dest="template_command")
    template_list_cmd = template_subparsers.add_parser(
        "list", help="List available templates."
    )
    template_list_cmd.set_defaults(func=command_template_list)
    template_apply_cmd = template_subparsers.add_parser(
        "apply", help="Expand a template and append the result to a file."
    )
    template_apply_cmd.add_argument(
        "name", help="Template name (key under config templates)."
    )
    template_apply_cmd.add_argument(
        "--append",
        metavar="FILE",
        required=True,
        help="File to append the expanded template to.",
    )
    template_apply_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the expanded template without writing.",
    )
    template_apply_cmd.add_argument(
        "--revision", help="Expected SHA-256 revision of the append target."
    )
    template_apply_cmd.set_defaults(func=command_template_apply)

    return parser


def _add_input_paths(parser):
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="Input file(s), or - for stdin. Reads stdin when omitted.",
    )


def _add_import_core_arguments(parser):
    """Arguments shared by `import-ics` and `import`.

    `import` is a thin routing dispatcher over the same `command_import_ics`
    implementation (see `command_import`), so both subparsers register the
    exact same flags here rather than each defining its own copy. Only the
    `--preset` default differs between the two and stays defined separately
    on each subparser.
    """
    _add_input_paths(parser)
    parser.add_argument("-o", "--output", help="Output file. Defaults to stdout.")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to --output instead of overwriting it.",
    )
    parser.add_argument(
        "--project",
        help="Add this project: detail to every imported event.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Add this tag: detail to every imported event. Can be repeated.",
    )
    parser.add_argument(
        "--expand-rrule",
        action="store_true",
        help="Write one record per occurrence instead of a single record with repeat:RRULE:.",
    )
    parser.add_argument(
        "--expand-until",
        help="Expand occurrences up to this date. Defaults to one year out.",
    )
    parser.add_argument(
        "--expand-count",
        type=int,
        help="Maximum occurrences per recurring event. Capped at 500.",
    )


def _add_serve_core_arguments(parser):
    """Arguments shared by `serve` and `web`: one authoritative Web runtime.

    `web` is a convenience launcher over `serve`'s own resolution/safety
    behavior (see `_prepare_serve`), so both subparsers register the exact
    same flags here rather than each defining its own copy.
    """
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="path",
        help="life.txt file(s) to read. Defaults to life.txt.",
    )
    parser.add_argument(
        "--write-file",
        help="File used for create, update, and delete operations. Defaults to the first path.",
    )
    parser.add_argument("--host", help="Bind host.")
    parser.add_argument("--port", type=int, help="Bind port.")
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Disable all write endpoints (POST/PUT/DELETE) except /api/check-line. Safe for public deployments.",
    )
    parser.add_argument(
        "--token-env",
        metavar="ENVVAR",
        help="Read the API bearer token from ENVVAR instead of storing it in config.",
    )
    parser.add_argument(
        "--insecure-public",
        action="store_true",
        help="Allow a non-loopback writable Web server without a bearer token. Not recommended.",
    )


def _add_item_filter_arguments(parser):
    parser.add_argument(
        "--open",
        action="store_true",
        help="Keep unfinished workflow items only: [ ], [/], [>], or [?].",
    )
    parser.add_argument(
        "--status",
        action="append",
        help="Filter by status or alias. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--type",
        dest="kinds",
        action="append",
        help="Filter by type or alias. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--project",
        action="append",
        help="Filter by project detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        help="Filter by tag detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--tag-all",
        action="append",
        help="Require every listed tag value. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--exclude-tag",
        action="append",
        help="Exclude items containing any listed tag value. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--user",
        action="append",
        help="Filter by any user-related detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--team",
        action="append",
        help="Filter by team/group detail or config-defined team membership.",
    )
    parser.add_argument(
        "--person",
        action="append",
        help="Filter by person detail. Missing person on S items defaults to self.",
    )
    parser.add_argument(
        "--owner",
        action="append",
        help="Filter by owner detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--assignee",
        action="append",
        help="Filter by assignee detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--attendee",
        action="append",
        help="Filter by attendee detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--sender",
        action="append",
        help="Filter by sender detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--recipient",
        action="append",
        help="Filter by recipient detail. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--detail",
        action="append",
        default=[],
        help="Filter by detail key or key=value. Repeated filters are ANDed.",
    )
    parser.add_argument(
        "--text",
        help="Case-insensitive substring filter across title, line, and detail values.",
    )
    parser.add_argument(
        "--after",
        help="Keep items related to this time or later: now, YYYY-MM-DD, or ISO-like datetime.",
    )
    parser.add_argument(
        "--before",
        help="Keep items related to this time or earlier: now, YYYY-MM-DD, or ISO-like datetime.",
    )


def _add_occurrence_export_arguments(parser):
    parser.add_argument(
        "--occurrences",
        action="store_true",
        help=(
            "Export generated agenda occurrence records instead of stored items. "
            "Requires --after and --before to bound recurrence expansion."
        ),
    )


_W225_GUIDANCE = (
    "  Hint: To resolve W225, either (1) close children manually, "
    "(2) run archive --orphan-children adopt, or (3) run archive --orphan-children promote."
)


def command_check(args):
    config = _config(args)
    items, diagnostics = _parse_life_inputs(args.paths, config)
    from .progress_history import progress_history_diagnostics
    from .native_history import item_event_history_diagnostics

    diagnostics = diagnostics + progress_history_diagnostics(
        items, id_key=id_key_from_config(config)
    )
    diagnostics = diagnostics + item_event_history_diagnostics(
        items, id_key=id_key_from_config(config)
    )
    diagnostics = diagnostics + _attachment_diagnostics_for_check(items, config, args)
    ignore_codes = getattr(args, "ignore_codes", None)
    filtered_diagnostics = filter_diagnostics(
        diagnostics,
        severities=getattr(args, "diagnostic_severities", None),
        codes=getattr(args, "diagnostic_codes", None),
        categories=getattr(args, "diagnostic_categories", None),
        ignore_codes=ignore_codes,
    )
    has_filter = any(
        getattr(args, name, None)
        for name in (
            "diagnostic_severities",
            "diagnostic_codes",
            "diagnostic_categories",
            "ignore_codes",
        )
    )

    if args.format == "json":
        output = json.dumps(
            [
                diagnostic_to_output_dict(diagnostic)
                for diagnostic in filtered_diagnostics
            ],
            ensure_ascii=False,
            indent=2,
        )
        write_text(None, output + "\n")
    elif args.format == "sarif":
        write_text(None, render_sarif(filtered_diagnostics))
    else:
        if filtered_diagnostics:
            cascade_roles = classify_cascade_roles(filtered_diagnostics)
            for index, diagnostic in enumerate(filtered_diagnostics):
                if index:
                    write_text(None, "\n")
                relation = cascade_roles.get(id(diagnostic))
                write_text(
                    None, render_diagnostic_rich(diagnostic, relation=relation) + "\n"
                )
                if str(getattr(diagnostic, "code", "")).upper() == "W225":
                    write_text(None, _W225_GUIDANCE + "\n")
            write_text(
                None, "\n" + render_diagnostics_summary(filtered_diagnostics) + "\n"
            )
        elif has_filter:
            write_text(
                None, _t("check.ok_no_matching_diagnostics", n=len(items)) + "\n"
            )
        else:
            write_text(None, _t("check.ok", n=len(items)) + "\n")

    return _exit_code(filtered_diagnostics, args.warnings_as_errors)


def command_integrity(args):
    from .integrity import (
        apply_missing_id_repair,
        build_integrity_plan,
        build_integrity_report,
        format_integrity_text,
        integrity_apply_to_json,
        integrity_plan_to_json,
        integrity_report_to_json,
    )

    paths = list(args.paths or [])
    if paths and paths[0] == "plan":
        plan = build_integrity_plan(
            paths[1:],
            config=_config(args),
            verify_files=getattr(args, "verify_files", False),
            profile=getattr(args, "profile", "default"),
            ai_context=getattr(args, "ai_context", False),
            graph=getattr(args, "graph", False),
        )
        write_text(None, integrity_plan_to_json(plan))
        return 0

    if paths and paths[0] == "apply":
        try:
            result = apply_missing_id_repair(
                paths[1] if len(paths) > 1 else None,
                config=_config(args),
                expected_revision=getattr(args, "expected_revision", None),
                confirm=getattr(args, "confirm", False),
                prefix=getattr(args, "prefix", None),
            )
        except Exception as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1 if "conflict" in str(exc).lower() else 2
        if getattr(args, "json", False):
            write_text(None, integrity_apply_to_json(result))
        else:
            write_text(
                None,
                "integrity apply: %d ID assignment(s), %s -> %s\n"
                % (
                    result["assignment_count"],
                    result["before_revision"],
                    result["after_revision"],
                ),
            )
        return 0

    report = build_integrity_report(
        paths,
        config=_config(args),
        verify_files=getattr(args, "verify_files", False),
        profile=getattr(args, "profile", "default"),
        ai_context=getattr(args, "ai_context", False),
        graph=getattr(args, "graph", False),
    )
    if getattr(args, "json", False):
        write_text(None, integrity_report_to_json(report))
    else:
        write_text(None, format_integrity_text(report))
    return 0


def command_ids(args):
    if args.assign:
        return command_ids_assign(args)

    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    key = args.key or id_key_from_config(_config(args))
    audit = id_audit(items, key=key)

    if args.format == "json":
        output = json.dumps(
            _id_audit_output(audit, args.only),
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        records = _id_audit_jsonl_records(audit, args.only)
        output = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        if output:
            output += "\n"
        write_text(None, output)
    else:
        write_text(None, format_id_audit(audit, args.only))

    _print_warnings(diagnostics)
    return 0


def command_links(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    key = args.key or id_key_from_config(_config(args))
    topo = getattr(args, "topo", False)
    crit = getattr(args, "critical_path", False)
    path_ids = getattr(args, "path", None)

    if topo:
        if args.item_id or args.chain or crit or path_ids:
            raise ValueError(
                "--topo cannot be combined with --id, --chain, "
                "--critical-path, or --path."
            )
        if args.direction != "both":
            raise ValueError("--direction is only valid with --id, not --topo.")
        if args.format in ("mermaid", "dot"):
            raise ValueError("--topo supports text, json, or jsonl output.")
        try:
            order = topological_order(
                items, key=key, relations=_split_csv_args(args.relation)
            )
        except ValueError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        if args.format == "json":
            write_text(
                None,
                json.dumps(
                    {"order": order},
                    ensure_ascii=False,
                    indent=2 if args.pretty else None,
                    separators=None if args.pretty else (",", ":"),
                )
                + "\n",
            )
        elif args.format == "jsonl":
            output = "\n".join(
                json.dumps({"id": node_id}, ensure_ascii=False, separators=(",", ":"))
                for node_id in order
            )
            if output:
                output += "\n"
            write_text(None, output)
        elif order:
            write_text(None, "\n".join(order) + "\n")
        else:
            write_text(None, "(no items participate in the dependency graph)\n")
        _print_warnings(diagnostics)
        return 0

    if crit:
        if args.item_id or topo or path_ids:
            raise ValueError(
                "--critical-path cannot be combined with --id, --topo, or --path."
            )
        if args.direction != "both":
            raise ValueError(
                "--direction is only valid with --id, not --critical-path."
            )
        if args.format in ("mermaid", "dot"):
            raise ValueError("--critical-path supports text, json, or jsonl output.")
        try:
            result = critical_path(
                items,
                key=key,
                root_id=args.chain,
                relations=_split_csv_args(args.relation),
            )
        except ValueError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        if args.format == "json":
            write_text(
                None,
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2 if args.pretty else None,
                    separators=None if args.pretty else (",", ":"),
                )
                + "\n",
            )
        elif args.format == "jsonl":
            write_text(
                None,
                json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n",
            )
        elif result["path"]:
            step_word = "step" if result["length"] == 1 else "steps"
            write_text(
                None,
                "Critical path (%d %s): %s\n"
                % (result["length"], step_word, " -> ".join(result["path"])),
            )
            if result["estimate_sum"] is not None:
                write_text(None, "estimate_sum=%s\n" % result["estimate_sum"])
        else:
            write_text(None, "(no items participate in the dependency graph)\n")
        _print_warnings(diagnostics)
        return 0

    if path_ids:
        if args.item_id or args.chain or topo or crit:
            raise ValueError(
                "--path cannot be combined with --id, --chain, --topo, or "
                "--critical-path."
            )
        if args.direction != "both":
            raise ValueError("--direction is only valid with --id, not --path.")
        if args.format in ("mermaid", "dot"):
            raise ValueError("--path supports text, json, or jsonl output.")
        from_id, to_id = path_ids
        hops = shortest_path(
            items,
            key=key,
            from_id=from_id,
            to_id=to_id,
            relations=_split_csv_args(args.relation),
        )
        if args.format == "json":
            write_text(
                None,
                json.dumps(
                    {"from": from_id, "to": to_id, "path": hops},
                    ensure_ascii=False,
                    indent=2 if args.pretty else None,
                    separators=None if args.pretty else (",", ":"),
                )
                + "\n",
            )
        elif args.format == "jsonl":
            output = "\n".join(
                json.dumps(hop, ensure_ascii=False, separators=(",", ":"))
                for hop in (hops or [])
            )
            if output:
                output += "\n"
            write_text(None, output)
        elif hops is None:
            write_text(None, "No path found between %s and %s.\n" % (from_id, to_id))
        else:
            write_text(None, "%s\n" % hops[0]["id"])
            for hop in hops[1:]:
                write_text(
                    None,
                    "  -> %s (%s, %s)\n"
                    % (hop["id"], hop["relation"], hop["direction"]),
                )
        _print_warnings(diagnostics)
        return 0

    if getattr(args, "chain", None):
        if args.item_id:
            raise ValueError("Use either --chain or --id, not both.")
        if args.direction != "both":
            raise ValueError("--direction is only valid with --id, not --chain.")
        if args.relation:
            raise ValueError("--relation is only valid for link records, not --chain.")
        if args.format in ("mermaid", "dot"):
            raise ValueError("--chain supports text, json, or jsonl output.")
        chains = dependency_chain_records(items, key=key, root_id=args.chain)
        if args.format == "json":
            write_text(
                None,
                json.dumps(
                    chains,
                    ensure_ascii=False,
                    indent=2 if args.pretty else None,
                    separators=None if args.pretty else (",", ":"),
                )
                + "\n",
            )
        elif args.format == "jsonl":
            output = "\n".join(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                for record in chains
            )
            if output:
                output += "\n"
            write_text(None, output)
        else:
            write_text(None, format_dependency_chain(chains))
        _print_warnings(diagnostics)
        return 0

    records = link_records(
        items,
        key=key,
        focus_id=args.item_id,
        direction=args.direction,
        relations=_split_csv_args(args.relation),
    )

    if args.format == "json":
        write_text(None, links_to_json(records, pretty=args.pretty) + "\n")
    elif args.format == "jsonl":
        output = links_to_jsonl(records)
        if output:
            output += "\n"
        write_text(None, output)
    elif args.format == "mermaid":
        write_text(None, links_to_mermaid(records))
    elif args.format == "dot":
        write_text(None, links_to_dot(records))
    else:
        write_text(None, format_link_table(records))

    _print_warnings(diagnostics)
    return 0


def command_sources(args):
    key = args.key or id_key_from_config(_config(args))
    normalized = _normalize_paths(args.paths, _config(args))
    file_directives = OrderedDict()
    for path in normalized:
        source = "stdin" if path == "-" else path
        text = read_text(path)
        file_directives[source] = parse_directives(text)
    records, diagnostics = source_ownership_records(args.paths, _config(args), key)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1

    if args.missing_id:
        records = [record for record in records if not record.get("id")]

    if args.format == "json":
        payload = OrderedDict([("items", records), ("directives", file_directives)])
        output = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        output = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        if output:
            output += "\n"
        write_text(None, output)
    else:
        lines = []
        for source, directives in file_directives.items():
            if directives:
                lines.append("Directives (%s):" % source)
                for k, v in directives.items():
                    lines.append("  #! %s: %s" % (k, v))
        if lines:
            write_text(None, "\n".join(lines) + "\n")
        write_text(None, format_source_ownership_table(records, key))

    _print_warnings(diagnostics)
    return 0


def _split_csv_args(values):
    result = []
    for raw in values or []:
        for value in str(raw).split(","):
            value = value.strip()
            if value:
                result.append(value)
    return result


def command_ids_assign(args):
    key = args.key or id_key_from_config(_config(args))
    records = assign_missing_ids(
        args.paths,
        _config(args),
        key,
        args.dry_run,
        args.backup,
        prefix=args.prefix,
    )

    if args.format == "json":
        output = json.dumps(
            records,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
        write_text(None, output + "\n")
    elif args.format == "jsonl":
        output = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        if output:
            output += "\n"
        write_text(None, output)
    else:
        write_text(None, format_id_assignments(records, args.dry_run))
    return 0


def command_to_json(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    if getattr(args, "occurrences", False):
        records = _occurrence_export_records(items, args)
        output = agenda_records_to_json(records, pretty=args.pretty)
    else:
        items = _filter_items_from_args(items, args)
        output = encode_conversion_items(items, "json", pretty=args.pretty).rstrip("\n")
    write_text(args.output, output + "\n")
    _print_warnings(diagnostics)
    return 0


def command_to_jsonl(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    if getattr(args, "occurrences", False):
        records = _occurrence_export_records(items, args)
        output = agenda_records_to_jsonl(records)
    else:
        items = _filter_items_from_args(items, args)
        output = encode_conversion_items(items, "jsonl").rstrip("\n")
    if output:
        output += "\n"
    write_text(args.output, output)
    _print_warnings(diagnostics)
    return 0


def command_to_csv(args):
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    if getattr(args, "occurrences", False):
        records = _occurrence_export_records(items, args)
        output = occurrence_records_to_csv(records)
    else:
        items = _filter_items_from_args(items, args)
        output = encode_conversion_items(items, "csv")
    write_text(args.output, output)
    _print_warnings(diagnostics)
    return 0


#: Export-format dispatch registry for `lifetxt export --format ...`.
#:
#: Each handler is an existing, independently-tested command function
#: (command_to_json, command_share, ...); this dict never contains a second
#: implementation of any serializer. New formats (native life, sqlite,
#: lifetxtz) register here rather than growing a second export framework --
#: see #688/#689/#691/#693. Populated at the bottom of this module (after
#: every handler function is defined) via register_export_format calls.
EXPORT_FORMAT_HANDLERS = {}


def register_export_format(name, handler):
    """Register an additional `lifetxt export --format NAME` handler.

    `handler(args) -> int` follows the same contract as every existing
    export command function. Called by native_codec/sqlite_codec/
    lifetxtz_codec at import time so `lifetxt export` never needs to know
    about a new format's implementation module directly.
    """
    EXPORT_FORMAT_HANDLERS[name] = handler


def command_export(args):
    handler = EXPORT_FORMAT_HANDLERS.get(args.format)
    if handler is None:
        raise ValueError(
            "Unsupported export format: %r. Supported: %s"
            % (args.format, ", ".join(sorted(EXPORT_FORMAT_HANDLERS)))
        )
    return handler(args)


def command_convert(args):
    """Thin file/stdin adapter over :mod:`lifetxt.conversion`."""
    if args.capabilities:
        write_text(
            args.output,
            json.dumps(
                conversion_capabilities(), ensure_ascii=False, separators=(",", ":")
            )
            + "\n",
        )
        return 0
    if not args.source_format or not args.target_format:
        raise ValueError(
            "convert requires --from FORMAT and --to FORMAT. "
            "Use --capabilities to inspect supported pairs."
        )
    ensure_supported_conversion_pair(args.source_format, args.target_format)

    items = []
    diagnostics = []
    for path in _normalize_paths(args.paths):
        decoded, path_diagnostics = decode_conversion_text(
            args.source_format,
            read_text(path),
            source_name="stdin" if path == "-" else os.path.abspath(path),
            id_key=id_key_from_config(_config(args)),
        )
        items.extend(decoded)
        diagnostics.extend(path_diagnostics)
    output = encode_conversion_items(
        items,
        args.target_format,
        pretty=args.pretty,
        canonical=args.canonical,
        id_key=id_key_from_config(_config(args)),
        calendar_name=args.calendar_name,
    )
    write_text(args.output, output)
    _print_warnings(diagnostics)
    return 0


def _export_sqlite(args):
    """`lifetxt export --format sqlite` handler (#691).

    Reuses the item loading/filtering path every other export format shares
    and delegates the actual database construction to
    lifetxt.sqlite_codec.export_sqlite(), which implements the
    lifetxt-sqlite-v1 contract frozen by #690.
    """
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    items = _filter_items_from_args(items, args)
    if not args.output:
        raise ValueError(
            "--format sqlite requires -o/--output: SQLite is a binary "
            "format and cannot be written to stdout."
        )
    id_key = id_key_from_config(_config(args))
    sqlite_codec.export_sqlite(items, args.output, key=id_key)
    _print_warnings(diagnostics)
    return 0


def _import_sqlite_preset(path, args):
    """`import --preset sqlite` handler (#691), registered into
    IMPORT_PRESET_HANDLERS below."""
    return sqlite_codec.import_sqlite(path)


def _export_lifetxtz(args):
    """`lifetxt export --format lifetxtz` handler (#693).

    Reuses the item loading/filtering path every other export format
    shares and delegates archive construction to
    lifetxt.lifetxtz_codec.export_lifetxtz(), which implements the
    lifetxtz-v1 contract frozen by #692.
    """
    items, diagnostics = _parse_or_exit(args.paths, _config(args))
    items = _filter_items_from_args(items, args)
    if not args.output:
        raise ValueError(
            "--format lifetxtz requires -o/--output: .lifetxtz is a binary "
            "format and cannot be written to stdout."
        )
    id_key = id_key_from_config(_config(args))
    lifetxtz_codec.export_lifetxtz(items, args.output, key=id_key)
    _print_warnings(diagnostics)
    return 0


def _import_lifetxtz_preset(path, args):
    """`import --preset lifetxtz` handler (#693), registered into
    IMPORT_PRESET_HANDLERS below. Verifies archive integrity, then parses
    and validates the recovered native payload through the authoritative
    parser before any item is returned -- refusing (SystemExit(1), the
    same convention _parse_or_exit already uses) before any write.
    """
    payload_text = lifetxtz_codec.import_lifetxtz(path)
    id_key = id_key_from_config(_config(args))
    items, diagnostics = parse_text(
        payload_text, id_key=id_key, check_ids=False, check_references=False
    )
    if _has_error(diagnostics):
        _print_diagnostics(dia…65498 tokens truncated…e_text(None, "Removed %s from %s\n" % (args.path, target))
    _print_config_write_notes(report)
    return 0


def command_config_check(args):
    from .config_validation import validation_report
    from .config_writer import rejected_candidates

    config = _config(args)
    report = validation_report(config)
    # Retained candidates are never removed automatically, so report them here
    # rather than let them sit unnoticed beside the configuration.
    retained = rejected_candidates(config.get("_path"))
    if getattr(args, "json", False):
        report = OrderedDict(report)
        report["rejected_candidates"] = retained
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0 if report["ok"] else 1
    status = "OK" if report["ok"] else "ERRORS"
    write_text(
        None,
        "config check: %s (config_version=%s, writable=%s)\n"
        % (status, report["config_version"], report["writable"]),
    )
    for candidate in retained:
        write_text(
            None,
            "  [NOTE] refused write retained at %s (review, then delete)\n" % candidate,
        )
    for row in report["diagnostics"]:
        location = (" @ %s" % row["path"]) if row.get("path") else ""
        write_text(
            None,
            "  [%s] %s: %s%s\n"
            % (row["severity"].upper(), row["code"], row["message"], location),
        )
    return 0 if report["ok"] else 1


def command_config_migrate(args):
    from .config_migration import migrate_config

    config = _config(args)
    source = _config_without_runtime(
        config, getattr(args, "_workspace_injected_keys", None)
    )
    migrated, changes = migrate_config(source)
    if not changes:
        write_text(None, "Configuration is already current; no changes.\n")
        return 0
    write_text(None, "Planned changes:\n")
    for change in changes:
        write_text(None, "  - %s\n" % change)
    if getattr(args, "dry_run", False):
        write_text(None, "(dry run: nothing written)\n")
        return 0
    target = args.output or config.get("_path")
    if not target:
        raise ValueError(
            "No config file to write. Run config init first or pass --output."
        )
    report, code = _commit_config(args, config, target, migrated)
    if code:
        return code
    write_text(None, "Wrote migrated config to %s\n" % target)
    _print_config_write_notes(report)
    return 0


def command_workspace_doctor(args):
    from .workspace import workspace_doctor

    report = workspace_doctor(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0 if report["ok"] else 1
    write_text(
        None,
        "workspace doctor: %s (%d workspace(s), default=%s)\n"
        % (
            "OK" if report["ok"] else "ERRORS",
            report["workspace_count"],
            report["default_workspace"],
        ),
    )
    for entry in report["workspaces"]:
        marker = "*" if entry["default"] else " "
        write_text(
            None,
            "%s %s: %s (%d file(s)) -> %s\n"
            % (
                marker,
                entry["name"],
                "OK" if entry["ok"] else "ERRORS",
                entry["input_count"],
                entry["write_file"] or "(none)",
            ),
        )
        for row in entry["diagnostics"]:
            write_text(
                None,
                "    [%s] %s: %s\n"
                % (row["severity"].upper(), row["code"], row["message"]),
            )
    for shared in report["shared_files"]:
        write_text(
            None,
            "shared: %s (%s)\n" % (shared["path"], ", ".join(shared["workspaces"])),
        )
    return 0 if report["ok"] else 1


def _project_items(args):
    paths = _normalize_paths(
        getattr(args, "paths", None), _config(args), stdin_when_empty=False
    ) or ["life.txt"]
    items, _diagnostics = _parse_or_exit(paths, _config(args))
    return items


def _project_today():
    try:
        return timezone_today()
    except Exception:
        return None


def command_project_list(args):
    from .projects import project_list

    rows = project_list(
        _project_items(args),
        _config(args),
        _project_today(),
        include_archived=getattr(args, "all", False),
    )
    if getattr(args, "area", None):
        rows = [r for r in rows if r["area"] == args.area]
    if getattr(args, "owner", None):
        rows = [r for r in rows if r["owner"] == args.owner]
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No projects found.\n")
        return 0
    for row in rows:
        pct = (
            "%.0f%%" % row["progress_percent"]
            if row["progress_percent"] is not None
            else "n/a"
        )
        write_text(
            None,
            "[%s] %-20s %s  %d/%d done (%s)  open=%d overdue=%d blocked=%d risks=%d\n"
            % (
                row["health"][0].upper(),
                row["name"],
                row["state"],
                row["task_done"],
                row["task_total"],
                pct,
                row["open_count"],
                row["overdue_count"],
                row["blocked_count"],
                row["open_risk_count"],
            ),
        )
    return 0


def command_project_show(args):
    from .projects import project_hub

    try:
        hub = project_hub(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(hub, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "%s (%s)\n" % (hub["display_name"], hub["name"]))
    write_text(
        None,
        "  state=%s owner=%s area=%s due=%s\n"
        % (hub["state"], hub["owner"], hub["area"], hub["due"]),
    )
    prog = hub["progress"]
    pct = "%.0f%%" % prog["percent"] if prog["percent"] is not None else "n/a"
    write_text(
        None,
        "  progress: %d/%d (%s)  health=%s (%s)\n"
        % (
            prog["done"],
            prog["total"],
            pct,
            hub["health"]["label"],
            "; ".join(hub["health"]["reasons"]),
        ),
    )
    _project_section("open tasks", hub["open_tasks"])
    _project_section("overdue", hub["overdue_tasks"])
    _project_section("blocked", hub["blocked_tasks"])
    _project_section("milestones", hub["milestones"])
    _project_section("risks", hub["risks"], risk=True)
    _project_section("decisions", hub["decisions"])
    _project_section("meetings", hub["meetings"])
    for note in hub["health"]["limitations"]:
        write_text(None, "  note: %s\n" % note)
    return 0


def _project_section(label, rows, risk=False):
    if not rows:
        return
    write_text(None, "  %s (%d):\n" % (label, len(rows)))
    for row in rows:
        if risk:
            write_text(
                None,
                "    - [%s/%s] %s\n" % (row["severity"], row["state"], row["title"]),
            )
        else:
            extra = ""
            if row.get("due"):
                extra = " due:%s" % row["due"]
            elif row.get("on"):
                extra = " on:%s" % row["on"]
            write_text(None, "    - %s%s\n" % (row["title"], extra))


def command_project_health(args):
    from .projects import alias_map, collect_projects, compute_health

    config = _config(args)
    projects = collect_projects(_project_items(args), config, _project_today())
    if getattr(args, "all", False) or not getattr(args, "name", None):
        names = list(projects.keys())
    else:
        canonical = alias_map(config).get(args.name, args.name)
        if canonical not in projects:
            sys.stderr.write("ERROR: Unknown project %r\n" % args.name)
            return 1
        names = [canonical]
    reports = OrderedDict()
    for name in names:
        reports[name] = compute_health(projects[name], _project_today())
    if getattr(args, "json", False):
        write_text(None, json.dumps(reports, ensure_ascii=False, indent=2) + "\n")
        return 0
    for name, health in reports.items():
        write_text(
            None,
            "%s: %s (%s)\n" % (name, health["label"], "; ".join(health["reasons"])),
        )
        write_text(None, "  formula: %s\n" % health["formula"])
        for note in health["limitations"]:
            write_text(None, "  note: %s\n" % note)
    return 0


def command_project_timeline(args):
    from .projects import project_timeline

    try:
        rows = project_timeline(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    for row in rows:
        item = row["item"]
        write_text(
            None, "%s  %s %s\n" % (row["when"], item.get("kind", ""), item["title"])
        )
    return 0


def command_project_workload(args):
    from .projects import project_workload

    try:
        rows = project_workload(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    for row in rows:
        write_text(
            None,
            "%-20s open=%d done=%d overdue=%d\n"
            % (row["assignee"], row["open"], row["done"], row["overdue"]),
        )
    return 0


def command_project_risks(args):
    from .projects import project_risks

    try:
        rows = project_risks(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No risks recorded.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "[%s/%s] %s (owner=%s)\n"
            % (row["severity"], row["state"], row["title"], row["owner"]),
        )
    return 0


def _project_write_target(args):
    config = _config(args)
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        if paths:
            target = paths[0]
    if not target:
        target = "life.txt"
    return target


def command_project_new(args):
    from .projects import build_project_record_line

    line = build_project_record_line(
        args.name,
        owner=args.owner,
        area=args.area,
        state=args.state,
        due=args.due,
        start=args.start,
        visibility=args.visibility,
    )
    return _emit_project_line(args, line)


def command_project_add(args):
    from .projects import (
        build_decision_line,
        build_meeting_line,
        build_milestone_line,
        build_risk_line,
    )

    if args.record_type == "milestone":
        line = build_milestone_line(
            args.project, args.title, due=args.due, owner=args.owner
        )
    elif args.record_type == "risk":
        line = build_risk_line(
            args.project,
            args.title,
            severity=args.severity,
            owner=args.owner,
            state=args.state,
        )
    elif args.record_type == "decision":
        line = build_decision_line(
            args.project, args.title, on=args.on, owner=args.owner
        )
    else:
        line = build_meeting_line(args.project, args.title, on=args.on, at=args.at)
    return _emit_project_line(args, line)


def command_project_archive(args):
    """Move one project's records to the workspace's configured archive source.

    Reuses ``command_archive``'s candidate filtering, external-reference
    warnings, and transactional multi-file write unchanged; this only adds a
    ``project:`` filter and workspace-based source/destination resolution so
    the write target is never outside the resolved source manifest.

    ``--emit-plan``/``--apply-plan`` (#254/#255) add an optional reviewable
    ``archive-plan-v1`` document between selection and write; see
    :mod:`lifetxt.archive_plan_v1`. Neither flag changes behavior when
    omitted.
    """
    emit_plan_path = getattr(args, "emit_plan", None)
    apply_plan_path = getattr(args, "apply_plan", None)
    if emit_plan_path and apply_plan_path:
        raise ValueError("--emit-plan and --apply-plan are mutually exclusive.")
    if emit_plan_path and not getattr(args, "dry_run", False):
        raise ValueError("--emit-plan requires --dry-run in this version.")

    if apply_plan_path:
        if getattr(args, "revision", None):
            raise ValueError(
                "--apply-plan and --revision are mutually exclusive: a plan "
                "already freezes the exact revision set to apply."
            )
        if getattr(args, "paths", None):
            raise ValueError(
                "--apply-plan and explicit source paths are mutually "
                "exclusive: the plan already freezes its source file list."
            )
        if getattr(args, "dest", None):
            raise ValueError(
                "--apply-plan and --dest are mutually exclusive: the plan "
                "already freezes its destination path."
            )
        config = _config(args)
        return _project_archive_apply_plan(args, config, apply_plan_path)

    config = _config(args)
    from .workspace import resolve_workspace, workspace_resolution_active

    workspace_name = getattr(args, "workspace", None)
    archive_paths = []
    scan_paths = None
    if workspace_resolution_active(config, workspace_name):
        resolution = resolve_workspace(config, workspace_name)
        archive_paths = resolution["archive_paths"]
        # Never scan the archive destination itself as a source: it would
        # self-include (command_archive rejects that) or, worse, be read
        # before it exists.
        archive_path_set = {os.path.normcase(path) for path in archive_paths}
        scan_paths = [
            path
            for path in resolution["input_paths"]
            if os.path.normcase(path) not in archive_path_set
        ]

    dest = getattr(args, "dest", None)
    if not dest:
        if not archive_paths:
            raise ValueError(
                "No archive-role workspace source is configured. Add a source "
                "with role: archive to the active workspace, or pass --dest "
                "explicitly."
            )
        dest = archive_paths[0]

    explicit_paths = getattr(args, "paths", None)
    if explicit_paths:
        paths = _normalize_paths(explicit_paths, config, stdin_when_empty=False)
    elif scan_paths:
        paths = scan_paths
    else:
        paths = _normalize_paths(None, config, stdin_when_empty=False)
    if not paths:
        raise ValueError("No source files specified.")

    archive_args = argparse.Namespace(
        paths=paths,
        dest=dest,
        revision=getattr(args, "revision", None) or [],
        statuses=getattr(args, "statuses", None),
        before=getattr(args, "before", None),
        max_items=getattr(args, "max_items", None),
        dry_run=getattr(args, "dry_run", False),
        copy=getattr(args, "copy", False),
        yes=getattr(args, "yes", False),
        orphan_children=getattr(args, "orphan_children", "block"),
        preserve_structure=getattr(args, "preserve_structure", False),
        block_on_external_refs=getattr(args, "block_on_external_refs", False),
        project_filter=args.name,
        config=getattr(args, "config", None),
        config_data=config,
        workspace=workspace_name,
    )
    if emit_plan_path:
        _project_archive_emit_plan(archive_args, config, emit_plan_path)
    return command_archive(archive_args)


def _archive_plan_blocking_reason(selection, args):
    """Why a plan cannot be emitted for the current selection, or ``None``."""
    if not selection.candidates:
        return "no items match the archive criteria"
    if selection.orphan_blocked:
        return "open children block the selection (see --orphan-children)"
    if selection.external_refs and getattr(args, "block_on_external_refs", False):
        return "blocked by external reference(s) to archived items"
    return None


def _project_archive_emit_plan(archive_args, config, emit_plan_path):
    """Write an ``archive-plan-v1`` document for the current selection.

    Purely additive: computed from the same ``archive_args``/``selection``
    ``command_archive`` is about to print from, so it never changes the
    existing dry-run text output. Nothing is written when the selection
    would not itself proceed (no candidates, orphan-blocked, or blocked by
    external references), matching "no other change" for --emit-plan.
    """
    from . import archive_plan_v1
    from .config_writer import config_revision as _config_revision_of
    from .mutation import read_text_snapshot
    from .timezone_policy import utcnow
    from .workspace import active_workspace_name

    selection = _archive_select(archive_args, config)
    reason = _archive_plan_blocking_reason(selection, archive_args)
    if reason:
        sys.stderr.write("No archive plan written: %s.\n" % reason)
        return

    dest_abs = os.path.abspath(archive_args.dest)
    dest_snapshot = read_text_snapshot(dest_abs, allow_missing=True)
    config_path = config.get("_path") if isinstance(config, dict) else None
    config_rev = _config_revision_of(config_path)
    workspace_name = active_workspace_name(config) or getattr(
        archive_args, "workspace", None
    )

    sources = [
        (path, selection.file_snapshots[path].content_hash) for path in selection.paths
    ]
    parameters = {
        "statuses": list(selection.statuses),
        "before": archive_args.before,
        "max_items": archive_args.max_items,
        "mode": selection.mode,
        "orphan_children": selection.orphan_mode,
        "preserve_structure": bool(getattr(archive_args, "preserve_structure", False)),
        "block_on_external_refs": bool(
            getattr(archive_args, "block_on_external_refs", False)
        ),
    }
    now_iso = utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    plan = archive_plan_v1.build_plan(
        project=archive_args.project_filter,
        workspace_name=workspace_name,
        config_path=config_path,
        config_revision=config_rev,
        sources=sources,
        destination_path=dest_abs,
        destination_revision=dest_snapshot.content_hash,
        selected_item_ids=selection.candidate_ids,
        external_references=archive_plan_v1.external_reference_rows(
            selection.external_refs
        ),
        parameters=parameters,
        now_iso=now_iso,
    )
    archive_plan_v1.write_plan(emit_plan_path, plan)
    sys.stdout.write("Archive plan written to %s.\n" % emit_plan_path)


def _project_archive_apply_plan(args, config, apply_plan_path):
    """Verify an ``archive-plan-v1`` document against current state, then
    delegate to :func:`command_archive` using the plan's frozen parameters.

    Every verification step below runs, and must pass, before any write --
    matching the precede-side-effects discipline ``archive_safety_v3.py``
    already established for the ad-hoc ``--revision`` path.
    """
    from . import archive_plan_v1
    from .config_writer import config_revision as _config_revision_of
    from .mutation import read_text_snapshot
    from .transaction_journal import journal_directory

    plan = archive_plan_v1.load_plan(apply_plan_path)

    # 1. plan_version supported.
    archive_plan_v1.verify_plan_version(plan)

    # 2. Self-consistency: the plan file must match its own recorded hash
    #    (catches corruption/hand-edits, not a deliberate forgery -- see
    #    verify_plan_hash's docstring).
    archive_plan_v1.verify_plan_hash(plan)

    # 3. Current source/destination revisions must match the plan exactly.
    current_source_revisions = {}
    for row in plan.get("sources", []):
        path = row.get("path")
        snapshot = read_text_snapshot(path, allow_missing=True)
        current_source_revisions[path] = snapshot.content_hash

    dest_info = plan.get("destination") or {}
    dest_path = dest_info.get("path")
    current_dest_revision = None
    if dest_path:
        current_dest_revision = read_text_snapshot(
            dest_path, allow_missing=True
        ).content_hash

    archive_plan_v1.verify_revisions_unchanged(
        plan, current_source_revisions, current_dest_revision
    )

    # 4. Current workspace/config revision must match the plan exactly.
    config_path = config.get("_path") if isinstance(config, dict) else None
    current_config_revision = _config_revision_of(config_path)
    archive_plan_v1.verify_workspace_revision_unchanged(plan, current_config_revision)

    # 5. Candidate selection re-derived from current state must match the
    # plan's frozen item-ID list exactly, using the plan's own frozen
    # parameters rather than any current CLI flags.
    parameters = plan.get("parameters") or {}
    plan_paths = [row["path"] for row in plan.get("sources", [])]
    reselect_args = argparse.Namespace(
        paths=plan_paths,
        dest=dest_path,
        revision=[],
        statuses=parameters.get("statuses"),
        before=parameters.get("before"),
        max_items=parameters.get("max_items"),
        dry_run=True,
        copy=parameters.get("mode") == "copy",
        yes=True,
        orphan_children=parameters.get("orphan_children", "block"),
        preserve_structure=bool(parameters.get("preserve_structure", False)),
        block_on_external_refs=bool(parameters.get("block_on_external_refs", False)),
        project_filter=plan.get("project"),
        config=getattr(args, "config", None),
        config_data=config,
        workspace=(plan.get("workspace") or {}).get("name"),
    )
    selection = _archive_select(reselect_args, config)
    if not selection.candidates:
        raise ValueError(
            "Archive plan is stale: no items currently match the plan's "
            "archive criteria. Re-run --dry-run --emit-plan to produce a "
            "current plan."
        )
    if selection.orphan_blocked:
        raise ValueError(
            "Archive plan is stale: open children now block the selection. "
            "Re-run --dry-run --emit-plan to produce a current plan."
        )
    archive_plan_v1.verify_selection_unchanged(plan, selection.candidate_ids)

    # 6. Recovery evidence (transaction journal directory) must be reachable.
    journal_dir = journal_directory(config, writable_path=dest_path)
    archive_plan_v1.verify_recovery_evidence_reachable(journal_dir)

    reserved_transaction_id = plan.get("reserved_transaction_id")

    if not getattr(args, "yes", False):
        sys.stdout.write(
            "Archive plan verified against current state "
            "(reserved_transaction_id=%s). No changes made.\n"
            "Re-run the same command with --yes to apply it.\n"
            % reserved_transaction_id
        )
        return 0

    revision_tokens = [
        "%s=%s" % (path, revision)
        for path, revision in current_source_revisions.items()
    ]
    if dest_path is not None:
        revision_tokens.append("%s=%s" % (dest_path, current_dest_revision))

    execute_args = argparse.Namespace(
        paths=plan_paths,
        dest=dest_path,
        revision=revision_tokens,
        statuses=parameters.get("statuses"),
        before=parameters.get("before"),
        max_items=parameters.get("max_items"),
        dry_run=False,
        copy=parameters.get("mode") == "copy",
        yes=True,
        orphan_children=parameters.get("orphan_children", "block"),
        preserve_structure=bool(parameters.get("preserve_structure", False)),
        block_on_external_refs=bool(parameters.get("block_on_external_refs", False)),
        project_filter=plan.get("project"),
        config=getattr(args, "config", None),
        config_data=config,
        workspace=(plan.get("workspace") or {}).get("name"),
    )
    sys.stdout.write(
        "Applying archive plan (reserved_transaction_id=%s).\n"
        % reserved_transaction_id
    )
    return command_archive(execute_args)


def _emit_project_line(args, line):
    if getattr(args, "dry_run", False):
        write_text(None, line + "\n")
        return 0
    target = _project_write_target(args)
    _ensure_writable_path(target, _config(args), "project")
    append_line(target, line)
    write_text(None, "Appended to %s:\n  %s\n" % (target, line))
    return 0


def command_portfolio(args):
    from .projects import portfolio

    report = portfolio(
        _project_items(args),
        _config(args),
        _project_today(),
        include_archived=getattr(args, "all", False),
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "Portfolio (%d project(s)):\n" % report["count"])
    for row in report["projects"]:
        pct = (
            "%.0f%%" % row["progress_percent"]
            if row["progress_percent"] is not None
            else "n/a"
        )
        write_text(
            None,
            "[%s] %-20s %-8s progress=%s open=%d overdue=%d blocked=%d risk=%s\n"
            % (
                row["health"][0].upper(),
                row["name"],
                row["state"],
                pct,
                row["open_count"],
                row["overdue_count"],
                row["blocked_count"],
                row["top_risk_severity"] or "-",
            ),
        )
    write_text(
        None,
        "legend: progress=%s; health=%s\n"
        % (report["legend"]["progress"], report["legend"]["health"]),
    )
    return 0


def command_today(args):
    from .command_center import command_center, scoped_items

    config = _config(args)
    items = _project_items(args)
    saved_view = getattr(args, "saved_view", None)
    area = getattr(args, "area", None)
    if saved_view or area:
        try:
            items = scoped_items(items, config, saved_view=saved_view, area=area)
        except ValueError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1

    report = command_center(
        items,
        config,
        _project_today(),
        horizon_days=getattr(args, "horizon", 3),
        person=getattr(args, "person", None),
        mode=getattr(args, "mode", "today"),
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    _render_today_text(report, saved_view=saved_view, area=area)
    return 0


def _progress_display(raw):
    """Render a ``progress:`` value for human-readable listings (#649).

    Percentages are shown as-is; fractions are shown as ``m/n`` with a
    derived percentage alongside. Returns ``""`` when ``raw`` is absent, so
    a record with no ``progress:`` detail shows nothing extra. An
    unparseable value (which ``check`` would separately flag as W230) is
    still shown as-is rather than silently hidden.
    """
    if not raw:
        return ""
    from .progress import ProgressValueError, parse_progress

    try:
        parsed = parse_progress(raw)
    except ProgressValueError:
        return raw
    if parsed.kind == "fraction":
        return "%s (%d%%)" % (raw, int(round(parsed.percent)))
    return raw


def _relative_date_suffix(value, reference=None):
    # A caller with no already-resolved reference date (report["reference_date"]
    # etc.) still gets the workspace-aware "today" (#142) here, rather than
    # falling through to relative_time's own bare system-date default, which
    # would drift from every other surface when the configured workspace
    # timezone differs from the host's.
    relative = relative_time(value, today=reference or timezone_today())
    return " (%s)" % relative if relative else ""


def _progress_suffix(row):
    display = _progress_display(row.get("progress"))
    return " progress:%s" % display if display else ""


def _render_today_text(report, saved_view=None, area=None):
    """Render the daily command center as the NOW/ATTENTION/TODAY/NEXT
    ACTIONS/BLOCKED/HABITS/INBOX hub structure lifetxt today's documented
    information architecture describes (#627).

    Every row still comes from ``report`` (the shared
    :func:`lifetxt.command_center.command_center` aggregation) unchanged;
    this function only decides where to print each row and skips a row
    already printed under an earlier heading, so the same record is not
    presented twice.
    """
    counts = report["counts"]
    mode = report["mode"]
    mode_label = _t("today.mode.%s" % mode) or mode.capitalize()
    if report["reference_date"]:
        header = _t("today.brief_for", mode=mode_label, date=report["reference_date"])
    else:
        header = _t("today.brief", mode=mode_label)
    if saved_view:
        header += " (saved view: %s)" % saved_view
    elif area:
        header += " (area: %s)" % area
    write_text(None, header + "\n")
    if not report["safety"]["ok"]:
        write_text(
            None, _t("today.config_error", n=report["safety"]["config_errors"]) + "\n"
        )

    shown = set()

    def row_key(row):
        return (row.get("source"), row.get("line"))

    def unshown(rows):
        fresh = []
        for row in rows or []:
            key = row_key(row)
            if key in shown:
                continue
            shown.add(key)
            fresh.append(row)
        return fresh

    now_rows = report.get("now") or []
    if now_rows:
        write_text(None, "\n%s\n" % _t("today.now"))
        for row in now_rows:
            since = " since %s" % row["since"] if row.get("since") else ""
            write_text(
                None,
                "  %s: %s%s\n"
                % (row.get("person") or "self", row.get("state") or "", since),
            )

    attention_rows = unshown(report.get("overdue")) + unshown(report.get("due_today"))
    has_attention = bool(
        attention_rows or report["ticket_attention"] or report["project_attention"]
    )
    if has_attention:
        write_text(None, "\n%s\n" % _t("today.attention"))
        for row in attention_rows:
            due = (
                " due:%s%s"
                % (
                    row["due"],
                    _relative_date_suffix(row["due"], report["reference_date"]),
                )
                if row.get("due")
                else ""
            )
            reason = " (%s)" % row["reason"] if row.get("reason") else ""
            progress = _progress_suffix(row)
            write_text(
                None,
                "  %s %s%s%s%s\n"
                % (row["status"], row["title"], due, progress, reason),
            )
        if report["project_attention"]:
            write_text(
                None,
                _t("today.projects_attention", n=len(report["project_attention"]))
                + "\n",
            )
            for row in report["project_attention"]:
                write_text(
                    None,
                    "    [%s] %s: %s\n"
                    % (
                        row["health"][0].upper(),
                        row["name"],
                        "; ".join(row["reasons"]),
                    ),
                )
        if report["ticket_attention"]:
            write_text(
                None,
                _t("today.tickets_attention", n=len(report["ticket_attention"])) + "\n",
            )
            for row in report["ticket_attention"]:
                write_text(
                    None,
                    "    %s %s: %s\n"
                    % (row["status"], row["title"], ", ".join(row["reasons"])),
                )

    today_rows = report.get("today_events") or []
    if today_rows:
        write_text(None, "\n%s\n" % _t("today.today_heading"))
        for row in today_rows:
            when = row.get("when") or ""
            write_text(None, "  %s %s\n" % (when, row.get("title") or ""))

    # Habit-kind actionable items get their own HABITS heading below rather
    # than doubling up in NEXT ACTIONS; next_action_items() itself is not
    # touched, only which of its rows this renderer prints where.
    next_rows = unshown(
        [row for row in (report.get("next_actions") or []) if row.get("kind") != "H"]
    )
    write_text(None, "\n%s\n" % _t("today.next_actions"))
    if next_rows:
        for row in next_rows:
            project = " @%s" % row["project"] if row.get("project") else ""
            due = (
                " due:%s%s"
                % (
                    row["due"],
                    _relative_date_suffix(row["due"], report["reference_date"]),
                )
                if row.get("due")
                else ""
            )
            progress = _progress_suffix(row)
            write_text(
                None,
                "  %s %s%s%s%s\n"
                % (row["status"], row["title"], project, due, progress),
            )
    elif report.get("next_actions"):
        write_text(None, _t("today.next_actions_already_listed") + "\n")
    else:
        write_text(None, _t("today.next_actions_none") + "\n")

    blocked_rows = report.get("blocked") or []
    waiting_rows = report.get("waiting") or []
    if blocked_rows or waiting_rows:
        write_text(None, "\n%s\n" % _t("today.blocked"))
        for row in blocked_rows:
            write_text(None, "  %s %s\n" % (row["status"], row["title"]))
        blocked_keys = set(row_key(row) for row in blocked_rows)
        for row in waiting_rows:
            if row_key(row) in blocked_keys:
                continue
            write_text(
                None,
                "  %s %s %s\n"
                % (_t("today.waiting_prefix"), row["status"], row["title"]),
            )

    habit_rows = report.get("habits") or []
    if habit_rows:
        write_text(None, "\n%s\n" % _t("today.habits"))
        for row in habit_rows:
            write_text(None, "  %s %s\n" % (row["status"], row["title"]))

    upcoming_rows = unshown(report.get("upcoming"))
    if upcoming_rows:
        write_text(None, "\n%s\n" % _t("today.upcoming", n=report["horizon_days"]))
        for row in upcoming_rows:
            due = (
                " due:%s%s"
                % (
                    row["due"],
                    _relative_date_suffix(row["due"], report["reference_date"]),
                )
                if row.get("due")
                else ""
            )
            progress = _progress_suffix(row)
            write_text(
                None, "  %s %s%s%s\n" % (row["status"], row["title"], due, progress)
            )

    inbox = report.get("inbox") or {}
    pending_count = inbox.get("pending_count", 0)
    messages = report.get("messages") or []
    captures = report.get("captures") or []
    if pending_count or messages or captures:
        write_text(None, "\n%s\n" % _t("today.inbox"))
        if pending_count:
            write_text(None, _t("today.inbox_pending", n=pending_count) + "\n")
        for row in messages:
            write_text(None, _t("today.inbox_message", title=row["title"]) + "\n")
        for row in captures:
            write_text(None, _t("today.inbox_capture", title=row["title"]) + "\n")

    if all(v == 0 for v in counts.values()):
        write_text(None, "\n%s\n" % _t("today.all_clear"))


def command_area_list(args):
    from .areas import area_list

    rows = area_list(_project_items(args), _config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No areas found.\n")
        return 0
    for row in rows:
        pct = (
            "%.0f%%" % row["progress_percent"]
            if row["progress_percent"] is not None
            else "n/a"
        )
        write_text(
            None,
            "%-16s %d/%d done (%s)  open=%d projects=%d\n"
            % (
                row["name"],
                row["task_done"],
                row["task_total"],
                pct,
                row["task_open"],
                row["project_count"],
            ),
        )
    return 0


def command_area_show(args):
    from .areas import area_show

    try:
        summary = area_show(_project_items(args), _config(args), args.name)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "%s\n" % summary["name"])
    pct = (
        "%.0f%%" % summary["progress_percent"]
        if summary["progress_percent"] is not None
        else "n/a"
    )
    write_text(
        None,
        "  tasks: %d/%d done (%s) open=%d\n"
        % (summary["task_done"], summary["task_total"], pct, summary["task_open"]),
    )
    if summary["projects"]:
        write_text(None, "  projects: %s\n" % ", ".join(summary["projects"]))
    for row in summary["open_items"]:
        write_text(None, "  - %s %s\n" % (row["status"], row["title"]))
    return 0


def command_backlinks(args):
    from .links import backlink_records

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    key = id_key_from_config(_config(args))
    records = backlink_records(items, args.id, key=key)
    if getattr(args, "json", False):
        write_text(None, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not records:
        write_text(None, "No items reference %s.\n" % args.id)
        return 0
    write_text(None, "Items referencing %s (%d):\n" % (args.id, len(records)))
    for row in records:
        write_text(
            None,
            "  %s <- %s (%s) %s\n"
            % (
                row["relation"],
                row["source_id"] or "(no id)",
                row["source_status"],
                row["source_title"],
            ),
        )
    return 0


def _emit_query_items(args, items, diagnostics=None):
    id_key = id_key_from_config(_config(args))
    fmt = getattr(args, "format", "life")
    if fmt == "json":
        write_text(
            args.output,
            items_to_json(items, pretty=getattr(args, "pretty", False)) + "\n",
        )
    elif fmt == "jsonl":
        output = items_to_jsonl(items)
        if output:
            output += "\n"
        write_text(args.output, output)
    elif fmt == "table":
        write_text(
            args.output, _format_filter_table(items, width=getattr(args, "width", 0))
        )
    else:
        write_text(
            args.output,
            _items_to_life_text(
                items, canonical=getattr(args, "canonical", False), key=id_key
            ),
        )
    for row in diagnostics or []:
        if row.get("severity") == "error":
            sys.stderr.write("ERROR: %s %s\n" % (row.get("code"), row.get("message")))
        else:
            sys.stderr.write("WARNING: %s %s\n" % (row.get("code"), row.get("message")))


def command_temporal(args):
    from .temporal_context import DEFAULT_STALE_DAYS, temporal_context
    from .web_read_service import find_item_by_id

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    key = id_key_from_config(_config(args))
    try:
        target = find_item_by_id(items, args.id, key=key)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if target is None:
        sys.stderr.write("ERROR: No item with id %r.\n" % args.id)
        return 1
    stale_after = getattr(args, "stale_after", None)
    context = temporal_context(
        items,
        target,
        _project_today(),
        key=key,
        window_days=getattr(args, "window", 7),
        limit=getattr(args, "limit", 20),
        stale_after_days=stale_after if stale_after is not None else DEFAULT_STALE_DAYS,
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(context, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "Temporal context for %s (%s):\n" % (args.id, target.title))
    if not context["facts"]:
        write_text(None, "  No overdue/due/staleness facts.\n")
    for fact in context["facts"]:
        detail = ", ".join(
            "%s=%s" % (k, v)
            for k, v in fact.items()
            if k not in ("rule", "source_field", "reference_time")
        )
        write_text(
            None, "  %s (%s): %s\n" % (fact["rule"], fact["source_field"], detail)
        )
    if not context["related"]:
        write_text(None, "  No related items within %sd.\n" % context["window_days"])
    else:
        write_text(
            None,
            "  Related within %sd (%d):\n"
            % (context["window_days"], len(context["related"])),
        )
        for edge in context["related"]:
            write_text(
                None,
                "    %s (%dd) %s %s\n"
                % (
                    edge["relation"],
                    edge["days"],
                    edge["target_id"] or "(no id)",
                    edge["target"]["title"],
                ),
            )
    return 0


def command_timeline(args):
    from .native_timeline import native_timeline
    from .lifecycle_analytics import lifecycle_analytics, lifecycle_summary
    from .timezone_policy import resolve_timezone_name

    config = _config(args)
    raw_paths = getattr(args, "paths", None)
    workspace_target = getattr(args, "id", None)
    # With the shared positional path convention, `timeline --workspace path`
    # is parsed as the optional id. Treat that sole token as an input path; an
    # explicit workspace target can still be written as `--workspace ID path`.
    if (
        getattr(args, "workspace_timeline", False)
        and not raw_paths
        and workspace_target
    ):
        raw_paths = [workspace_target]
        workspace_target = None
    if not getattr(args, "workspace_timeline", False) and not getattr(args, "id", None):
        sys.stderr.write(
            "ERROR: timeline requires an item ID or --workspace-timeline.\n"
        )
        return 1
    paths = _normalize_paths(raw_paths, config, stdin_when_empty=False) or ["life.txt"]
    items, _diagnostics = _parse_or_exit(paths, config)
    if getattr(args, "workspace_timeline", False):
        from .workspace_timeline import workspace_timeline

        try:
            result = workspace_timeline(
                items,
                id_key=id_key_from_config(config),
                limit=getattr(args, "limit", 100),
                since=getattr(args, "since", None),
                until=getattr(args, "until", None),
                event=getattr(args, "event", None),
                target_id=workspace_target,
                project=getattr(args, "project", None),
            )
        except ValueError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        if getattr(args, "json", False):
            write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            return 0
        write_text(None, "Workspace Life Timeline:\n")
        write_text(
            None,
            "  Coverage: complete:%s; events:%d/%d\n"
            % (
                str(result["complete"]).lower(),
                result["bounds"]["returned_events"],
                result["bounds"]["total_valid_events"],
            ),
        )
        for event in result["events"]:
            write_text(
                None,
                "  %s  %s  %s:%s  target:%s\n"
                % (
                    event["at"] or "(no time)",
                    event["event"],
                    event["record_kind"],
                    event["record_id"],
                    event["target_id"],
                ),
            )
        if result["limitations"]:
            write_text(None, "  Limitations: %s\n" % ", ".join(result["limitations"]))
        return 0

    def _window(value):
        if not value or str(value).count("..") != 1:
            raise ValueError("Timeline comparison windows must use START..END.")
        return tuple(str(value).split("..", 1))

    try:
        result = native_timeline(
            items,
            args.id,
            id_key=id_key_from_config(config),
            limit=getattr(args, "limit", 100),
            since=getattr(args, "since", None),
            until=getattr(args, "until", None),
            event=getattr(args, "event", None),
            include_all_valid=bool(
                getattr(args, "summary", False)
                or any(
                    getattr(args, name, False)
                    for name in (
                        "duration",
                        "status_dwell",
                        "schedule_analysis",
                        "relation_analysis",
                        "completion_cycles",
                        "transitions",
                        "gaps",
                        "cadence",
                        "oscillation",
                        "provenance_analysis",
                        "progress_analysis",
                        "effort",
                        "schedule_lead_time",
                        "due_variance",
                    )
                )
            ),
        )
        if getattr(args, "compare_window", None) or getattr(args, "to_window", None):
            if not getattr(args, "compare_window", None) or not getattr(
                args, "to_window", None
            ):
                raise ValueError(
                    "--compare-window and --to-window must be provided together."
                )
            if getattr(args, "as_of", None):
                raise ValueError(
                    "--as-of cannot be combined with --compare-window/--to-window."
                )
            from .lifecycle_analytics import compare_lifecycle_windows

            first_start, first_end = _window(args.compare_window)
            second_start, second_end = _window(args.to_window)
            first = native_timeline(
                items,
                args.id,
                id_key=id_key_from_config(config),
                limit=getattr(args, "limit", 100),
                since=first_start,
                until=first_end,
                event=getattr(args, "event", None),
                include_all_valid=True,
            )
            second = native_timeline(
                items,
                args.id,
                id_key=id_key_from_config(config),
                limit=getattr(args, "limit", 100),
                since=second_start,
                until=second_end,
                event=getattr(args, "event", None),
                include_all_valid=True,
            )
            result = compare_lifecycle_windows(first, second)
        as_of_result = None
        if getattr(args, "as_of", None):
            if getattr(args, "summary", False) or any(
                getattr(args, name, False)
                for name in (
                    "duration",
                    "status_dwell",
                    "schedule_analysis",
                    "relation_analysis",
                    "completion_cycles",
                    "transitions",
                    "gaps",
                    "cadence",
                    "oscillation",
                    "provenance_analysis",
                    "progress_analysis",
                    "effort",
                    "schedule_lead_time",
                    "due_variance",
                )
            ):
                raise ValueError(
                    "--as-of cannot be combined with --summary or an analysis flag."
                )
            from .native_semantic_as_of import semantic_as_of

            as_of_result = semantic_as_of(
                items, args.id, args.as_of, id_key=id_key_from_config(config)
            )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    analysis_flags = (
        ("duration", "duration"),
        ("status_dwell", "status_dwell"),
        ("schedule_analysis", "schedule"),
        ("relation_analysis", "relation"),
        ("completion_cycles", "completion_cycles"),
        ("transitions", "transitions"),
        ("gaps", "gaps"),
        ("cadence", "cadence"),
        ("oscillation", "oscillation"),
        ("provenance_analysis", "provenance"),
        ("progress_analysis", "progress"),
        ("effort", "effort"),
        ("schedule_lead_time", "schedule_lead_time"),
        ("due_variance", "due_variance"),
    )
    selected_analysis = next(
        (name for attr, name in analysis_flags if getattr(args, attr, False)), None
    )
    if getattr(args, "compare_window", None) or getattr(args, "to_window", None):
        if getattr(args, "json", False):
            write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        else:
            write_text(None, "Lifecycle window comparison for %s:\n" % args.id)
            for key, value in result["absolute_deltas"].items():
                write_text(None, "  %s: %s\n" % (key, value))
            if result["limitations"]:
                write_text(
                    None, "  Limitations: %s\n" % ", ".join(result["limitations"])
                )
        return 0
    if selected_analysis or getattr(args, "summary", False):
        result = lifecycle_analytics(
            result,
            selected_analysis or "summary",
            timezone_name=resolve_timezone_name(config),
        )
    if as_of_result is not None:
        result = dict(result)
        result["semantic_as_of"] = as_of_result
    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    if selected_analysis or getattr(args, "summary", False):
        write_text(None, "Lifecycle Summary for %s:\n" % result["target_id"])
        write_text(
            None, "  Analysis: %s\n" % result.get("analysis", "lifecycle_summary")
        )
        write_text(None, "  Events: %d\n" % result["observed_event_count"])
        write_text(None, "  First: %s\n" % (result["first_event_at"] or "(none)"))
        write_text(None, "  Last:  %s\n" % (result["last_event_at"] or "(none)"))
        write_text(
            None, "  Status transitions: %d\n" % result["status_transition_count"]
        )
        write_text(None, "  Schedule changes: %d\n" % result["schedule_change_count"])
        write_text(None, "  Relation changes: %d\n" % result["relation_change_count"])
        write_text(None, "  Completed: %d\n" % result["completed_count"])
        write_text(None, "  Reopened: %d\n" % result["reopened_count"])
        base_keys = {
            "analysis_schema",
            "target_id",
            "observed_event_count",
            "event_counts",
            "first_event_at",
            "last_event_at",
            "status_transition_count",
            "schedule_change_count",
            "relation_change_count",
            "completed_count",
            "reopened_count",
            "complete",
            "limitations",
            "diagnostics",
            "analysis",
        }
        for key, value in result.items():
            if key not in base_keys:
                write_text(None, "  %s: %s\n" % (key, value))
        if result["limitations"]:
            write_text(None, "  Limitations: %s\n" % ", ".join(result["limitations"]))
        return 0
    write_text(
        None,
        "Native Timeline for %s (%s):\n"
        % (result["target_id"], result["target"]["title"]),
    )
    write_text(
        None,
        "  Coverage: %s; complete:%s; events:%d/%d\n"
        % (
            result["completeness"]["item"]["coverage"],
            str(result["complete"]).lower(),
            result["bounds"]["returned_events"],
            result["bounds"]["total_valid_events"],
        ),
    )
    for event in result["events"]:
        write_text(
            None,
            "  %s  %s  %s:%s  seq:%s\n"
            % (
                event["at"] or "(no time)",
                event["event"],
                event["record_kind"],
                event["record_id"],
                event["sequence"] if event["sequence"] is not None else "?",
            ),
        )
    if result["invalid_events"]:
        write_text(
            None,
            "  Invalid events excluded: %d\n" % len(result["invalid_events"]),
        )
    for diagnostic in result["diagnostics"]:
        write_text(
            None,
            "  Warning %s: %s\n" % (diagnostic["code"], diagnostic["message"]),
        )
    if result["limitations"]:
        write_text(None, "  Limitations: %s\n" % ", ".join(result["limitations"]))
    if as_of_result is not None:
        write_text(None, "  As of %s:\n" % as_of_result["as_of"])
        for field_name, field_result in as_of_result["fields"].items():
            state = field_result["state"]
            if state == "unavailable":
                write_text(
                    None,
                    "    %s: unavailable (%s)\n" % (field_name, field_result["reason"]),
                )
            elif "values" in field_result:
                write_text(
                    None,
                    "    %s: %s [%s]\n" % (field_name, field_result["values"], state),
                )
            else:
                write_text(
                    None,
                    "    %s: %s [%s]\n" % (field_name, field_result["value"], state),
                )
    return 0


def command_history_check(args):
    from .history_consistency import verify_history_consistency

    config = _config(args)
    paths = _normalize_paths(
        getattr(args, "paths", None), config, stdin_when_empty=False
    ) or ["life.txt"]
    items, _diagnostics = _parse_or_exit(paths, config)
    try:
        result = verify_history_consistency(
            items,
            paths,
            id_key=id_key_from_config(config),
            item_id=getattr(args, "item_id", None),
            commit_limit=getattr(args, "commit_limit", 100),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(
        None,
        "History consistency%s:\n"
        % (" for %s" % result["item_id"] if result["item_id"] else ""),
    )
    write_text(
        None,
        "  Native history: %s (%d event(s))\n"
        % (
            "available" if result["native_evidence"]["available"] else "unavailable",
            result["native_evidence"]["event_count"],
        ),
    )
    write_text(
        None,
        "  Git evidence: %s (%d commit(s); complete:%s)\n"
        % (
            "available" if result["git_evidence"]["available"] else "unavailable",
            result["git_evidence"]["commits_examined"],
            str(result["git_evidence"]["history_complete"]).lower(),
        ),
    )
    for name in (
        "verified",
        "native_only",
        "git_only",
        "conflict",
        "unverifiable",
    ):
        write_text(None, "  %-13s %d\n" % (name + ":", result["summary"][name]))
    for row in result["comparisons"]:
        write_text(
            None,
            "  [%s] %s %s.%s %s -> %s%s\n"
            % (
                row["classification"],
                row["item_id"],
                row["domain"],
                row["field"],
                row["before"],
                row["after"],
                " (%s)" % row["reason"] if row["reason"] else "",
            ),
        )
        if row["classification"] == "conflict" and row["git"]:
            write_text(
                None,
                "    Git: %s -> %s at %s\n"
                % (
                    row["git"]["before"],
                    row["git"]["after"],
                    row["git"]["after_commit"],
                ),
            )
    if result["limitations"]:
        write_text(None, "  Limitations: %s\n" % ", ".join(result["limitations"]))
    return 0


def command_thread(args):
    from .temporal_thread import DEFAULT_STALE_DAYS, temporal_thread
    from .web_read_service import find_item_by_id

    key = id_key_from_config(_config(args))
    paths = _normalize_paths(
        getattr(args, "paths", None), _config(args), stdin_when_empty=False
    ) or ["life.txt"]
    stale_after = getattr(args, "stale_after", None)
    bounds = {
        "max_depth": getattr(args, "depth", 8),
        "max_nodes": getattr(args, "nodes", 50),
        "window_days": getattr(args, "window", 7),
        "temporal_limit": getattr(args, "limit", 20),
        "stale_after_days": (
            stale_after if stale_after is not None else DEFAULT_STALE_DAYS
        ),
    }
    revision = getattr(args, "revision", None)
    diff_spec = getattr(args, "diff", None)
    as_of = getattr(args, "as_of", None)
    requested_ref = getattr(args, "ref", None)
    analysis_items = None
    if requested_ref and not as_of:
        sys.stderr.write("ERROR: --ref is only valid together with --as-of.\n")
        return 1

    try:
        if diff_spec:
            result = _historical_temporal_diff(
                paths, args.id, diff_spec, key=key, bounds=bounds
            )
            if getattr(args, "json", False):
                write_text(
                    None, json.dumps(result, ensure_ascii=False, indent=2) + "\n"
                )
            else:
                _write_temporal_diff(result)
            return 0
        if revision or as_of:
            from .historical_temporal import (
                historical_temporal_thread,
                historical_temporal_thread_as_of,
            )

            if revision:
                result = historical_temporal_thread(
                    paths, args.id, _project_today(), revision, key=key, **bounds
                )
            else:
                result = historical_temporal_thread_as_of(
                    paths,
                    args.id,
                    _project_today(),
                    as_of,
                    ref=requested_ref,
                    key=key,
                    **bounds,
                )
            target = None
        else:
            items, _diagnostics = _parse_or_exit(paths, _config(args))
            analysis_items = items
            target = find_item_by_id(items, args.id, key=key)
            if target is None:
                sys.stderr.write("ERROR: No item with id %r.\n" % args.id)
                return 1
            result = temporal_thread(items, target, _project_today(), key=key, **bounds)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if (
        getattr(args, "metrics", False)
        or getattr(args, "replacement_analysis", False)
        or getattr(args, "consistency_summary", False)
        or getattr(args, "realization_analysis", False)
    ):
        from .temporal_thread import (
            realization_timing_analysis,
            replacement_chain_analysis,
            temporal_consistency_summary,
            temporal_thread_metrics,
        )

        if getattr(args, "metrics", False):
            result["analysis"] = temporal_thread_metrics(result)
        elif getattr(args, "replacement_analysis", False):
            result["analysis"] = replacement_chain_analysis(result)
        else:
            if getattr(args, "realization_analysis", False):
                if analysis_items is None:
                    raise ValueError(
                        "--realization-analysis is only available for current workspace reads."
                    )
                result["analysis"] = realization_timing_analysis(
                    analysis_items, result, key=key
                )
                if getattr(args, "json", False):
                    write_text(
                        None, json.dumps(result, ensure_ascii=False, indent=2) + "\n"
                    )
                    return 0
                write_text(None, "Realizes timing analysis for %s:\n" % args.id)
                for row in result["analysis"]["results"]:
                    write_text(
                        None,
                        "  %s -> %s: %s\n"
                        % (row["actual_id"], row["plan_id"], row["classification"]),
                    )
                return 0
            result["analysis"] = temporal_consistency_summary(result)
    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    if result.get("analysis"):
        write_text(
            None,
            "Thread analysis for %s (%s):\n"
            % (args.id, result["analysis"].get("analysis", "unknown")),
        )
        for key, value in result["analysis"].items():
            if key != "analysis":
                write_text(None, "  %s: %s\n" % (key, value))
    write_text(
        None,
        "Temporal thread for %s (%s):\n" % (args.id, result["target"]["title"]),
    )
    historical = result.get("historical")
    if historical:
        if historical["mode"] == "git_exact_revision":
            write_text(
                None, "  Historical revision: %s\n" % historical["resolved_commit"]
            )
            write_text(None, "  Evidence: git-exact-revision\n")
        else:
            write_text(None, "  As of: %s\n" % historical["cutoff"])
            write_text(None, "  Git ref: %s\n" % historical["requested_ref"])
            write_text(None, "  Time policy: committer\n")
            write_text(
                None, "  Selected revision: %s\n" % historical["selected_commit"]
            )
            write_text(None, "  Evidence: git-history\n")
        if not historical["evidence_complete"]:
            write_text(
                None,
                "  Historical evidence incomplete: %s\n"
                % ", ".join(historical["limitations"]),
            )
    labels = (
        ("predecessors", "Predecessors"),
        ("successors", "Successors"),
        ("realized_plans", "Realized plans"),
        ("realized_by", "Realized by"),
        ("replacement_predecessors", "Replaced predecessors"),
        ("replacement_successors", "Replacement successors"),
    )
    any_explicit = False
    for name, label in labels:
        rows = result["relations"][name]
        if not rows:
            continue
        any_explicit = True
        write_text(None, "  %s:\n" % label)
        for row in rows:
            write_text(None, "    %s %s\n" % (row["id"], row["title"]))
    if not any_explicit:
        write_text(None, "  No explicit lifecycle relations.\n")
    derived = result["derived"]
    write_text(
        None,
        "  Derived temporal context: %d fact(s), %d nearby item(s).\n"
        % (len(derived["facts"]), len(derived["related"])),
    )
    if result["explicit"]["cycles"]:
        write_text(
            None,
            "  Warning: %d lifecycle cycle(s).\n" % len(result["explicit"]["cycles"]),
        )
    warnings = result["consistency"]["warnings"]
    if warnings:
        write_text(None, "  Consistency warnings:\n")
        for warning in warnings:
            evidence = warning["evidence"]
            write_text(
                None,
                "    %s:%s says %s follows %s, but comparable dates say "
                "%s is before %s (%s:%s; %s:%s).\n"
                % (
                    warning["relation"],
                    warning["target_id"],
                    evidence["successor_id"],
                    evidence["predecessor_id"],
                    evidence["successor_id"],
                    evidence["predecessor_id"],
                    evidence["source_field"],
                    evidence["source_value"],
                    evidence["target_field"],
                    evidence["target_value"],
                ),
            )
    if result["consistency"]["truncated"]:
        write_text(None, "  Consistency evidence truncated by thread bounds.\n")
    if result["explicit"]["truncated"]:
        write_text(None, "  Result truncated by explicit traversal bounds.\n")
    return 0


def _split_temporal_diff_spec(value):
    text = str(value or "")
    if text.count("..") != 1:
        raise ValueError("--diff must use exactly REV_A..REV_B.")
    before, after = text.split("..", 1)
    if not before or not after:
        raise ValueError("--diff requires both REV_A and REV_B.")
    return before, after


def _historical_temporal_diff(paths, target_id, diff_spec, key, bounds):
    from .historical_temporal import historical_snapshot, thread_from_snapshot
    from .temporal_diff import temporal_diff

    before_revision, after_revision = _split_temporal_diff_spec(diff_spec)
    before_snapshot = historical_snapshot(paths, before_revision, key=key)
    after_snapshot = historical_snapshot(paths, after_revision, key=key)
    before_thread = thread_from_snapshot(
        before_snapshot,
        target_id,
        _project_today(),
        key=key,
        allow_missing_target=True,
        **bounds,
    )
    after_thread = thread_from_snapshot(
        after_snapshot,
        target_id,
        _project_today(),
        key=key,
        allow_missing_target=True,
        **bounds,
    )
    return temporal_diff(
        before_thread,
        after_thread,
        before_snapshot["historical"],
        after_snapshot["historical"],
        target_id,
    )


def _write_temporal_diff(result):
    write_text(None, "Temporal diff for %s:\n" % result["target_id"])
    write_text(None, "  From: %s\n" % result["from"]["resolved_commit"])
    write_text(None, "  To:   %s\n" % result["to"]["resolved_commit"])
    write_text(
        None,
        "  Target available: from=%s, to=%s\n"
        % (
            str(result["availability"]["from"]).lower(),
            str(result["availability"]["to"]).lower(),
        ),
    )
    sections = (
        ("Items added", result["items"]["added"], lambda row: row["id"]),
        ("Items removed", result["items"]["removed"], lambda row: row["id"]),
        (
            "Item changes",
            result["items"]["changed"],
            lambda row: (
                "%s %s"
                % (
                    row["id"],
                    ", ".join(
                        "%s:%s->%s" % (name, change["from"], change["to"])
                        for name, change in row["changes"].items()
                    ),
                )
            ),
        ),
        (
            "Relations added",
            result["explicit"]["added_edges"],
            lambda row: (
                "%s %s:%s" % (row["source_id"], row["relation"], row["target_id"])
            ),
        ),
        (
            "Relations removed",
            result["explicit"]["removed_edges"],
            lambda row: (
                "%s %s:%s" % (row["source_id"], row["relation"], row["target_id"])
            ),
        ),
        (
            "Consistency introduced",
            result["consistency"]["introduced_warnings"],
            lambda row: (
                "%s %s:%s" % (row["source_id"], row["relation"], row["target_id"])
            ),
        ),
        (
            "Consistency resolved",
            result["consistency"]["resolved_warnings"],
            lambda row: (
                "%s %s:%s" % (row["source_id"], row["relation"], row["target_id"])
            ),
        ),
    )
    any_change = False
    for label, rows, render in sections:
        if not rows:
            continue
        any_change = True
        write_text(None, "  %s:\n" % label)
        for row in rows:
            write_text(None, "    %s\n" % render(row))
    if not any_change:
        write_text(None, "  No semantic lifecycle changes.\n")
    if not result["complete"]:
        write_text(
            None,
            "  Comparison incomplete: %s\n" % ", ".join(result["limitations"]),
        )


def command_freebusy(args):
    from .freebusy import compute_freebusy
    from .timeutil import parse_time

    items, diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    try:
        range_start, range_end = parse_agenda_range(
            start_text=getattr(args, "start", None),
            end_text=getattr(args, "end", None),
            around_text=getattr(args, "around", None),
            window_text=getattr(args, "window", "1h"),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1

    day_start_text = getattr(args, "day_start", None)
    day_end_text = getattr(args, "day_end", None)
    if bool(day_start_text) != bool(day_end_text):
        sys.stderr.write("ERROR: --day-start and --day-end must be used together.\n")
        return 1
    day_window = None
    if day_start_text and day_end_text:
        day_start_time = parse_time(day_start_text)
        day_end_time = parse_time(day_end_text)
        if day_start_time is None or day_end_time is None:
            sys.stderr.write("ERROR: --day-start and --day-end must look like HH:MM.\n")
            return 1
        if day_end_time <= day_start_time:
            sys.stderr.write("ERROR: --day-end must be later than --day-start.\n")
            return 1
        day_window = (day_start_time, day_end_time)

    try:
        result = compute_freebusy(items, range_start, range_end, day_window=day_window)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1

    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        _print_warnings(diagnostics)
        return 0

    write_text(
        None,
        "Freebusy for %s..%s:\n" % (result["range_start"], result["range_end"]),
    )
    if not result["busy"]:
        write_text(None, "  No busy intervals.\n")
    else:
        write_text(None, "  Busy (%d):\n" % len(result["busy"]))
        for entry in result["busy"]:
            write_text(
                None,
                "    %s..%s (%s) %s\n"
                % (
                    entry["start"],
                    entry["end"],
                    entry["source_field"],
                    entry["item"]["title"],
                ),
            )
    if not result["free"]:
        write_text(None, "  No free intervals.\n")
    else:
        write_text(None, "  Free (%d):\n" % len(result["free"]))
        for entry in result["free"]:
            write_text(None, "    %s..%s\n" % (entry["start"], entry["end"]))
    if result["conflicts"]:
        write_text(None, "  Conflicts (%d):\n" % len(result["conflicts"]))
        for conflict in result["conflicts"]:
            write_text(
                None,
                "    %s overlaps %s: %s..%s\n"
                % (
                    conflict["a"]["title"],
                    conflict["b"]["title"],
                    conflict["start"],
                    conflict["end"],
                ),
            )
    if result["instants"]:
        write_text(None, "  Instants (%d):\n" % len(result["instants"]))
        for instant in result["instants"]:
            write_text(
                None,
                "    %s (%s) %s\n"
                % (instant["at"], instant["source_field"], instant["item"]["title"]),
            )
    for diag in result["diagnostics"]:
        write_text(
            None,
            "  NOTE: %s %s\n" % (diag["code"], diag["message"]),
        )
    _print_warnings(diagnostics)
    return 0


def command_vm_run(args):
    from .vm import (
        VMProgramError,
        VMStepLimitExceeded,
        build_program,
        run_program,
    )

    config = _config(args)
    paths = _normalize_paths(
        getattr(args, "paths", None), config, stdin_when_empty=False
    ) or ["life.txt"]
    items, _diagnostics = _parse_or_exit(paths, config)
    key = id_key_from_config(config)
    try:
        program = build_program(items, id_key=key)
        result = run_program(program, args.entry, max_steps=args.max_steps)
    except VMProgramError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    except VMStepLimitExceeded as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("Interrupted.\n")
        return 130

    if getattr(args, "json", False):
        payload = OrderedDict(
            (
                ("halted", True),
                ("entry", args.entry),
                ("steps", result.steps),
                ("state", OrderedDict(result.state.items())),
            )
        )
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    write_text(
        None,
        "HALT after %d step%s\n" % (result.steps, "" if result.steps == 1 else "s"),
    )
    for counter_id, value in result.state.items():
        write_text(None, "%s=%s\n" % (counter_id, value))
    return 0


def command_vm_graph(args):
    from .vm import VMProgramError, build_program, program_to_dot, program_to_mermaid

    config = _config(args)
    paths = _normalize_paths(
        getattr(args, "paths", None), config, stdin_when_empty=False
    ) or ["life.txt"]
    items, _diagnostics = _parse_or_exit(paths, config)
    key = id_key_from_config(config)
    try:
        program = build_program(items, id_key=key)
        if args.format == "dot":
            output = program_to_dot(program, entry=args.entry)
        else:
            output = program_to_mermaid(program, entry=args.entry)
    except VMProgramError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1

    write_text(None, output)
    return 0


def _backup_result_json(result):
    return OrderedDict(
        (
            ("path", result.path),
            ("format", result.manifest.get("format")),
            ("created_at", result.manifest.get("created_at")),
            ("file_count", result.manifest.get("file_count")),
            ("total_bytes", result.manifest.get("total_bytes")),
        )
    )


def _backup_verify_result_json(result):
    return OrderedDict(
        (
            ("ok", result.ok),
            ("format", result.manifest.get("format") if result.manifest else None),
            ("errors", list(result.errors)),
        )
    )


def command_backup_create(args):
    from .backup import BackupError
    from .backup_cli import (
        BackupCliError,
        run_create,
        resolve_destination,
        resolve_sources,
    )

    config = _config(args)
    try:
        destination = resolve_destination(config, args.destination)
        sources = resolve_sources(config, args.sources or None)
        result = run_create(sources, destination)
    except (BackupCliError, BackupError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(
            None,
            json.dumps(_backup_result_json(result), ensure_ascii=False, indent=2)
            + "\n",
        )
    else:
        write_text(None, "Created backup: %s\n" % result.path)
    return 0


def command_backup_status(args):
    from .backup_cli import BackupCliError, resolve_destination, run_status

    config = _config(args)
    try:
        destination = resolve_destination(config, args.destination)
        status = run_status(destination)
    except BackupCliError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(status, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "Backup status for %s:\n" % status["destination"])
    write_text(None, "  Local backups: %d\n" % status["backup_count"])
    write_text(
        None, "  Latest local backup: %s\n" % (status["latest_local_backup"] or "-")
    )
    write_text(
        None,
        "  Last attempt: %s (ok=%s)\n"
        % (status["last_attempt_at"] or "-", status["last_attempt_ok"]),
    )
    write_text(
        None,
        "  Last remote upload: %s (ok=%s)\n"
        % (status["last_remote_upload_at"] or "-", status["last_remote_upload_ok"]),
    )
    if status.get("last_remote_error"):
        write_text(None, "  Last remote error: %s\n" % status["last_remote_error"])
    return 0


def command_backup_verify(args):
    from .backup_cli import (
        BackupCliError,
        resolve_destination,
        run_verify,
        run_verify_latest,
    )

    if bool(args.path) == bool(args.latest):
        sys.stderr.write("ERROR: Pass exactly one of BACKUP or --latest.\n")
        return 1
    try:
        if args.latest:
            destination = resolve_destination(_config(args), args.destination)
            path, result = run_verify_latest(destination)
        else:
            if args.destination:
                sys.stderr.write("ERROR: --destination is only valid with --latest.\n")
                return 1
            path = args.path
            result = run_verify(path)
    except BackupCliError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        payload = _backup_verify_result_json(result)
        if args.latest:
            payload["path"] = path
        write_text(
            None,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )
    else:
        write_text(None, "Backup %s: %s\n" % (path, "OK" if result.ok else "INVALID"))
        for error in result.errors:
            write_text(None, "  - %s\n" % error)
    return 0 if result.ok else 1


def command_backup_restore(args):
    from .backup import BackupError
    from .backup_cli import run_restore

    try:
        result = run_restore(
            args.path,
            args.destination_dir,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    except BackupError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(
            None,
            json.dumps(
                OrderedDict(
                    (
                        ("dry_run", result.dry_run),
                        ("restored", list(result.restored)),
                        ("conflicts", list(result.conflicts)),
                        ("errors", list(result.errors)),
                    )
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    else:
        write_text(
            None,
            "%s %d file(s)%s\n"
            % (
                "Would restore" if result.dry_run else "Restored",
                len(result.restored),
                " (dry run)" if result.dry_run else "",
            ),
        )
        for conflict in result.conflicts:
            write_text(None, "  conflict: %s\n" % conflict)
        for error in result.errors:
            write_text(None, "  error: %s\n" % error)
    return 0 if result.ok else 1


def command_backup_prune(args):
    from .backup import BackupError
    from .backup_cli import BackupCliError, resolve_destination, run_prune

    config = _config(args)
    try:
        destination = resolve_destination(config, args.destination)
        result = run_prune(destination, keep_last=args.keep_last, dry_run=args.dry_run)
    except (BackupCliError, BackupError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(
            None,
            json.dumps(
                OrderedDict(
                    (
                        ("dry_run", result.dry_run),
                        ("kept", list(result.kept)),
                        ("deleted", list(result.deleted)),
                        ("ignored", list(result.ignored)),
                        ("errors", list(result.errors)),
                    )
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    else:
        write_text(
            None,
            "%s %d, deleted %d, ignored %d\n"
            % (
                "Would keep" if result.dry_run else "Kept",
                len(result.kept),
                len(result.deleted),
                len(result.ignored),
            ),
        )
    return 0


def command_backup_run_scheduled(args):
    from .backup import BackupError
    from .backup_cli import BackupCliError, run_scheduled
    from .backup_remote import RcloneError

    config = _config(args)
    try:
        outcome = run_scheduled(config)
    except (BackupCliError, BackupError, RcloneError) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(
            None,
            json.dumps(
                OrderedDict(
                    (
                        ("backup", _backup_result_json(outcome["backup"])),
                        ("remote_uploaded", outcome["remote_uploaded"]),
                        ("remote_error", outcome["remote_error"]),
                    )
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    else:
        write_text(None, "Created backup: %s\n" % outcome["backup"].path)
        if outcome["remote_uploaded"] is not None:
            write_text(
                None,
                "Remote upload: %s\n"
                % ("ok" if outcome["remote_uploaded"] else "FAILED"),
            )
            if outcome["remote_error"]:
                write_text(None, "  %s\n" % outcome["remote_error"])
    return 0


def command_item_uri_format(args):
    from .item_uri import ItemUriError, format_item_uri, web_deep_link

    try:
        uri = format_item_uri(args.id)
    except ItemUriError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    deep_link = (
        web_deep_link(args.id, base_url=args.base_url) if args.base_url else None
    )
    if getattr(args, "json", False):
        payload = OrderedDict((("id", args.id), ("uri", uri)))
        if deep_link is not None:
            payload["web_deep_link"] = deep_link
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, uri + "\n")
    if deep_link is not None:
        write_text(None, deep_link + "\n")
    return 0


def command_item_uri_parse(args):
    from .item_uri import ItemUriError, parse_item_uri

    try:
        item_id = parse_item_uri(args.uri)
    except ItemUriError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        payload = OrderedDict((("uri", args.uri), ("id", item_id)))
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, item_id + "\n")
    return 0


def _format_query_explanation(explanation):
    """Render the query explanation for people at a terminal."""
    plan = explanation["plan"]
    lines = ["Query explanation:", "  query: %s" % plan["query"]]
    for key in ("membership", "details", "date_filters", "progress_filters", "text"):
        value = plan[key]
        if isinstance(value, dict):
            rendered = [
                "%s=%s" % (field, ", ".join(str(item) for item in values))
                for field, values in value.items()
            ]
        elif isinstance(value, list):
            rendered = [json.dumps(item, ensure_ascii=False) for item in value]
        else:
            rendered = [str(value)]
        lines.append("  %s: %s" % (key, "; ".join(rendered) or "(none)"))
    lines.append("  open_only: %s" % ("true" if plan["open_only"] else "false"))
    diagnostics = explanation["diagnostics"]
    if diagnostics:
        lines.append("  diagnostics:")
        for item in diagnostics:
            lines.append(
                "    %s %s: %s" % (item["severity"], item["code"], item["message"])
            )
    else:
        lines.append("  diagnostics: (none)")
    return "\n".join(lines) + "\n"


def command_query(args):
    from .query import explain_query, run_query

    config = _config(args)
    if getattr(args, "explain", False):
        explanation = explain_query(args.query, config=config)
        if getattr(args, "format", "life") == "json":
            output = (
                json.dumps(
                    explanation,
                    ensure_ascii=False,
                    indent=2 if getattr(args, "pretty", False) else None,
                    separators=None if getattr(args, "pretty", False) else (",", ":"),
                )
                + "\n"
            )
        else:
            output = _format_query_explanation(explanation)
        write_text(getattr(args, "output", None), output)
        if any(d["severity"] == "error" for d in explanation["diagnostics"]):
            for d in explanation["diagnostics"]:
                if d["severity"] == "error":
                    sys.stderr.write("ERROR: %s %s\n" % (d["code"], d["message"]))
            return 1
        return 0

    revision = getattr(args, "revision", None)
    as_of = getattr(args, "as_of", None)
    historical = None
    if revision or as_of:
        # Historical revision/as-of-scoped query (#726/#730/#760): the shared
        # read-only snapshot reader is the only Git historical input path,
        # and its items feed the existing, unmodified Query engine unchanged.
        from .historical_temporal import read_historical_snapshot

        key = id_key_from_config(config)
        paths = _normalize_paths(
            getattr(args, "paths", None), config, stdin_when_empty=False
        ) or ["life.txt"]
        try:
            snapshot = read_historical_snapshot(
                paths,
                key=key,
                revision=revision,
                as_of=as_of,
                ref=getattr(args, "ref", None),
            )
        except ValueError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        errors = [
            diagnostic
            for diagnostic in snapshot["diagnostics"]
            if getattr(diagnostic, "severity", "") == "error"
        ]
        if errors:
            first = errors[0]
            sys.stderr.write(
                "ERROR: historical input has %s at %s:%s.\n"
                % (first.code, first.source or "(unknown source)", first.line or "?")
            )
            return 1
        items = snapshot["items"]
        historical = snapshot["historical"]
    else:
        items, _diagnostics = _parse_or_exit(
            _normalize_paths(
                getattr(args, "paths", None), config, stdin_when_empty=False
            )
            or ["life.txt"],
            config,
        )
    filtered, query_diags = run_query(
        items,
        args.query,
        config=config,
        sort=getattr(args, "sort", None),
        order=getattr(args, "order", "asc"),
        limit=getattr(args, "limit", None),
    )
    if any(d["severity"] == "error" for d in query_diags):
        for d in query_diags:
            if d["severity"] == "error":
                sys.stderr.write("ERROR: %s %s\n" % (d["code"], d["message"]))
        return 1
    if historical is not None:
        fmt = getattr(args, "format", "life")
        if fmt == "json":
            payload = OrderedDict(
                (
                    ("historical", historical),
                    (
                        "items",
                        json.loads(items_to_json(filtered, pretty=False)),
                    ),
                )
            )
            write_text(
                args.output,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2 if getattr(args, "pretty", False) else None,
                    separators=(None if getattr(args, "pretty", False) else (",", ":")),
                )
                + "\n",
            )
            for row in query_diags or []:
                if row.get("severity") == "error":
                    sys.stderr.write(
                        "ERROR: %s %s\n" % (row.get("code"), row.get("message"))
                    )
                else:
                    sys.stderr.write(
                        "WARNING: %s %s\n" % (row.get("code"), row.get("message"))
                    )
            return 0
        if historical["mode"] == "git_exact_revision":
            write_text(
                None,
                "Historical revision: %s (resolved %s)\n"
                % (historical["requested_revision"], historical["resolved_commit"]),
            )
        else:
            write_text(
                None,
                "Historical as of: %s (ref %s, resolved %s)\n"
                % (
                    historical["cutoff"],
                    historical["requested_ref"],
                    historical["selected_commit"],
                ),
            )
        if not historical["evidence_complete"]:
            write_text(
                None,
                "Historical evidence incomplete: %s\n"
                % ", ".join(historical["limitations"]),
            )
    _emit_query_items(args, filtered, query_diags)
    return 0


def command_view_list(args):
    from .saved_views import list_saved_views

    views = list_saved_views(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(views, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not views:
        write_text(None, "No saved views configured.\n")
        return 0
    for view in views:
        sort = ",".join(view["sort"]) or "-"
        write_text(
            None,
            "%-20s %s  (sort=%s limit=%s)\n"
            % (view["name"], view["query"], sort, view["limit"]),
        )
    return 0


def command_view_show(args):
    from .saved_views import get_saved_view

    try:
        view = get_saved_view(_config(args), args.name)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, json.dumps(view, ensure_ascii=False, indent=2) + "\n")
    return 0


def command_view_validate(args):
    from .saved_views import validate_saved_views

    rows = validate_saved_views(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0 if not rows else 1
    if not rows:
        write_text(None, "All saved views are valid.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "[%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 1


def command_view_run(args):
    from .saved_views import run_saved_view

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    try:
        filtered, query_diags = run_saved_view(items, _config(args), args.name)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    _emit_query_items(args, filtered, query_diags)
    return 0


def command_group_list(args):
    from .groups import group_summaries

    summaries = group_summaries(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not summaries:
        write_text(None, "No groups configured.\n")
        return 0
    for row in summaries:
        flag = "" if row["ok"] else " [errors]"
        write_text(
            None,
            "%-20s %d member(s), %d disabled%s\n"
            % (row["name"], row["resolved_members"], row["disabled"], flag),
        )
    return 0


def command_group_show(args):
    from .groups import expand_group, group_directory

    config = _config(args)
    directory = group_directory(config)
    if args.name not in directory:
        sys.stderr.write("ERROR: Unknown group %r\n" % args.name)
        return 1
    diagnostics = []
    members = expand_group(config, args.name, diagnostics=diagnostics)
    if getattr(args, "json", False):
        payload = OrderedDict(
            (
                ("name", args.name),
                ("members", members),
                ("definition", directory[args.name]),
                ("diagnostics", diagnostics),
            )
        )
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(None, "%s (%d resolved member(s)):\n" % (args.name, len(members)))
    for member in members:
        write_text(None, "  - %s\n" % member)
    for row in diagnostics:
        write_text(
            None,
            "  [%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0


def command_group_validate(args):
    from .groups import validate_groups

    rows = validate_groups(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0 if not any(r["severity"] == "error" for r in rows) else 1
    if not rows:
        write_text(None, "All groups are valid.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "[%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0 if not any(r["severity"] == "error" for r in rows) else 1


def command_message_recipients(args):
    from .groups import resolve_recipients

    refs = [r.strip() for r in str(args.to).split(",") if r.strip()]
    result = resolve_recipients(_config(args), refs)
    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return (
            0 if not any(d["severity"] == "error" for d in result["diagnostics"]) else 1
        )
    write_text(
        None, "Resolved %d recipient(s) from %s:\n" % (result["count"], ", ".join(refs))
    )
    for recipient in result["recipients"]:
        write_text(None, "  - %s\n" % recipient)
    for row in result["diagnostics"]:
        write_text(
            None,
            "  [%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0 if not any(d["severity"] == "error" for d in result["diagnostics"]) else 1


def command_message_send(args):
    from .groups import resolve_recipients

    refs = [r.strip() for r in str(args.to).split(",") if r.strip()]
    config = _config(args)
    result = resolve_recipients(config, refs)
    errors = [d for d in result["diagnostics"] if d["severity"] == "error"]
    if errors:
        for row in errors:
            sys.stderr.write("ERROR: %s %s\n" % (row["code"], row["message"]))
        return 1
    if not result["recipients"]:
        sys.stderr.write("ERROR: No recipients resolved.\n")
        return 1
    sender = args.sender or config_user_name(config)
    line = _build_message_line(
        args.title,
        sender,
        result,
        refs,
        ack_policy=getattr(args, "ack_policy", "any"),
        body=getattr(args, "body", None),
    )
    if getattr(args, "dry_run", False):
        write_text(None, line + "\n")
        return 0
    target = getattr(args, "output", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    _ensure_writable_path(target, config, "message send")
    append_line(target, line)
    write_text(
        None,
        "Appended message to %s (%d recipient(s)):\n  %s\n"
        % (target, result["count"], line),
    )
    return 0


def _build_message_line(title, sender, resolution, refs, ack_policy="any", body=None):
    parts = ["[ ] M", "_".join(str(title).split()), "sender:%s" % sender]
    for recipient in resolution["recipients"]:
        parts.append("recipient:%s" % recipient)
    # Preserve the original group/team references for audit without losing the
    # readable resolved recipient list above. A reference is a group/team when
    # its expansion is not simply the literal name itself.
    expansion = resolution.get("expansion", {})
    for ref in refs:
        _prefix, bare = _split_group_ref(ref)
        expanded = expansion.get(ref, [ref])
        if expanded != [bare]:
            parts.append("group:%s" % bare)
    if ack_policy and ack_policy != "any":
        parts.append("ack_policy:%s" % ack_policy)
    if body:
        parts.append("body:%s" % "_".join(str(body).split()))
    return " ".join(parts)


def _split_group_ref(ref):
    text = str(ref)
    for prefix in ("group:", "team:", "user:", "person:"):
        if text.startswith(prefix):
            return prefix[:-1], text[len(prefix) :]
    return None, text


def command_message_status(args):
    from .delivery import delivery_summary
    from .groups import resolve_recipients

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    config = _config(args)
    target_id = getattr(args, "id", None)
    policy = getattr(args, "policy", None)
    summaries = []
    for item in items:
        if item.kind != "M":
            continue
        if target_id and (item.details.get("id", [None])[0] != target_id):
            continue
        summaries.append(delivery_summary(item, config, resolve_recipients, policy))
    if getattr(args, "json", False):
        write_text(None, json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not summaries:
        write_text(None, "No messages found.\n")
        return 0
    for summary in summaries:
        ack = summary["acknowledgement"]
        write_text(
            None,
            "%s [%s] recipients=%d ack=%d/%d (%s) %s\n"
            % (
                summary["title"],
                summary["message_id"] or "no-id",
                summary["recipient_count"],
                ack["acknowledged"],
                ack["required"],
                ack["policy"],
                "COMPLETE" if ack["complete"] else "open",
            ),
        )
        for state in summary["states"]:
            write_text(None, "    %-16s %s\n" % (state["recipient"], state["state"]))
    return 0


def command_person_list(args):
    from .people import people_list

    rows = people_list(_project_items(args), _config(args), _project_today())
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No people found.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "%-20s open=%d messages=%d meetings=%d\n"
            % (row["person"], row["assigned_open"], row["messages"], row["meetings"]),
        )
    return 0


def command_person_show(args):
    from .people import person_overview

    ov = person_overview(
        _project_items(args), _config(args), args.name, _project_today()
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(ov, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(
        None,
        "%s%s\n"
        % (ov["person"], (" (%s)" % ", ".join(ov["aliases"])) if ov["aliases"] else ""),
    )
    if ov["presence"]:
        write_text(
            None,
            "  presence: %s %s\n"
            % (ov["presence"].get("state") or "", ov["presence"].get("from") or ""),
        )
    counts = ov["counts"]
    write_text(
        None,
        "  open=%d waiting=%d overdue=%d sent=%d received=%d meetings=%d\n"
        % (
            counts["assigned_open"],
            counts["waiting"],
            counts["overdue"],
            counts["messages_sent"],
            counts["messages_received"],
            counts["meetings"],
        ),
    )
    mem = ov["memberships"]
    if mem["teams"] or mem["groups"]:
        write_text(
            None,
            "  teams: %s  groups: %s\n"
            % (", ".join(mem["teams"]) or "-", ", ".join(mem["groups"]) or "-"),
        )
    _person_section("Assigned (open)", ov["assigned_open"])
    _person_section("Overdue", ov["overdue"])
    _person_section("Waiting", ov["waiting"])
    _person_section("Meetings", ov["meetings"])
    if ov["projects"]:
        write_text(None, "  projects:\n")
        for proj in ov["projects"]:
            role = "owner" if proj["owner"] else "member"
            write_text(
                None,
                "    - %s (%s, %d task(s))\n"
                % (proj["name"], role, proj["assigned_tasks"]),
            )
    return 0


def _person_section(label, rows, limit=10):
    if not rows:
        return
    write_text(None, "  %s (%d):\n" % (label, len(rows)))
    for row in rows[:limit]:
        due = (
            " due:%s%s" % (row["due"], _relative_date_suffix(row["due"]))
            if row.get("due")
            else ""
        )
        project = " @%s" % row["project"] if row.get("project") else ""
        write_text(
            None, "    - %s %s%s%s\n" % (row["status"], row["title"], project, due)
        )


def command_person_group(args):
    from .people import group_overview

    try:
        report = group_overview(
            _project_items(args), _config(args), args.name, _project_today()
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(
        None,
        "%s (%d member(s)) open=%d overdue=%d\n"
        % (
            report["group"],
            report["member_count"],
            report["total_assigned_open"],
            report["total_overdue"],
        ),
    )
    for member in report["members"]:
        write_text(
            None,
            "  %-20s open=%d overdue=%d received=%d\n"
            % (
                member["person"],
                member["assigned_open"],
                member["overdue"],
                member["messages_received"],
            ),
        )
    for row in report["diagnostics"]:
        write_text(
            None,
            "  [%s] %s: %s\n" % (row["severity"].upper(), row["code"], row["message"]),
        )
    return 0


def _proposal_target(args):
    config = _config(args)
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    return target


def command_proposal_list(args):
    from .inbox import inbox_summary, list_proposals, proposal_to_line

    config = _config(args)
    proposals = list_proposals(config, status=getattr(args, "status", None))
    if getattr(args, "json", False):
        write_text(None, json.dumps(proposals, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not proposals:
        write_text(None, "No proposals.\n")
        return 0
    for proposal in proposals:
        try:
            preview = proposal_to_line(proposal)
        except ValueError:
            preview = proposal.get("operation", "?")
        write_text(
            None,
            "%-12s [%-8s] %-8s %s\n"
            % (
                proposal["id"],
                proposal.get("status", "pending"),
                proposal.get("source", ""),
                preview,
            ),
        )
    summary = inbox_summary(config)
    write_text(
        None,
        "(%d total: %s)\n"
        % (
            summary["total"],
            ", ".join("%s=%d" % (k, v) for k, v in summary["counts"].items() if v),
        ),
    )
    return 0


def _proposal_details_from_args(args):
    details = OrderedDict()
    for key in ("project", "due", "assignee", "priority"):
        value = getattr(args, key, None)
        if value:
            details[key] = value
    tags = getattr(args, "tag", None)
    if tags:
        details["tag"] = tags
    return details


def command_proposal_add(args):
    from .inbox import stage_create

    proposal = stage_create(
        _config(args),
        args.title,
        kind=getattr(args, "kind", "T"),
        details=_proposal_details_from_args(args),
        source=getattr(args, "source", "manual"),
    )
    write_text(None, "Staged proposal %s\n" % proposal["id"])
    return 0


def command_proposal_show(args):
    from .inbox import get_proposal

    proposal = get_proposal(_config(args), args.id)
    if proposal is None:
        sys.stderr.write("ERROR: Unknown proposal %r\n" % args.id)
        return 1
    write_text(None, json.dumps(proposal, ensure_ascii=False, indent=2) + "\n")
    return 0


def command_proposal_edit(args):
    from .inbox import edit_proposal

    try:
        edit_proposal(
            _config(args),
            args.id,
            title=getattr(args, "title", None),
            kind=getattr(args, "kind", None),
            details=_proposal_details_from_args(args),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "Edited proposal %s\n" % args.id)
    return 0


def command_proposal_accept(args):
    from .inbox import batch_apply

    config = _config(args)
    target = _proposal_target(args)
    _ensure_writable_path(target, config, "proposal accept")
    report = batch_apply(config, args.ids, target)
    for result in report["results"]:
        if result.get("applied"):
            write_text(
                None,
                "Accepted %s -> %s\n  %s\n" % (result["id"], target, result["line"]),
            )
        else:
            sys.stderr.write("ERROR: %s: %s\n" % (result["id"], result.get("error")))
    write_text(None, "Applied %d/%d.\n" % (report["applied"], report["total"]))
    return 0 if report["applied"] == report["total"] else 1


def command_proposal_reject(args):
    from .inbox import reject

    try:
        reject(_config(args), args.id)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "Rejected %s\n" % args.id)
    return 0


def command_proposal_defer(args):
    from .inbox import defer

    try:
        defer(_config(args), args.id)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "Deferred %s\n" % args.id)
    return 0


def command_find(args):
    from .global_search import global_search

    items, _diagnostics = _parse_or_exit(
        _normalize_paths(
            getattr(args, "paths", None), _config(args), stdin_when_empty=False
        )
        or ["life.txt"],
        _config(args),
    )
    types = _split_csv_args(getattr(args, "types", None)) or None
    result = global_search(
        items,
        _config(args),
        args.term,
        types=types,
        limit=getattr(args, "limit", None),
        fuzzy=getattr(args, "fuzzy", False),
    )
    if getattr(args, "json", False):
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not result["total"]:
        write_text(None, "No matches for %r.\n" % args.term)
        return 0
    write_text(None, "%d match(es) for %r:\n" % (result["total"], args.term))
    for entity, rows in result["groups"].items():
        write_text(None, "%s (%d):\n" % (entity, len(rows)))
        for row in rows:
            location = ""
            if row.get("source") and row.get("line"):
                location = " (%s:%s)" % (row["source"], row["line"])
            write_text(None, "  %-20s %s%s\n" % (row["name"], row["snippet"], location))
    return 0


def _ticket_paths(args):
    return _normalize_paths(
        getattr(args, "paths", None), _config(args), stdin_when_empty=False
    ) or ["life.txt"]


def _ticket_write_file(args, ticket_id=None):
    from .tickets import find_ticket_file

    config = _config(args)
    if ticket_id:
        found = find_ticket_file(
            _ticket_paths(args), ticket_id, key=id_key_from_config(config)
        )
        if found:
            return found
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    return target


def command_ticket_new(args):
    from .tickets import build_ticket_line, next_ticket_id

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    ticket_id = getattr(args, "id", None) or next_ticket_id(items, config)
    line = build_ticket_line(
        config,
        args.subject,
        tracker=args.tracker,
        priority=args.priority,
        severity=args.severity,
        assignee=args.assignee,
        reporter=args.reporter,
        component=args.component,
        version=args.version,
        sprint=args.sprint,
        project=args.project,
        due=args.due,
        est=args.est,
        ticket_status=getattr(args, "status", "new"),
        watchers=getattr(args, "watcher", None),
        ticket_id=ticket_id,
    )
    if getattr(args, "dry_run", False):
        write_text(None, line + "\n")
        return 0
    target = getattr(args, "to", None) or config_write_file(config)
    if not target:
        paths = config_paths(config)
        target = paths[0] if paths else "life.txt"
    _ensure_writable_path(target, config, "ticket new")
    event_line = _ticket_creation_event_line(
        ticket_id,
        config,
        project=args.project,
        tracker=args.tracker,
        author=args.reporter,
    )
    append_line(target, line + "\n" + event_line)
    write_text(None, "Created %s in %s:\n  %s\n" % (ticket_id, target, line))
    return 0


def _ticket_creation_event_line(
    ticket_id, config, project=None, tracker=None, author=None
):
    from .serializer import item_to_line
    from .ticket_activity import build_creation_event

    event = build_creation_event(
        ticket_id,
        author=author or config_user_name(config),
        project=project,
        tracker=tracker,
    )
    return item_to_line(event)


def command_ticket_list(args):
    from .tickets import ticket_list

    config = _config(args)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    filters = {}
    for field in (
        "tracker",
        "status",
        "priority",
        "severity",
        "assignee",
        "component",
        "version",
        "sprint",
        "project",
    ):
        value = getattr(args, field, None)
        if value:
            filters["ticket_status" if field == "status" else field] = value
    if getattr(args, "open_only", False):
        filters["open_only"] = True
    rows = ticket_list(items, config, filters, key=id_key_from_config(config))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not rows:
        write_text(None, "No tickets.\n")
        return 0
    for row in rows:
        write_text(
            None,
            "%-10s %-8s %-10s %-8s %-10s %s\n"
            % (
                row["id"] or "-",
                row["tracker"] or "-",
                row["ticket_status"] or "-",
                row["priority"] or "-",
                row["assignee"] or "-",
                row["title"],
            ),
        )
    return 0


def command_ticket_show(args):
    from .tickets import ticket_view

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    from .tickets import is_ticket, ticket_id_of

    target = None
    for item in items:
        if is_ticket(item) and str(ticket_id_of(item, key)) == args.id:
            target = item
            break
    if target is None:
        sys.stderr.write("ERROR: Ticket %r not found.\n" % args.id)
        return 1
    view = ticket_view(target, config, items, key=key)
    if getattr(args, "json", False):
        write_text(None, json.dumps(view, ensure_ascii=False, indent=2) + "\n")
        return 0
    s = view["summary"]
    write_text(None, "%s  %s\n" % (s["id"], s["title"]))
    write_text(
        None,
        "  tracker=%s status=%s (%s) priority=%s severity=%s\n"
        % (s["tracker"], s["ticket_status"], s["status"], s["priority"], s["severity"]),
    )
    write_text(
        None,
        "  assignee=%s reporter=%s project=%s component=%s version=%s sprint=%s\n"
        % (
            s["assignee"],
            s["reporter"],
            s["project"],
            s["component"],
            s["version"],
            s["sprint"],
        ),
    )
    if s["watchers"]:
        write_text(None, "  watchers: %s\n" % ", ".join(s["watchers"]))
    if view["relations"]:
        write_text(None, "  relations:\n")
        for relation, targets in view["relations"].items():
            write_text(None, "    %s: %s\n" % (relation, ", ".join(targets)))
    if view["incoming_links"]:
        write_text(None, "  referenced by:\n")
        for row in view["incoming_links"]:
            write_text(
                None,
                "    %s <- %s %s\n"
                % (row["relation"], row["source_id"] or "?", row["source_title"]),
            )
    return 0


def _ticket_patch_and_report(
    args, ticket_id, detail_updates, status=None, verb="Updated"
):
    from .tickets import apply_ticket_patch

    config = _config(args)
    key = id_key_from_config(config)
    target = _ticket_write_file(args, ticket_id)
    _ensure_writable_path(target, config, "ticket edit")
    try:
        apply_ticket_patch(target, ticket_id, detail_updates, status=status, key=key)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    write_text(None, "%s %s in %s\n" % (verb, ticket_id, target))
    return 0


def command_ticket_edit(args):
    updates = OrderedDict()
    for pair in getattr(args, "set_fields", None) or []:
        if "=" not in pair:
            sys.stderr.write("ERROR: --set expects KEY=VALUE, got %r\n" % pair)
            return 1
        k, v = pair.split("=", 1)
        updates[k.strip()] = v.strip()
    for key in getattr(args, "unset", None) or []:
        updates[key.strip()] = None
    if not updates:
        sys.stderr.write("ERROR: nothing to change; use --set or --unset.\n")
        return 1
    if getattr(args, "dry_run", False):
        write_text(
            None,
            "Would update %s: %s\n"
            % (args.id, json.dumps(updates, ensure_ascii=False)),
        )
        return 0
    return _ticket_patch_and_report(args, args.id, updates, verb="Edited")


def command_ticket_assign(args):
    return _ticket_patch_and_report(
        args, args.id, {"assignee": args.assignee}, verb="Assigned"
    )


def command_ticket_close(args):
    from .tickets import TERMINAL_STATUSES, transition_updates

    status = getattr(args, "status", "closed")
    if status not in TERMINAL_STATUSES:
        sys.stderr.write(
            "ERROR: %r is not a terminal status (%s).\n"
            % (status, ", ".join(TERMINAL_STATUSES))
        )
        return 1
    actor = getattr(args, "by", None) or config_user_name(_config(args))
    updates, life = transition_updates(_config(args), status, actor=actor)
    if getattr(args, "resolution", None):
        updates["resolution"] = args.resolution
    return _ticket_patch_and_report(args, args.id, updates, status=life, verb="Closed")


def command_ticket_reopen(args):
    from .tickets import transition_updates

    status = getattr(args, "status", "new")
    updates, life = transition_updates(_config(args), status)
    updates["closed_by"] = None
    updates["resolution"] = None
    return _ticket_patch_and_report(
        args, args.id, updates, status=life, verb="Reopened"
    )


def _ticket_relation_edit(args, add):
    from .tickets import apply_ticket_patch, is_ticket, ticket_id_of

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    current = None
    for item in items:
        if is_ticket(item) and str(ticket_id_of(item, key)) == args.id:
            current = item
            break
    if current is None:
        sys.stderr.write("ERROR: Ticket %r not found.\n" % args.id)
        return 1
    existing = [str(v) for v in current.details.get(args.relation, [])]
    if add:
        if args.target in existing:
            write_text(
                None, "%s already has %s:%s\n" % (args.id, args.relation, args.target)
            )
            return 0
        new_values = existing + [args.target]
    else:
        if args.target not in existing:
            sys.stderr.write(
                "ERROR: %s has no %s:%s\n" % (args.id, args.relation, args.target)
            )
            return 1
        new_values = [v for v in existing if v != args.target]
    target = _ticket_write_file(args, args.id)
    _ensure_writable_path(target, config, "ticket link")
    apply_ticket_patch(target, args.id, {args.relation: new_values or None}, key=key)
    write_text(
        None,
        "%s %s %s:%s\n"
        % ("Linked" if add else "Unlinked", args.id, args.relation, args.target),
    )
    return 0


def command_ticket_link(args):
    return _ticket_relation_edit(args, add=True)


def command_ticket_unlink(args):
    return _ticket_relation_edit(args, add=False)


def command_ticket_validate(args):
    from .tickets import iter_tickets, validate_ticket

    config = _config(args)
    key = id_key_from_config(config)
    items, _diags = _parse_or_exit(_ticket_paths(args), config)
    rows = []
    for item in iter_tickets(items):
        rows.extend(validate_ticket(item, config, key=key))
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0 if not any(r["severity"] == "error" for r in rows) else 1
    if not rows:
        write_text(None, "All tickets are valid.\n")
        return 0
    for row in rows:
        loc = " (%s:%s)" % (row["source"], row["line"]) if row.get("source") else ""
        write_text(
            None,
            "[%s] %s: %s%s\n"
            % (row["severity"].upper(), row["code"], row["message"], loc),
        )
    return 0 if not any(r["severity"] == "error" for r in rows) else 1


def command_config_revision(args):
    """Print the exact revision of the configuration file.

    This is what ``--expected-revision`` compares against, so a script can read
    it, build its change, and write back without racing another writer.
    """
    from .config_writer import config_revision

    config = _config(args)
    target = getattr(args, "output", None) or config.get("_path")
    if not target:
        sys.stderr.write("ERROR: No configuration file to inspect.\n")
        return 1
    write_text(None, "%s\n" % config_revision(target))
    return 0


def command_config_explain(args):
    from .config_registry import explain_key

    entry = explain_key(args.path)
    if entry is None:
        sys.stderr.write("ERROR: No registered metadata for %s\n" % args.path)
        return 1
    write_text(None, "%s\n" % args.path)
    for key, value in entry.items():
        if value is None:
            continue
        label = key.replace("_", " ")
        write_text(None, "  %-16s %s\n" % (label + ":", value))
    return 0


def _config_without_runtime(config, injected_keys=None):
    data = OrderedDict()
    for key, value in (config or {}).items():
        if key in ("_path", "_active_workspace"):
            continue
        if injected_keys and key in injected_keys:
            continue
        data[key] = value
    return data


def _write_config_file(
    path,
    data,
    expected_revision=None,
    dry_run=False,
    require_revision=False,
    audit_log=None,
    audit_max_bytes=None,
):
    from .config_writer import write_config

    return write_config(
        path,
        data,
        expected_revision=expected_revision,
        dry_run=dry_run,
        require_revision=require_revision,
        audit_log=audit_log,
        audit_max_bytes=audit_max_bytes,
    )


def _config_write_section(config):
    config_section_value = config.get("config") if isinstance(config, dict) else None
    config_section_value = (
        config_section_value if isinstance(config_section_value, dict) else {}
    )
    write = config_section_value.get("write")
    return write if isinstance(write, dict) else {}


def _config_write_requires_revision(config):
    return _truthy_config(_config_write_section(config).get("require_revision"))


def _config_write_audit_settings(config):
    write = _config_write_section(config)
    return write.get("audit_log"), write.get("audit_max_bytes")


def _config_write_revision(args, config, target):
    """Expected revision for a config write, or None when CAS cannot apply.

    An explicit ``--expected-revision`` always wins. Otherwise the revision of
    the file that was actually loaded is used, so a concurrent writer between
    load and write is caught rather than silently overwritten. When ``--output``
    names a different file we never read it, so there is nothing to compare
    against and the write proceeds without a precondition.
    """
    explicit = getattr(args, "expected_revision", None)
    if explicit:
        return explicit
    source = (config or {}).get("_path")
    if not source or not target:
        return None
    if os.path.abspath(source) != os.path.abspath(target):
        return None
    from .config_writer import config_revision

    return config_revision(target)


def _commit_config(args, config, target, data):
    """Write configuration under compare-and-set. Returns ``(report, code)``."""
    from .config_writer import ConfigRevisionRequired, StaleConfigRevision

    audit_log, audit_max_bytes = _config_write_audit_settings(config)
    try:
        report = _write_config_file(
            target,
            data,
            _config_write_revision(args, config, target),
            require_revision=_config_write_requires_revision(config),
            audit_log=audit_log,
            audit_max_bytes=audit_max_bytes,
        )
    except ConfigRevisionRequired as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return None, 1
    except StaleConfigRevision as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        if exc.retained:
            sys.stderr.write("Your unwritten change was kept at %s\n" % exc.retained)
        return None, 1
    return report, 0


def _print_config_write_notes(report):
    if not report:
        return
    if report.get("revision"):
        write_text(None, "  revision: %s\n" % report["revision"])
    if report.get("backup"):
        write_text(None, "  backup: %s\n" % report["backup"])
    for row in report.get("warnings") or []:
        location = (" @ %s" % row["path"]) if row.get("path") else ""
        write_text(
            None, "  [WARNING] %s: %s%s\n" % (row["code"], row["message"], location)
        )


def _workspace_diag_line(row):
    return "  [%s] %s: %s" % (row["severity"].upper(), row["code"], row["message"])


def command_workspace_list(args):
    from .workspace import workspace_summaries

    summaries = workspace_summaries(_config(args))
    if getattr(args, "json", False):
        write_text(None, json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")
        return 0
    if not summaries:
        write_text(None, "No workspaces configured.\n")
        return 0
    for summary in summaries:
        marker = "*" if summary["default"] else " "
        tags = []
        if summary["legacy"]:
            tags.append("legacy")
        if not summary["ok"]:
            tags.append("has-errors")
        suffix = (" [%s]" % ", ".join(tags)) if tags else ""
        write_text(
            None,
            "%s %s  (%d source(s), %d file(s)) -> %s%s\n"
            % (
                marker,
                summary["name"],
                summary["source_count"],
                summary["input_count"],
                summary["write_file"] or "(none)",
                suffix,
            ),
        )
    return 0


def command_workspace_show(args):
    from .workspace import resolve_workspace

    try:
        resolution = resolve_workspace(
            _config(args),
            getattr(args, "name", None) or getattr(args, "workspace", None),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if getattr(args, "json", False):
        write_text(None, json.dumps(resolution, ensure_ascii=False, indent=2) + "\n")
        return 0
    write_text(
        None,
        "workspace: %s%s\n"
        % (resolution["name"], " (legacy)" if resolution["legacy"] else ""),
    )
    write_text(None, "base_dir: %s\n" % resolution["base_dir"])
    write_text(None, "write_file: %s\n" % (resolution["write_file"] or "(none)"))
    write_text(None, "sources:\n")
    for record in resolution["sources"]:
        write_text(
            None,
            "  - %s  role=%s writable=%s visible=%s priority=%d\n"
            % (
                record["path"],
                record["role"],
                record["writable"],
                record["default_visible"],
                record["priority"],
            ),
        )
    if resolution["diagnostics"]:
        write_text(None, "diagnostics:\n")
        for row in resolution["diagnostics"]:
            write_text(None, _workspace_diag_line(row) + "\n")
    return 0


def command_workspace_files(args):
    from .workspace import resolve_workspace

    try:
        resolution = resolve_workspace(
            _config(args),
            getattr(args, "name", None) or getattr(args, "workspace", None),
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    from .workspace import source_reason

    rows = []
    for record in resolution["sources"]:
        reason = source_reason(record)
        for path in record["files"]:
            rows.append(
                OrderedDict(
                    (
                        ("path", path),
                        ("role", record["role"]),
                        ("mode", "rw" if record["writable"] else "ro"),
                        ("origin", record["path"]),
                        ("matched_glob", record["matched_glob"]),
                        ("reason", reason),
                        ("exists", os.path.exists(path)),
                    )
                )
            )
    if getattr(args, "json", False):
        write_text(None, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if getattr(args, "resolved", False):
        for row in rows:
            write_text(
                None,
                "%s  role=%s mode=%s origin=%s exists=%s reason=(%s)\n"
                % (
                    row["path"],
                    row["role"],
                    row["mode"],
                    row["origin"],
                    row["exists"],
                    row["reason"],
                ),
            )
    else:
        for row in rows:
            write_text(None, "%s\n" % row["path"])
    return 0


def command_workspace_validate(args):
    from .workspace import resolve_workspace, iter_workspace_definitions

    config = _config(args)
    if getattr(args, "all", False):
        names = list(iter_workspace_definitions(config).keys())
    else:
        names = [getattr(args, "name", None) or getattr(args, "workspace", None)]
    reports = []
    overall_ok = True
    for name in names:
        try:
            resolution = resolve_workspace(config, name)
        except ValueError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 1
        overall_ok = overall_ok and resolution["ok"]
        reports.append(resolution)
    if getattr(args, "json", False):
        payload = [
            OrderedDict(
                (
                    ("name", r["name"]),
                    ("ok", r["ok"]),
                    ("diagnostics", r["diagnostics"]),
                )
            )
            for r in reports
        ]
        write_text(None, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0 if overall_ok else 1
    for resolution in reports:
        status = "OK" if resolution["ok"] else "ERRORS"
        write_text(None, "workspace %s: %s\n" % (resolution["name"], status))
        for row in resolution["diagnostics"]:
            write_text(None, _workspace_diag_line(row) + "\n")
    return 0 if overall_ok else 1


def command_tui(args):
    if getattr(args, "remote_clear_cache", False):
        if not getattr(args, "remote_url", None):
            sys.stderr.write("ERROR: --remote-clear-cache requires --remote-url.\n")
            return 1
        from .tui_remote_cache import clear_snapshot

        cleared = clear_snapshot(
            args.remote_url, username=getattr(args, "remote_user", None)
        )
        print("Offline cache cleared." if cleared else "No offline cache to clear.")
        return 0
    if getattr(args, "remote_url", None):
        # Remote mode never reads or defaults to a local life.txt; paths
        # are meaningless for a Web API-backed workspace (#677/#679).
        args.paths = list(args.paths or [])
    else:
        args.paths = _normalize_paths(
            args.paths, _config(args), stdin_when_empty=False
        ) or ["life.txt"]
    from .tui import cmd_tui

    return cmd_tui(args)


def command_fzf(args):
    args.paths = _normalize_paths(
        args.paths, _config(args), stdin_when_empty=False
    ) or ["life.txt"]
    from .fzf_helper import cmd_fzf

    return cmd_fzf(args)


def command_timer(args):
    config = _config(args)
    if getattr(args, "timer_command", None) == "summary":
        args.paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    elif getattr(args, "timer_command", None) == "status" and getattr(
        args, "paths", None
    ):
        args.paths = _normalize_paths(args.paths, config, stdin_when_empty=False)
    from .timer import cmd_timer

    return cmd_timer(args)


def command_stats(args):
    config = _config(args)
    args.paths = _normalize_paths(args.paths, config, stdin_when_empty=False) or [
        "life.txt"
    ]
    args.filter_items_func = _filter_items_from_args
    args.id_key = id_key_from_config(config)
    from .stats import cmd_stats

    return cmd_stats(args)


def command_lifecycle_stats(args):
    from .lifecycle_analytics import workspace_lifecycle_stats
    from .timezone_policy import resolve_timezone_name

    config = _config(args)
    paths = _normalize_paths(
        getattr(args, "paths", None), config, stdin_when_empty=False
    ) or ["life.txt"]
    items, _diagnostics = _parse_or_exit(paths, config)
    result = workspace_lifecycle_stats(
        items,
        id_key=id_key_from_config(config),
        limit=args.limit,
        since=args.since,
        until=args.until,
        duration=args.duration,
        timezone_name=resolve_timezone_name(config),
    )
    if args.coverage:
        result["analysis"] = "native_history_coverage"
        counts = {
            state: sum(1 for row in result["coverage"] if row["state"] == state)
            for state in ("complete", "partial", "none")
        }
        result["coverage_counts"] = counts
    if args.json:
        write_text(None, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        write_text(
            None,
            "Workspace Lifecycle Stats: %d item(s), %d with history\n"
            % (result["scanned_item_count"], result["items_with_native_history_count"]),
        )
        if args.duration:
            write_text(
                None, "  Duration distribution: %s\n" % result["duration_distribution"]
            )
    return 0


def command_git_hook(args):
    from .git_hook import cmd_git_hook

    return cmd_git_hook(args)


def command_completion(args):
    from .completion import cmd_completion

    return cmd_completion(args)


def command_assist_update(args):
    if args.interactive:
        raise ValueError("--interactive is not supported with --update.")
    if args.append:
        raise ValueError(
            "--append is only for creating new items. Use --output for update copies."
        )
    if not has_update_fields(args):
        raise ValueError("No update fields were specified.")

    text = read_text(args.update)
    updated_text, updated_line, diagnostics = update_text(text, args)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return 1
    if not args.no_check:
        _print_warnings(diagnostics)

    output = args.output if args.output else args.update
    _ensure_writable_path(output, _config(args), "assist --update")
    write_text(output, updated_text)
    write_text(None, updated_line + "\n")
    return 0


def _write_life_items(items, output, canonical=False, key="id"):
    text = _validated_life_text_or_exit(items, canonical=canonical, key=key)
    if text is None:
        return 1
    write_text(output, text)
    return 0


def _validated_life_text_or_exit(items, canonical=False, key="id"):
    if canonical:
        items = _canonical_hierarchy_items(items, key=key)
    diagnostics = []
    lines = []
    for item in items:
        diagnostics.extend(validate_item(item))
        lines.append(item_to_line(item))
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        return None
    _print_warnings(diagnostics)
    text = "\n".join(lines)
    if text:
        text += "\n"
    return text


def _items_to_life_text(items, canonical=False, key="id"):
    """Render items as native life.txt text.

    Delegates to lifetxt.native_codec (#689), the shared payload boundary
    also used by the sqlite (#691) and lifetxtz (#693) codecs, so this
    module keeps exactly one implementation of native rendering.
    """
    return native_codec.items_to_life_text(items, canonical=canonical, key=key)


def _canonical_hierarchy_items(items, key="id"):
    """Return item copies with explicit parent: links and no indentation."""
    return native_codec.canonical_hierarchy_items(items, key=key)


def _copy_item(item):
    return native_codec.copy_item(item)


def format_id_audit(audit, only="all"):
    lines = []
    cross_file_count = audit.get("cross_file_duplicate_count", 0)
    cross_file_note = (", %d cross-file" % cross_file_count) if cross_file_count else ""
    lines.append(
        "ID audit (%s): %d item(s), %d id(s), %d duplicate id(s)%s, %d missing id item(s)"
        % (
            audit.get("key", "id"),
            audit.get("total_items", 0),
            audit.get("id_count", 0),
            audit.get("duplicate_count", 0),
            cross_file_note,
            audit.get("missing_count", 0),
        )
    )

    if only in ("all", "duplicates"):
        lines.append("")
        lines.extend(_format_id_duplicate_section(audit.get("duplicates", [])))

    if only in ("all", "missing"):
        lines.append("")
        lines.extend(_format_id_missing_section(audit.get("missing", [])))

    if only == "present":
        lines.append("")
        lines.extend(_format_id_present_section(audit.get("present", [])))

    return "\n".join(lines).rstrip() + "\n"


def assign_missing_ids(paths, config, key, dry_run=False, backup=False, prefix=None):
    normalized = _normalize_paths(paths, config)
    if any(path == "-" for path in normalized):
        raise ValueError("ids --assign requires real file paths, not stdin.")

    existing = set()
    parsed_by_path = []
    for path in normalized:
        text = read_text(path)
        items, diagnostics = parse_text(text)
        if _has_error(diagnostics):
            raise ValueError(
                "Cannot assign IDs because %s has validation errors." % path
            )
        parsed_by_path.append((path, text, items))
        existing.update(collect_item_ids(items, key=key))

    records = []
    for path, text, _items in parsed_by_path:
        changed, new_text, path_records = _assign_missing_ids_in_text(
            path,
            text,
            key,
            existing,
            config,
            prefix,
        )
        records.extend(path_records)
        if changed and not dry_run:
            if backup:
                write_text(path + ".bak", text)
            write_text(path, new_text)
    return records


def _assign_missing_ids_in_text(path, text, key, existing, config, prefix=None):
    raw_lines = text.splitlines(True)
    changed = False
    records = []
    new_lines = []
    for line_no, raw_line in enumerate(raw_lines, 1):
        body, ending = split_line_ending(raw_line)
        item, diagnostics = parse_line(body, line_no)
        if item is None or _has_error(diagnostics) or item.details.get(key):
            new_lines.append(raw_line)
            continue
        assigned = ensure_item_id(
            item,
            existing_ids=existing,
            key=key,
            prefix=prefix or id_prefix_for_item(item, config),
        )
        new_line = item_to_line(item) + ending
        new_lines.append(new_line)
        changed = True
        records.append(
            OrderedDict(
                [
                    ("path", path),
                    ("line", line_no),
                    ("id", assigned),
                    ("type", item.kind),
                    ("status", item.status),
                    ("title", item.title),
                    ("text", item_to_line(item)),
                ]
            )
        )
    if not raw_lines and text:
        new_lines.append(text)
    return changed, "".join(new_lines), records


def format_id_assignments(records, dry_run=False):
    heading = "Planned ID assignments" if dry_run else "ID assignments"
    lines = ["%s: %d item(s)" % (heading, len(records))]
    if not records:
        return lines[0] + "\n"
    rows = []
    for record in records:
        rows.append(
            OrderedDict(
                [
                    ("path", record["path"]),
                    ("line", str(record["line"])),
                    ("id", record["id"]),
                    ("type", record["type"]),
                    ("title", record["title"]),
                ]
            )
        )
    lines.extend(_format_table(rows, ("path", "line", "id", "type", "title")))
    return "\n".join(lines) + "\n"


def _format_id_duplicate_section(records):
    lines = ["Duplicate IDs:"]
    if not records:
        lines.append("No duplicate IDs.")
        return lines
    rows = []
    for record in records:
        cross_marker = "*" if record.get("cross_file") else ""
        rows.append(
            OrderedDict(
                [
                    ("id", record["id"] + cross_marker),
                    ("count", str(record["count"])),
                    (
                        "locations",
                        "; ".join(item["location"] for item in record["items"]),
                    ),
                    ("titles", "; ".join(item["title"] for item in record["items"])),
                ]
            )
        )
    result = lines + _format_table(rows, ("id", "count", "locations", "titles"))
    if any(r.get("cross_file") for r in records):
        result.append("* = duplicate spans multiple files")
    return result


def _format_id_missing_section(records):
    lines = ["Missing IDs:"]
    if not records:
        lines.append("No missing IDs.")
        return lines
    rows = []
    for item in records:
        rows.append(
            OrderedDict(
                [
                    ("location", item["location"]),
                    ("type", item["type"]),
                    ("status", item["status"]),
                    ("title", item["title"]),
                ]
            )
        )
    return lines + _format_table(rows, ("location", "type", "status", "title"))


def _format_id_present_section(records):
    lines = ["Present IDs:"]
    if not records:
        lines.append("No IDs found.")
        return lines
    rows = []
    for record in records:
        rows.append(
            OrderedDict(
                [
                    ("id", record["id"]),
                    ("count", str(record["count"])),
                    (
                        "locations",
                        "; ".join(item["location"] for item in record["items"]),
                    ),
                ]
            )
        )
    return lines + _format_table(rows, ("id", "count", "locations"))


def _format_table(rows, columns):
    widths = []
    for column in columns:
        width = len(column)
        for row in rows:
            width = max(width, len(str(row.get(column, ""))))
        widths.append(width)
    lines = []
    lines.append(_format_table_row(columns, widths))
    lines.append(_format_table_row(["-" * width for width in widths], widths))
    for row in rows:
        lines.append(
            _format_table_row([row.get(column, "") for column in columns], widths)
        )
    return lines


def _format_table_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"


def _id_audit_output(audit, only):
    if only == "all":
        return audit
    data = OrderedDict()
    for key in (
        "key",
        "total_items",
        "id_count",
        "duplicate_count",
        "cross_file_duplicate_count",
        "missing_count",
    ):
        if key in audit:
            data[key] = audit[key]
    data[only] = audit[only]
    return data


def _id_audit_jsonl_records(audit, only):
    records = []
    if only == "all":
        records.append(
            OrderedDict(
                [
                    ("kind", "summary"),
                    ("key", audit["key"]),
                    ("total_items", audit["total_items"]),
                    ("id_count", audit["id_count"]),
                    ("duplicate_count", audit["duplicate_count"]),
                    (
                        "cross_file_duplicate_count",
                        audit.get("cross_file_duplicate_count", 0),
                    ),
                    ("missing_count", audit["missing_count"]),
                ]
            )
        )
    if only in ("all", "duplicates"):
        for record in audit["duplicates"]:
            entry = OrderedDict(record)
            entry["kind"] = "duplicate"
            records.append(entry)
    if only in ("all", "missing"):
        for item in audit["missing"]:
            entry = OrderedDict(item)
            entry["kind"] = "missing"
            records.append(entry)
    if only == "present":
        for record in audit["present"]:
            entry = OrderedDict(record)
            entry["kind"] = "present"
            records.append(entry)
    return records


def source_ownership_records(paths, config=None, key="id"):
    normalized = _normalize_paths(paths, config)
    records = []
    items = []
    diagnostics = []
    for source_index, path in enumerate(normalized, 1):
        source = "stdin" if path == "-" else path
        text = read_text(path)
        path_items, path_diagnostics = parse_text(
            text,
            id_key=key,
            check_ids=False,
            check_references=False,
        )
        _set_source(path_items, path_diagnostics, source)
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
        for item in path_items:
            records.append(_source_ownership_record(item, source, source_index, key))
    diagnostics.extend(duplicate_id_diagnostics(items, key=key))
    diagnostics.extend(reference_diagnostics(items, key=key))
    return records, diagnostics


def _source_ownership_record(item, source, source_index, key):
    id_values = [str(value) for value in item.details.get(key, []) if value]
    parent_values = [str(value) for value in item.details.get("parent", []) if value]
    record = OrderedDict()
    record["source"] = source
    record["source_index"] = source_index
    record["line"] = item.line
    record["end_line"] = getattr(item, "end_line", item.line) or item.line
    record["id_key"] = key
    record["id"] = id_values[0] if id_values else ""
    record["ids"] = id_values
    record["parent"] = parent_values[0] if parent_values else ""
    record["status"] = item.status
    record["type"] = item.kind
    record["title"] = item.title
    record["indent"] = item.indent
    record["detail_count"] = sum(len(values) for values in item.details.values())
    return record


def format_source_ownership_table(records, key):
    lines = [
        "Source ownership (%s): %d item(s) across %d source(s)"
        % (key, len(records), len(set(record["source"] for record in records)))
    ]
    if not records:
        return lines[0] + "\n"

    rows = []
    for record in records:
        line_value = str(record["line"])
        if record.get("end_line") and record["end_line"] != record["line"]:
            line_value = "%s-%s" % (record["line"], record["end_line"])
        rows.append(
            OrderedDict(
                [
                    ("source", record["source"]),
                    ("line", line_value),
                    ("id", record["id"]),
                    ("parent", record["parent"]),
                    ("type", record["type"]),
                    ("status", record["status"]),
                    ("title", record["title"]),
                ]
            )
        )
    lines.extend(
        _format_table(
            rows, ("source", "line", "id", "parent", "type", "status", "title")
        )
    )
    return "\n".join(lines) + "\n"


def _completed_parent_diagnostics(items, key="id"):
    """W225: completed/canceled parent has open children."""
    diagnostics = []
    _open_statuses = frozenset(("[ ]", "[/]", "[>]", "[?]"))
    _closed_statuses = frozenset(("[x]", "[-]"))

    id_to_item = {}
    for item in items:
        for val in item.details.get(key, []):
            id_to_item[str(val)] = item

    children_by_parent = {}
    for item in items:
        for parent_id in item.details.get("parent", []):
            pid = str(parent_id)
            children_by_parent.setdefault(pid, []).append(item)

    for parent_id, children in children_by_parent.items():
        parent = id_to_item.get(parent_id)
        if parent is None or parent.status not in _closed_statuses:
            continue
        open_children = [c for c in children if c.status in _open_statuses]
        if not open_children:
            continue
        child_ids = (
            ", ".join(str(v) for c in open_children for v in c.details.get(key, []))
            or "(no id)"
        )
        diagnostics.append(
            Diagnostic(
                "warning",
                "W225",
                "Completed/canceled parent %s:%s has %d open child(ren): %s."
                % (key, parent_id, len(open_children), child_ids),
                parent.line,
            )
        )
    return diagnostics


def _parse_or_exit(paths, config=None):
    items, diagnostics = _parse_life_inputs(paths, config)
    if _has_error(diagnostics):
        _print_diagnostics(diagnostics)
        raise SystemExit(1)
    return items, diagnostics


def _parse_life_inputs(paths, config=None):
    normalized = _normalize_paths(paths, config)
    include_source = len(normalized) > 1
    id_key = id_key_from_config(config or {})
    items = []
    diagnostics = []
    for path in normalized:
        text = read_text(path)
        path_items, path_diagnostics = parse_text(
            text,
            id_key=id_key,
            check_ids=False,
            check_references=False,
        )
        if include_source or path != "-":
            source = "stdin" if path == "-" else path
            _set_source(path_items, path_diagnostics, source)
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
    diagnostics.extend(duplicate_id_diagnostics(items, key=id_key))
    diagnostics.extend(reference_diagnostics(items, key=id_key))
    diagnostics.extend(_completed_parent_diagnostics(items, key=id_key))
    if config and config.get("custom_fields"):
        from .custom_fields import generic_custom_field_diagnostics

        diagnostics = generic_custom_field_diagnostics(items, diagnostics, config)
    return items, diagnostics


def _set_source(items, diagnostics, source):
    for item in items:
        item.source = source
    for diagnostic in diagnostics:
        diagnostic.source = source


def _filter_items_from_args(items, args):
    range_start, range_end = parse_optional_time_range(
        after_text=getattr(args, "after", None),
        before_text=getattr(args, "before", None),
    )
    config = _config(args)
    return filter_items(
        items,
        open_only=getattr(args, "open", False),
        statuses=getattr(args, "status", None),
        kinds=getattr(args, "kinds", None),
        projects=getattr(args, "project", None),
        tags=getattr(args, "tag", None),
        tag_all=getattr(args, "tag_all", None),
        exclude_tags=getattr(args, "exclude_tag", None),
        users=getattr(args, "user", None),
        persons=getattr(args, "person", None),
        owners=getattr(args, "owner", None),
        assignees=getattr(args, "assignee", None),
        attendees=getattr(args, "attendee", None),
        senders=getattr(args, "sender", None),
        recipients=getattr(args, "recipient", None),
        teams=getattr(args, "team", None),
        detail_filters=getattr(args, "detail", None),
        text=getattr(args, "text", None),
        range_start=range_start,
        range_end=range_end,
        user_aliases=config_user_aliases(config),
        team_members=config_team_members(config),
        team_aliases=config_team_aliases(config),
        tag_aliases=config_tag_aliases(config),
    )


def apply_config_defaults_to_item(item, args, directives=None):
    config = _config(args)
    directives = directives or {}

    if item.kind == "S" and "person" not in item.details:
        defaults = config_section(config, "defaults")
        user_section = config_section(config, "user")
        message_section = config_section(config, "message")
        configured_person = (
            defaults.get("person")
            or user_section.get("name")
            or message_section.get("default_sender")
        )
        person = configured_person or directives.get("self") or "self"
        item.details["person"] = [str(person)]

    if "project" not in item.details:
        defaults = config_section(config, "defaults")
        project = defaults.get("project") or directives.get("project")
        if project:
            item.details["project"] = [str(project)]

    if item.kind == "M":
        message = config_section(config, "message")
        sender = message.get("default_sender") or config_user_name(config)
        if sender and "sender" not in item.details:
            item.details["sender"] = [str(sender)]

        channel = message.get("default_channel")
        if channel and "channel" not in item.details:
            item.details["channel"] = [str(channel)]

        service = message.get("default_service")
        if service and "service" not in item.details:
            item.details["service"] = [str(service)]


def apply_auto_id_to_item(item, args):
    config = _config(args)
    if not auto_ids_enabled(config):
        return None

    key = id_key_from_config(config)
    if item.details.get(key):
        return item.details[key][0]

    existing = collect_item_ids(_auto_id_scan_items(args), key=key)
    return ensure_item_id(
        item,
        existing_ids=existing,
        key=key,
        prefix=id_prefix_for_item(item, config),
    )


def _auto_id_scan_items(args):
    items = []
    for path in _auto_id_scan_paths(args):
        if not path or path == "-" or not os.path.exists(path):
            continue
        path_items, _diagnostics = parse_text(read_text(path))
        items.extend(path_items)
    return items


def _auto_id_scan_paths(args):
    config = _config(args)
    candidates = []
    for path in config_paths(config) or []:
        candidates.append(path)
    write_file = config_write_file(config)
    if write_file:
        candidates.append(write_file)
    output = getattr(args, "output", None)
    append = getattr(args, "append", None)
    if output:
        candidates.append(output)
    if append:
        candidates.append(append)

    paths = []
    seen = set()
    for path in candidates:
        key = os.path.abspath(path) if path not in (None, "-") else path
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return expand_paths(paths, stdin_when_empty=False)


def _config(args):
    return getattr(args, "config_data", None) or {}


def _workspace_resolution_active(config, workspace_name):
    from .workspace import workspace_resolution_active

    return workspace_resolution_active(config, workspace_name)


def _maybe_apply_workspace(args):
    """Inject resolved workspace inputs/write target into the loaded config.

    Legacy top-level ``paths`` / ``write_file`` configurations are left byte
    identical: resolution only activates when a workspace is requested with
    ``--workspace`` or the config declares ``workspaces`` / ``default_workspace``.
    Downstream ``config_paths`` / ``config_write_file`` then transparently see
    the resolved sources without every command needing to change.

    The keys this function actually overwrites or adds are recorded on
    ``args._workspace_injected_keys`` so a later configuration *write* (
    ``config set|unset|migrate``) can exclude them: they are resolution
    output, not user-declared content, and must never be persisted back to
    the file (#136).
    """
    config = getattr(args, "config_data", None)
    workspace_name = getattr(args, "workspace", None)
    if not config or not _workspace_resolution_active(config, workspace_name):
        return
    from .workspace import resolve_workspace

    resolution = resolve_workspace(config, workspace_name or None)
    injected_keys = set()
    config["paths"] = list(resolution["input_paths"])
    injected_keys.add("paths")
    if resolution["write_file"]:
        config["write_file"] = resolution["write_file"]
        injected_keys.add("write_file")
    if resolution["generated_paths"] and "generated_paths" not in config:
        config["generated_paths"] = list(resolution["generated_paths"])
        injected_keys.add("generated_paths")
    config["_active_workspace"] = resolution["name"]
    args._workspace_injected_keys = injected_keys


def _config_generated_paths(config):
    values = []
    if config:
        raw = config.get("generated_paths")
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, (list, tuple)):
            values.extend(str(value) for value in raw if str(value))
        sync_raw = config_section(config, "sync_ics").get("generated_paths")
        if isinstance(sync_raw, str):
            values.append(sync_raw)
        elif isinstance(sync_raw, (list, tuple)):
            values.extend(str(value) for value in sync_raw if str(value))
    return values


def _ensure_writable_path(path, config, operation, allow_generated=False):
    if not path or path == "-":
        return
    abs_path = os.path.abspath(path)
    if not allow_generated and _path_matches_config_patterns(
        abs_path, _config_generated_paths(config), config
    ):
        raise ValueError("%s refuses to modify generated file: %s" % (operation, path))
    if os.path.exists(path):
        import stat

        mode = os.stat(path).st_mode
        if not (mode & stat.S_IWRITE):
            raise ValueError(
                "%s refuses to modify read-only file: %s" % (operation, path)
            )
        if not os.access(path, os.W_OK):
            raise ValueError(
                "%s refuses to modify non-writable file: %s" % (operation, path)
            )


def _path_matches_config_patterns(abs_path, patterns, config):
    if not patterns:
        return False
    import fnmatch

    bases = [os.getcwd()]
    config_path = config.get("_path") if config else None
    if config_path:
        bases.insert(0, os.path.dirname(os.path.abspath(config_path)) or os.getcwd())
    target = os.path.normcase(abs_path)
    for pattern in patterns:
        candidates = []
        if os.path.isabs(pattern):
            candidates.append(os.path.abspath(pattern))
        else:
            for base in bases:
                candidates.append(os.path.abspath(os.path.join(base, pattern)))
        for candidate in candidates:
            normalized = os.path.normcase(candidate)
            if target == normalized or fnmatch.fnmatch(target, normalized):
                return True
    return False


def _sync_config(args):
    return config_section(_config(args), "sync_ics")


def _public_config(config):
    if isinstance(config, dict):
        data = {}
        for key, value in config.items():
            if key == "_path":
                continue
            data[key] = _public_config(value)
        return data
    if isinstance(config, list):
        return [_public_config(value) for value in config]
    return config


def _items_from_json_paths(paths):
    items = []
    for path in _normalize_paths(paths):
        items.extend(items_from_json_text(read_text(path)))
    return items


def _items_from_jsonl_paths(paths):
    items = []
    for path in _normalize_paths(paths):
        items.extend(items_from_jsonl_text(read_text(path)))
    return items


def _items_from_csv_paths(paths):
    items = []
    for path in _normalize_paths(paths):
        items.extend(items_from_csv_text(read_text(path)))
    return items


def _normalize_paths(paths, config=None, stdin_when_empty=True):
    if paths is None:
        configured = config_paths(config)
        if configured:
            return expand_paths(configured, stdin_when_empty=stdin_when_empty)
        return ["-"] if stdin_when_empty else []
    if isinstance(paths, str):
        return expand_paths([paths], stdin_when_empty=stdin_when_empty)
    paths = list(paths)
    if not paths:
        configured = config_paths(config)
        if configured:
            return expand_paths(configured, stdin_when_empty=stdin_when_empty)
        return ["-"] if stdin_when_empty else []
    return expand_paths(paths, stdin_when_empty=stdin_when_empty)


def read_text(path):
    if path is None or path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def write_text(path, text):
    if path is None:
        _write_console_text(sys.stdout, text)
        return
    atomic_write_text(path, text)


def atomic_write_text(path, text):
    ensure_parent_dir(path)
    _shared_atomic_write_text(path, text)


def write_bytes(path, data):
    ensure_parent_dir(path)
    _shared_atomic_write_bytes(path, data)


def ensure_parent_dir(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def append_line(path, line):
    append_text(path, line + "\n")


def append_text(path, text):
    if not text:
        return
    from .write_operations import append_text as semantic_append_text

    return semantic_append_text(path, text, operation="cli.append", create=True)


def _undo_cache_dir(config):
    undo_cfg = config_section(config, "undo")
    return undo_cfg.get("dir") or os.path.join(".cache", "lifetxt", "undo")


def _backup_cache_dir(config):
    backup_cfg = config_section(config, "backup")
    return backup_cfg.get("dir") or os.path.join(".cache", "lifetxt", "backup")


def _undo_keep(config):
    undo_cfg = config_section(config, "undo")
    keep = undo_cfg.get("keep", 20)
    try:
        return max(1, int(keep))
    except (TypeError, ValueError):
        return 20


def _evict_old_snapshots(directory, keep=20):
    try:
        entries = sorted(os.listdir(directory))
        excess = entries[: max(0, len(entries) - keep)]
        for name in excess:
            try:
                os.unlink(os.path.join(directory, name))
            except OSError:
                pass
    except OSError:
        pass


def _pre_write_backup(path, config, op):
    """Save current file content as an undo snapshot before a write operation."""
    if not path or path == "-":
        return
    try:
        content = read_text(path)
    except FileNotFoundError:
        return

    ts = local_now_naive().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(path)

    undo_root = _undo_cache_dir(config)
    undo_dir = os.path.join(undo_root, basename)
    snapshot_name = "%s.%s.txt" % (ts, op)
    snapshot_path = os.path.join(undo_dir, snapshot_name)
    try:
        ensure_parent_dir(snapshot_path)
        with open(snapshot_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        _evict_old_snapshots(undo_dir, keep=_undo_keep(config))
    except OSError:
        pass

    backup_cfg = config_section(config, "backup")
    if backup_cfg.get("auto"):
        backup_root = _backup_cache_dir(config)
        backup_dir = os.path.join(backup_root, basename)
        backup_path = os.path.join(backup_dir, "%s.txt" % ts)
        try:
            ensure_parent_dir(backup_path)
            with open(backup_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
            keep_b = backup_cfg.get("keep", 20)
            try:
                keep_b = max(1, int(keep_b))
            except (TypeError, ValueError):
                keep_b = 20
            _evict_old_snapshots(backup_dir, keep=keep_b)
        except OSError:
            pass


def split_line_ending(line):
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def fetch_url(url, timeout, user_agent, index):
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        raise ValueError(
            "Failed to fetch iCalendar source #%d: HTTP %s." % (index, exc.code)
        )
    except URLError as exc:
        raise ValueError(
            "Failed to fetch iCalendar source #%d: %s." % (index, exc.reason)
        )
    except OSError as exc:
        raise ValueError("Failed to fetch iCalendar source #%d: %s." % (index, exc))


def decode_ics_bytes(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _ics_sync_sources(args):
    sources = []
    for url in args.url:
        sources.append({"kind": "url", "name": "url", "url": url})
    for env_name in args.url_env:
        url = os.environ.get(env_name)
        if not url:
            raise ValueError("Environment variable %s is not set or empty." % env_name)
        sources.append({"kind": "env", "name": env_name, "url": url})
    for source in _sync_config(args).get("sources", []) or []:
        if not isinstance(source, dict):
            raise ValueError("sync_ics.sources entries must be objects.")
        url = source.get("url")
        kind = "url"
        name = source.get("name") or "config"
        if not url and source.get("url_env"):
            env_name = source.get("url_env")
            url = os.environ.get(env_name)
            kind = "env"
            name = env_name
            if not url:
                raise ValueError(
                    "Environment variable %s is not set or empty." % env_name
                )
        if not url:
            raise ValueError("sync_ics.sources entry requires url or url_env.")
        tags = source.get("tags", source.get("tag", []))
        if isinstance(tags, str):
            tags = [tags]
        sources.append(
            {
                "kind": kind,
                "name": name,
                "url": url,
                "project": source.get("project"),
                "tags": tags,
            }
        )
    if not sources:
        raise ValueError("Specify at least one --url or --url-env.")
    return sources


def _ics_cache_name(source, index):
    digest = hashlib.sha256(source["url"].encode("utf-8")).hexdigest()[:12]
    if source["kind"] == "env":
        base = _safe_cache_part(source["name"])
    else:
        base = "source_%d" % index
    return "%s_%s.ics" % (base, digest)


def _safe_cache_part(value):
    chars = []
    for char in value:
        if char.isalnum() or char in ("-", "_"):
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars) or "source"


def _exit_code(diagnostics, warnings_as_errors):
    has_warning = False
    for diagnostic in diagnostics:
        if diagnostic.severity == "error":
            return 1
        if diagnostic.severity == "warning":
            has_warning = True
    if warnings_as_errors and has_warning:
        return 1
    return 0


def filter_diagnostics(
    diagnostics, severities=None, codes=None, categories=None, ignore_codes=None
):
    severity_filter = _diagnostic_severity_filter(severities)
    code_filter = _diagnostic_code_filter(codes)
    category_filter = _diagnostic_category_filter(categories)
    ignore_set = set(c.upper() for c in _split_csv_args(ignore_codes))

    filtered = []
    for diagnostic in diagnostics:
        if ignore_set and str(diagnostic.code).upper() in ignore_set:
            continue
        if severity_filter and str(diagnostic.severity).lower() not in severity_filter:
            continue
        if code_filter and str(diagnostic.code).upper() not in code_filter:
            continue
        if category_filter and diagnostic_category(diagnostic) not in category_filter:
            continue
        filtered.append(diagnostic)
    return filtered


def _diagnostic_severity_filter(values):
    severities = set(value.lower() for value in _split_csv_args(values))
    allowed = set(("error", "warning"))
    invalid = sorted(severities - allowed)
    if invalid:
        raise ValueError("Unknown diagnostic severity: %s." % ", ".join(invalid))
    return severities


def _diagnostic_code_filter(values):
    return set(value.upper() for value in _split_csv_args(values))


def _diagnostic_category_filter(values):
    categories = set(value.lower() for value in _split_csv_args(values))
    allowed = set(DIAGNOSTIC_CATEGORIES)
    invalid = sorted(categories - allowed)
    if invalid:
        raise ValueError("Unknown diagnostic category: %s." % ", ".join(invalid))
    return categories


def _has_error(diagnostics):
    for diagnostic in diagnostics:
        if diagnostic.severity == "error":
            return True
    return False


def _print_diagnostics(diagnostics):
    for diagnostic in diagnostics:
        sys.stderr.write(diagnostic.format() + "\n")


def _print_warnings(diagnostics):
    for diagnostic in diagnostics:
        if diagnostic.severity == "warning":
            sys.stderr.write(diagnostic.format() + "\n")


def command_deps(args):
    config = _config(args)
    id_key = id_key_from_config(config)
    paths = args.paths if args.paths else ["-"]
    items, diags = _parse_or_exit(paths, config)
    _print_warnings(diags)
    roots = dependency_chain_records(
        items,
        key=id_key,
        root_id=getattr(args, "root", None),
        blocked_only=getattr(args, "blocked", False),
        max_depth=getattr(args, "depth", None),
    )

    if args.format == "json":
        write_text(
            None,
            json.dumps(
                roots,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                separators=None if args.pretty else (",", ":"),
            )
            + "\n",
        )
        return 0

    if args.format == "mermaid":
        write_text(None, dependency_chains_to_mermaid(roots))
        return 0

    if args.format == "dot":
        write_text(None, dependency_chains_to_dot(roots))
        return 0

    write_text(None, format_dependency_chain(roots))
    return 0


def command_tag_list(args):
    config = _config(args)
    paths = args.paths if args.paths else ["-"]
    items, diags = _parse_or_exit(paths, config)
    _print_warnings(diags)
    counts = {}
    for item in items:
        for tag in item.details.get("tag", []):
            counts[tag] = counts.get(tag, 0) + 1
    sorted_tags = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    fmt = getattr(args, "format", "text")
    if fmt == "json":
        write_text(
            None,
            json.dumps(
                [{"tag": t, "count": c} for t, c in sorted_tags],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    else:
        if not sorted_tags:
            sys.stdout.write("No tags found.\n")
        else:
            for tag, count in sorted_tags:
                sys.stdout.write("%4d  %s\n" % (count, tag))
    return 0


def command_tag_rename(args):
    old_tag = args.old
    new_tag = args.new
    path = args.path
    dry_run = getattr(args, "dry_run", False)
    text = read_text(path)
    id_key = id_key_from_config(_config(args))
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    lines = text.splitlines(keepends=True)
    changed = 0
    import re as _re

    for item in items:
        if old_tag in item.details.get("tag", []):
            ln = item.line
            if ln and 0 < ln <= len(lines):
                new_line = _re.sub(
                    r"(\btag:\s*)" + _re.escape(old_tag) + r"(\b|$)",
                    r"\g<1>" + new_tag,
                    lines[ln - 1],
                )
                if new_line != lines[ln - 1]:
                    lines[ln - 1] = new_line
                    changed += 1
    if changed == 0:
        sys.stdout.write("Tag %r not found in %s.\n" % (old_tag, path))
        return 0
    new_text = "".join(lines)
    if dry_run:
        sys.stdout.write(
            "Would rename %d occurrence(s) of tag %r -> %r in %s.\n"
            % (changed, old_tag, new_tag, path)
        )
    else:
        _ensure_writable_path(path, _config(args), "tag rename")
        atomic_write_text(path, new_text)
        sys.stdout.write(
            "Renamed %d occurrence(s) of tag %r -> %r in %s.\n"
            % (changed, old_tag, new_tag, path)
        )
    return 0


def command_watch(args):
    import time

    paths = args.paths if args.paths else ["-"]
    run_cmd = getattr(args, "run", "summary")
    interval = getattr(args, "interval", 1.0)
    do_clear = getattr(args, "clear", False)
    show_timestamp = getattr(args, "timestamp", False)
    do_notify = getattr(args, "notify", False)
    last_exit = [None]

    if "-" in paths:
        sys.stderr.write("ERROR: watch does not support stdin. Specify file paths.\n")
        return 1

    def _mtimes():
        result = {}
        for p in paths:
            try:
                result[p] = os.path.getmtime(p)
            except OSError:
                result[p] = None
        return result

    def _rerun():
        if do_clear:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
        import subprocess

        cmd = [sys.executable, "-m", "lifetxt"] + [run_cmd] + paths
        if show_timestamp:
            sys.stdout.write(
                "\n[watch] %s  running: %s\n"
                % (local_now_naive().isoformat(timespec="seconds"), " ".join(cmd))
            )
            sys.stdout.flush()
        try:
            result = subprocess.run(cmd)
            exit_code = result.returncode
            if exit_code:
                marker = "[watch] command exited with %d" % exit_code
                if sys.stderr.isatty():
                    marker = "\033[31m%s\033[0m" % marker
                sys.stderr.write(marker + "\n")
            if do_notify and last_exit[0] is not None and exit_code != last_exit[0]:
                _watch_status_notify(run_cmd, exit_code)
            last_exit[0] = exit_code
        except Exception as exc:
            sys.stderr.write("Watch run error: %s\n" % exc)
            if do_notify:
                _watch_status_notify(run_cmd, 1, message=str(exc))

    sys.stdout.write("Watching %s (Ctrl-C to stop)...\n" % ", ".join(paths))
    last_mtimes = _mtimes()
    _rerun()
    try:
        while True:
            time.sleep(interval)
            current_mtimes = _mtimes()
            if current_mtimes != last_mtimes:
                last_mtimes = current_mtimes
                _rerun()
    except KeyboardInterrupt:
        sys.stdout.write("\nStopped.\n")
    return 0


def _watch_status_notify(command_name, exit_code, message=None):
    text = message or ("lifetxt %s exited with %d" % (command_name, exit_code))
    try:
        from .notifier import notify_desktop

        if notify_desktop({"title": "lifetxt watch", "body": text}):
            return
    except Exception:
        pass
    sys.stdout.write("\a")
    sys.stdout.flush()


def command_tag_merge(args):
    old_tag = args.old
    new_tag = args.new
    path = args.path
    dry_run = getattr(args, "dry_run", False)
    config = _config(args)
    from .write_operations import merge_tag_and_alias
    from .transaction_journal import journal_directory

    # Dry-run computes the semantic transform against an isolated temporary copy.
    if dry_run:
        from .write_operations import transform_items_text

        text = read_text(path)
        id_key = id_key_from_config(config)
        items, diagnostics = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )
        if _has_error(diagnostics):
            _print_diagnostics(diagnostics)
            return 1
        changes = []
        for item in items:
            values = [str(value) for value in item.details.get("tag", [])]
            if old_tag not in values:
                continue
            ids = item.details.get(id_key) or []
            if not ids:
                raise ValueError("Cannot merge tag on an item without %s:." % id_key)
            merged = []
            for value in values:
                candidate = new_tag if value == old_tag else value
                if candidate not in merged:
                    merged.append(candidate)
            changes.append({"id": str(ids[0]), "set_details": {"tag": merged}})
        if not changes:
            sys.stdout.write("Tag %r not found in %s.\n" % (old_tag, path))
            return 0
        transform_items_text(text, changes, id_key=id_key)
        sys.stdout.write(
            "Would merge %d item(s): tag %r -> %r in %s.\n"
            % (len(changes), old_tag, new_tag, path)
        )
        return 0

    _ensure_writable_path(path, config, "tag merge")
    config_path = getattr(args, "config", None) or ".lifetxt.json"
    result, changed = merge_tag_and_alias(
        path,
        old_tag,
        new_tag,
        config_path=config_path,
        life_revision=getattr(args, "revision", None),
        config_revision=getattr(args, "config_revision", None),
        id_key=id_key_from_config(config),
        journal_dir=journal_directory(config, writable_path=path),
        config=config,
    )
    if changed == 0:
        sys.stdout.write("Tag %r not found in %s.\n" % (old_tag, path))
        return 0
    sys.stdout.write(
        "Merged %d item(s): tag %r -> %r in %s.\n" % (changed, old_tag, new_tag, path)
    )
    sys.stdout.write(
        "Updated alias in %s (transaction %s).\n" % (config_path, result.transaction_id)
    )
    return 0


def _derive_key(passphrase, salt, length=32):
    import hashlib

    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, 100000, dklen=length
    )


def _xsk_encrypt(plaintext, passphrase):
    import hashlib, hmac as _hmac, secrets, base64

    salt = secrets.token_bytes(16)
    key = _derive_key(passphrase, salt)
    pt = plaintext.encode("utf-8")
    keystream = b""
    counter = 0
    while len(keystream) < len(pt):
        keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        counter += 1
    ciphertext = bytes(a ^ b for a, b in zip(pt, keystream[: len(pt)]))
    payload = salt + ciphertext
    mac = _hmac.new(key, payload, "sha256").digest()
    encoded = base64.b64encode(mac + payload).decode("ascii")
    return "enc:XSK:" + encoded


def _xsk_decrypt(enc_value, passphrase):
    import hashlib, hmac as _hmac, base64

    parts = enc_value.split(":", 2)
    if len(parts) != 3 or parts[0] != "enc" or parts[1] != "XSK":
        raise ValueError("Not an XSK-encrypted value: %r" % enc_value)
    raw = base64.b64decode(parts[2])
    if len(raw) < 48:
        raise ValueError("Truncated ciphertext.")
    mac = raw[:32]
    payload = raw[32:]
    salt = payload[:16]
    ciphertext = payload[16:]
    key = _derive_key(passphrase, salt)
    expected_mac = _hmac.new(key, payload, "sha256").digest()
    if not _hmac.compare_digest(mac, expected_mac):
        raise ValueError("MAC mismatch — wrong passphrase or tampered data.")
    keystream = b""
    counter = 0
    while len(keystream) < len(ciphertext):
        keystream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(
        a ^ b for a, b in zip(ciphertext, keystream[: len(ciphertext)])
    ).decode("utf-8")


def _aesgcm_key(passphrase, salt):
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as exc:
        raise ValueError(
            "AES-GCM requires the optional 'cryptography' package."
        ) from exc
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200000,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _aesgcm_encrypt(plaintext, passphrase):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ValueError(
            "AES-GCM requires the optional 'cryptography' package."
        ) from exc
    import base64
    import secrets

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _aesgcm_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return "enc:GCM:" + base64.b64encode(salt + nonce + ciphertext).decode("ascii")


def _aesgcm_decrypt(enc_value, passphrase):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ValueError(
            "AES-GCM requires the optional 'cryptography' package."
        ) from exc
    import base64

    parts = enc_value.split(":", 2)
    if len(parts) != 3 or parts[0] != "enc" or parts[1] != "GCM":
        raise ValueError("Not a GCM-encrypted value: %r" % enc_value)
    raw = base64.b64decode(parts[2])
    if len(raw) < 44:
        raise ValueError("Truncated AES-GCM ciphertext.")
    salt = raw[:16]
    nonce = raw[16:28]
    ciphertext = raw[28:]
    key = _aesgcm_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")


def _encrypt_field_value(plaintext, passphrase, algorithm):
    if algorithm == "xsk":
        return _xsk_encrypt(plaintext, passphrase)
    if algorithm == "aesgcm":
        return _aesgcm_encrypt(plaintext, passphrase)
    raise ValueError("Unsupported encryption algorithm: %s" % algorithm)


def _decrypt_field_value(enc_value, passphrase, algorithm="auto"):
    if algorithm == "auto":
        if enc_value.startswith("enc:XSK:"):
            algorithm = "xsk"
        elif enc_value.startswith("enc:GCM:"):
            algorithm = "aesgcm"
        else:
            raise ValueError("Unsupported encrypted value tag: %r" % enc_value)
    if algorithm == "xsk":
        return _xsk_decrypt(enc_value, passphrase)
    if algorithm == "aesgcm":
        return _aesgcm_decrypt(enc_value, passphrase)
    raise ValueError("Unsupported encryption algorithm: %s" % algorithm)


def _read_passphrase_arg(args):
    key_file = getattr(args, "key_file", None)
    key_env = getattr(args, "key_env", "LIFETXT_KEY")
    if key_file:
        passphrase = read_text(key_file).strip()
        if not passphrase:
            sys.stderr.write("ERROR: Passphrase file is empty: %s\n" % key_file)
            return ""
        return passphrase
    passphrase = os.environ.get(key_env, "")
    if not passphrase:
        sys.stderr.write(
            "ERROR: Passphrase not set. Set environment variable %s or use --key-file.\n"
            % key_env
        )
    return passphrase


def command_encrypt(args):
    import re as _re

    path = args.path
    fields = args.fields or ["body", "note"]
    kinds = set(args.kinds or [])
    algorithm = getattr(args, "algorithm", "xsk")
    dry_run = getattr(args, "dry_run", False)
    do_backup = getattr(args, "backup", False)
    passphrase = _read_passphrase_arg(args)
    if not passphrase:
        return 1
    text = read_text(path)
    id_key = id_key_from_config({})
    items, _ = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    lines = text.splitlines(keepends=True)
    total_changed = 0
    for item in items:
        if kinds and item.kind not in kinds:
            continue
        for field in fields:
            for val in item.details.get(field, []):
                sv = str(val)
                if sv.startswith("enc:"):
                    continue
                try:
                    enc_val = _encrypt_field_value(sv, passphrase, algorithm)
                except ValueError as exc:
                    sys.stderr.write("ERROR: %s\n" % exc)
                    return 1
                ln = item.line
                if ln and 0 < ln <= len(lines):
                    pattern = r"(\b" + _re.escape(field) + r":)" + _re.escape(sv)
                    new_line = _re.sub(
                        pattern, r"\g<1>" + enc_val, lines[ln - 1], count=1
                    )
                    if new_line != lines[ln - 1]:
                        lines[ln - 1] = new_line
                        total_changed += 1
    if dry_run:
        sys.stdout.write(
            "[dry-run] Would encrypt %d field value(s) in %s.\n" % (total_changed, path)
        )
        return 0
    if total_changed == 0:
        sys.stdout.write("No fields to encrypt (already encrypted or not found).\n")
        return 0
    _ensure_writable_path(path, _config(args), "encrypt")
    if do_backup:
        import shutil as _sh

        _sh.copy2(path, path + ".bak")
    atomic_write_text(path, "".join(lines))
    sys.stdout.write("Encrypted %d field value(s) in %s.\n" % (total_changed, path))
    return 0


def command_decrypt(args):
    import re as _re

    path = args.path
    fields_filter = set(args.fields or [])
    algorithm = getattr(args, "algorithm", "auto")
    dry_run = getattr(args, "dry_run", False)
    do_backup = getattr(args, "backup", False)
    passphrase = _read_passphrase_arg(args)
    if not passphrase:
        return 1
    text = read_text(path)
    lines = text.splitlines(keepends=True)
    total_changed = 0
    errors = 0
    ENC_RE = _re.compile(r"\b([\w-]+):(enc:(?:XSK|GCM):[A-Za-z0-9+/=]+)")
    for i, line in enumerate(lines):
        new_line = line
        for m in ENC_RE.finditer(line):
            field_key = m.group(1)
            enc_val = m.group(2)
            if fields_filter and field_key not in fields_filter:
                continue
            try:
                plaintext = _decrypt_field_value(enc_val, passphrase, algorithm)
                new_line = new_line.replace(enc_val, plaintext, 1)
                total_changed += 1
            except Exception as exc:
                sys.stderr.write(
                    "WARNING: line %d field %r: %s\n" % (i + 1, field_key, exc)
                )
                errors += 1
        lines[i] = new_line
    if dry_run:
        sys.stdout.write(
            "[dry-run] Would decrypt %d field value(s) in %s.\n" % (total_changed, path)
        )
        return 0
    if total_changed == 0:
        sys.stdout.write("No encrypted fields found.\n")
        return 1 if errors else 0
    _ensure_writable_path(path, _config(args), "decrypt")
    if do_backup:
        import shutil as _sh

        _sh.copy2(path, path + ".bak")
    atomic_write_text(path, "".join(lines))
    sys.stdout.write("Decrypted %d field value(s) in %s.\n" % (total_changed, path))
    return 1 if errors else 0


def _share_range_label(args):
    today = timezone_today()
    if getattr(args, "week", False):
        start = today - datetime.timedelta(days=today.weekday())
        end = start + datetime.timedelta(days=6)
        return "%s to %s" % (start.isoformat(), end.isoformat())
    if getattr(args, "month", None):
        import calendar as _calendar

        try:
            year_s, month_s = args.month.split("-")
            year_i, month_i = int(year_s), int(month_s)
            start = datetime.date(year_i, month_i, 1)
            last_day = _calendar.monthrange(year_i, month_i)[1]
            end = datetime.date(year_i, month_i, last_day)
        except (ValueError, AttributeError):
            raise ValueError("Invalid --month format. Use YYYY-MM.")
        return "%s to %s" % (start.isoformat(), end.isoformat())
    return "all matching items"


def _share_plot_data(items):
    from .timeutil import parse_elapsed as _parse_elapsed

    status_counts = OrderedDict()
    project_counts = OrderedDict()
    elapsed_by_project = OrderedDict()
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        project = (
            str(item.details.get("project", [""])[0])
            if item.details.get("project")
            else "(no project)"
        )
        project_counts[project] = project_counts.get(project, 0) + 1
        elapsed_vals = item.details.get("elapsed", [])
        if elapsed_vals:
            minutes = _parse_elapsed(str(elapsed_vals[0]))
            if minutes:
                elapsed_by_project[project] = (
                    elapsed_by_project.get(project, 0) + minutes
                )

    plot_data = OrderedDict()
    if status_counts:
        plot_data["Items by status"] = OrderedDict(
            sorted(status_counts.items(), key=lambda kv: -kv[1])
        )
    if project_counts:
        plot_data["Items by project"] = OrderedDict(
            sorted(project_counts.items(), key=lambda kv: -kv[1])
        )
    if elapsed_by_project:
        plot_data["Elapsed minutes by project"] = OrderedDict(
            sorted(elapsed_by_project.items(), key=lambda kv: -kv[1])
        )
    return plot_data


def _share_to_html(title, range_label, items, plot_data):
    def esc(value):
        return html.escape(str(value), quote=True)

    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>%s</title>" % esc(title),
        "<style>",
        "body{font-family:system-ui,-apple-system,sans-serif;line-height:1.5;max-width:960px;margin:32px auto;padding:0 16px;color:#1f2937}",
        "h1,h2{line-height:1.2} table{border-collapse:collapse;width:100%;margin:12px 0}",
        "th,td{border:1px solid #d1d5db;padding:6px 8px;text-align:left} th{background:#f3f4f6}",
        ".meta{color:#6b7280} svg{max-width:100%;height:auto}",
        "</style>",
        "</head>",
        "<body>",
        "<h1>%s</h1>" % esc(title),
        '<p class="meta">%s &middot; %d item(s)</p>' % (esc(range_label), len(items)),
    ]
    if plot_data:
        lines.append(_plot_data_to_svg(plot_data, title="Summary"))
    lines.append("<h2>Items</h2>")
    if items:
        lines.append(
            "<table><thead><tr><th>Status</th><th>Type</th><th>Title</th><th>Project</th></tr></thead><tbody>"
        )
        for item in items:
            project = (
                str(item.details.get("project", [""])[0])
                if item.details.get("project")
                else ""
            )
            lines.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (esc(item.status), esc(item.kind), esc(item.title), esc(project))
            )
        lines.append("</tbody></table>")
    else:
        lines.append("<p>No matching items.</p>")
    lines.extend(["</body>", "</html>"])
    return "\n".join(lines) + "\n"


def _share_to_markdown(title, range_label, items, plot_data):
    lines = ["# %s" % title, "", "%s — %d item(s)" % (range_label, len(items)), ""]
    for chart_title, data in plot_data.items():
        lines.append("## %s" % chart_title)
        lines.append("")
        max_value = max(data.values()) if data else 1
        for label, value in data.items():
            bar = _plot_bar(value, max_value, width=30)
            lines.append("- `%s` %s %s" % (label, bar, value))
        lines.append("")
    lines.append("## Items")
    lines.append("")
    if items:
        lines.append("| Status | Type | Title | Project |")
        lines.append("|---|---|---|---|")
        for item in items:
            project = (
                str(item.details.get("project", [""])[0])
                if item.details.get("project")
                else ""
            )
            lines.append(
                "| %s | %s | %s | %s |"
                % (item.status, item.kind, item.title.replace("|", "\\|"), project)
            )
    else:
        lines.append("No matching items.")
    return "\n".join(lines) + "\n"


def command_share(args):
    config = _config(args)
    paths = _normalize_paths(getattr(args, "paths", None) or [], config)
    items, diagnostics = _parse_life_inputs(paths, config)
    items = _filter_items_from_args(items, args)

    range_label = _share_range_label(args)
    plot_data = _share_plot_data(items)

    fmt = getattr(args, "format", "html") or "html"
    title = getattr(args, "title", None) or "lifetxt share report"
    output_path = getattr(args, "output", None) or (
        "share.html" if fmt == "html" else "share.md"
    )

    if fmt == "markdown":
        text = _share_to_markdown(title, range_label, items, plot_data)
    else:
        text = _share_to_html(title, range_label, items, plot_data)

    write_text(output_path, text)
    sys.stdout.write("Wrote %s (%d item(s)).\n" % (output_path, len(items)))
    _print_warnings(diagnostics)
    return 0


def _digest_message_from_report(args):
    """Render a configured `lifetxt report` profile as the digest message.

    `report` owns what the document means; digest only reuses the already-
    rendered text and its own delivery channels (#608). No review/stats/
    report semantics are duplicated here.
    """
    from . import report_cli

    report_name = args.report
    config_data = getattr(args, "config_data", None) or {}
    config_path = getattr(args, "config", None)
    profile = report_cli._profile_named(config_data, report_name)
    report_args = argparse.Namespace(
        name=report_name,
        date=getattr(args, "date", None),
        previous=getattr(args, "previous", False),
    )
    _profile, text, start, end = report_cli._render_named_report(
        report_args, config_data, config_path=config_path, workspace_name=None
    )
    subject_range = "%s to %s" % (start.isoformat(), end.isoformat())
    return text, subject_range


def command_digest(args):
    import contextlib
    import io

    report_name = getattr(args, "report", None)
    if report_name:
        message, digest_range = _digest_message_from_report(args)
    else:
        review_args = argparse.Namespace(
            paths=getattr(args, "paths", None) or [],
            week=getattr(args, "week", False),
            month=getattr(args, "month", None),
            from_date=None,
            to_date=None,
            project=getattr(args, "project", None),
            format="json",
            pretty=False,
            config=getattr(args, "config", None),
            config_data=getattr(args, "config_data", None),
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            command_review(review_args)
        result = json.loads(buffer.getvalue())
        digest_range = result["range"]

        lines = ["*lifetxt digest: %s*" % result["range"], ""]
        lines.append("Completed tasks: %d" % result["completed_tasks"])
        lines.append("Open tasks: %d" % result["open_tasks"])
        if result["habits"]:
            lines.append("")
            lines.append("Habits:")
            for habit_title, habit in result["habits"].items():
                lines.append(
                    "- %s: %d/%d (%d%%)"
                    % (
                        habit_title,
                        habit["done"],
                        habit["done"] + habit["open"],
                        habit["completion_rate"],
                    )
                )
        if result["elapsed_by_project"]:
            lines.append("")
            lines.append("Elapsed by project:")
            for project, elapsed in result["elapsed_by_project"].items():
                lines.append("- %s: %s" % (project, elapsed))
        message = "\n".join(lines)

    channel = args.channel
    dry_run = getattr(args, "dry_run", False)

    from .mail_delivery import append_local_file, send_slack_webhook, send_smtp_text

    if channel == "slack-webhook":
        url_env = getattr(args, "url_env", None)
        if not url_env:
            raise ValueError("--url-env is required with --format slack-webhook.")
        send_slack_webhook(message, url_env, dry_run=dry_run, output=sys.stdout)
        return 0

    if channel == "email":
        to_addr = getattr(args, "to", None)
        if not to_addr:
            raise ValueError("--to is required with --format email.")
        send_smtp_text(
            "lifetxt digest: %s" % digest_range,
            message,
            to_addr,
            host_env=getattr(args, "smtp_host_env", "LIFETXT_SMTP_HOST"),
            user_env=getattr(args, "smtp_user_env", "LIFETXT_SMTP_USER"),
            pass_env=getattr(args, "smtp_pass_env", "LIFETXT_SMTP_PASS"),
            port=getattr(args, "smtp_port", None),
            dry_run=dry_run,
            output=sys.stdout,
        )
        return 0

    if channel == "file":
        digest_path = getattr(args, "digest_path", None)
        if not digest_path:
            raise ValueError("--path is required with --format file.")
        append_local_file(
            digest_path,
            message,
            revision=getattr(args, "revision", None),
            dry_run=dry_run,
            output=sys.stdout,
        )
        return 0

    raise ValueError("Unsupported digest channel: %s" % channel)


def _resolve_template_placeholders(text, today=None):
    today = today or timezone_today()
    days_to_next_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + datetime.timedelta(days=days_to_next_monday)
    next_week = today + datetime.timedelta(days=7)
    replacements = (
        ("{today}", today.isoformat()),
        ("{next_monday}", next_monday.isoformat()),
        ("{next_week}", next_week.isoformat()),
    )
    for placeholder, value in replacements:
        text = text.replace(placeholder, value)
    return text


def command_template_list(args):
    templates = config_templates(_config(args))
    if not templates:
        sys.stdout.write(
            'No templates configured. Add a "templates" section to your config file.\n'
        )
        return 0
    for name, lines in templates.items():
        sys.stdout.write("%s (%d line(s))\n" % (name, len(lines)))
    return 0


def command_template_apply(args):
    templates = config_templates(_config(args))
    name = args.name
    if name not in templates:
        raise ValueError(
            "Template not found: %s. Run `lifetxt template list` to see available templates."
            % name
        )
    expanded_lines = [_resolve_template_placeholders(line) for line in templates[name]]
    expanded = "\n".join(expanded_lines) + "\n"

    if getattr(args, "dry_run", False):
        sys.stdout.write("[dry-run] Would append to %s:\n%s" % (args.append, expanded))
        return 0

    target = args.append
    from .write_operations import append_life_records

    append_life_records(
        target,
        expanded,
        expected_revision=getattr(args, "revision", None),
        operation="template.apply",
    )
    sys.stdout.write(
        "Appended template %r (%d line(s)) to %s.\n"
        % (name, len(expanded_lines), target)
    )
    return 0


# Base `lifetxt export` format registrations. Placed at module bottom so
# every referenced handler function is already defined; see
# EXPORT_FORMAT_HANDLERS's own docstring above.
register_export_format("json", command_to_json)
register_export_format("jsonl", command_to_jsonl)
register_export_format("csv", command_to_csv)
register_export_format("markdown", command_share)
register_export_format("life", command_filter)
register_export_format("sqlite", _export_sqlite)
register_import_preset("sqlite", _import_sqlite_preset)
register_export_format("lifetxtz", _export_lifetxtz)
register_import_preset("lifetxtz", _import_lifetxtz_preset)
