import pytest

from lifetxt.parser import parse_text


def test_parse_text_default_id_key_detects_duplicates():
    _, diagnostics = parse_text("[ ] T One id:dup\n[ ] T Two id:dup\n")
    assert any(d.code == "W213" for d in diagnostics)


def test_parse_text_id_checks_can_be_disabled():
    _, diagnostics = parse_text(
        "[ ] T One id:dup\n[ ] T Two id:dup\n", check_ids=False
    )
    assert not any(d.code == "W213" for d in diagnostics)


def test_parse_text_reference_checks_can_be_disabled():
    _, diagnostics = parse_text("[ ] T One id:one ref:missing\n")
    assert any(d.code == "W215" for d in diagnostics)
    _, disabled = parse_text("[ ] T One id:one ref:missing\n", check_references=False)
    assert not any(d.code == "W215" for d in disabled)


def test_parse_text_custom_id_key_is_used():
    _, diagnostics = parse_text("[ ] T One key:a\n[ ] T Two key:a\n", id_key="key")
    assert any(d.code == "W213" for d in diagnostics)


@pytest.mark.parametrize("line", [
    '[ ] T "Research Meeting" note:"Use \\"life.txt\\"" custom:value\r\n',
    "[ ] T Review \\\r\n  due:2026-06-12 custom:value\r\n",
])
def test_parse_text_semantic_boundaries_have_no_errors(line):
    _, diagnostics = parse_text(line)
    assert not any(d.severity == "error" for d in diagnostics)