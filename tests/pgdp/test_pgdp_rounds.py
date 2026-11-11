from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdomain_book_contracts.sources.pgdp.rounds import PGDPExport, PGDPResults


def _processed(text: str) -> str:
    return PGDPResults("page.png", text).processed_page_text


def test_results_resolve_png_path_and_keep_original_text() -> None:
    results = PGDPResults("sub/page.png", "a\r\nb")
    assert results.png_full_path == Path("sub/page.png").resolve()
    assert results.original_page_text == "a\r\nb"
    assert results.original_lines == ["a", "b"]


def test_results_index_lines_and_words() -> None:
    results = PGDPResults("p.png", "one two\n\nthree")
    assert results.processed_lines == [(0, "one two"), (1, ""), (2, "three")]
    assert results.processed_words == [
        (0, 0, "one"),
        (0, 1, "two"),
        (2, 0, "three"),
    ]


def test_process_normalises_windows_line_breaks() -> None:
    assert _processed("a\r\nb") == "a\nb"


def test_blank_page_marker_yields_empty_page() -> None:
    results = PGDPResults("p.png", "[Blank Page]")
    assert results.processed_page_text == ""
    assert results.processed_lines == []
    assert results.processed_words == []


def test_proofer_notes_are_removed_across_lines() -> None:
    assert _processed("a [* note\nmore] b") == "a  b"


def test_footnote_brackets_lose_their_brackets_but_other_brackets_stay() -> None:
    assert _processed("see [12] and [Illustration]") == "see 12 and [Illustration]"


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("[=a]", "\N{LATIN SMALL LETTER A WITH MACRON}"),
        ("[=O]", "\N{LATIN CAPITAL LETTER O WITH MACRON}"),
        ("[:u]", "\N{LATIN SMALL LETTER U WITH DIAERESIS}"),
        ("[:E]", "\N{LATIN CAPITAL LETTER E WITH DIAERESIS}"),
        ("[.z]", "\N{LATIN SMALL LETTER Z WITH DOT ABOVE}"),
        ("[.I]", "\N{LATIN CAPITAL LETTER I WITH DOT ABOVE}"),
        ("[`e]", "\N{LATIN SMALL LETTER E WITH GRAVE}"),
        ("[`U]", "\N{LATIN CAPITAL LETTER U WITH GRAVE}"),
        ("['e]", "\N{LATIN SMALL LETTER E WITH ACUTE}"),
        ("['Y]", "\N{LATIN CAPITAL LETTER Y WITH ACUTE}"),
        ("[)a]", "\N{LATIN SMALL LETTER A WITH BREVE}"),
        ("[)U]", "\N{LATIN CAPITAL LETTER U WITH BREVE}"),
        ("[c,]", "\N{LATIN SMALL LETTER C WITH CEDILLA}"),
    ],
)
def test_diacritic_markup_becomes_the_accented_letter(
    markup: str, expected: str
) -> None:
    assert PGDPResults.fix_pgdp_diacritics(f"x{markup}y") == f"x{expected}y"


def test_diacritic_markup_inside_a_word_is_replaced_in_page_text() -> None:
    assert (
        _processed("caf['e] na[:i]ve")
        == "caf\N{LATIN SMALL LETTER E WITH ACUTE} na\N{LATIN SMALL LETTER I WITH DIAERESIS}ve"
    )


def test_hyphen_asterisk_rejoins_word_split_across_lines() -> None:
    assert _processed("foo-*bar\nbaz qux") == "foo-\nbar baz qux"


def test_leading_and_trailing_page_asterisks_are_dropped() -> None:
    assert _processed("*start of page") == "start of page"
    assert _processed("end of page*") == "end of page"


def test_trailing_asterisk_keeps_the_preceding_hyphen() -> None:
    assert _processed("word-*") == "word-"


def test_asterisk_inside_text_is_kept() -> None:
    assert _processed("a * b") == "a * b"


def test_four_hyphens_become_long_dash_and_two_become_em_dash() -> None:
    assert _processed("a----b--c") == "a\N{TWO-EM DASH}b\N{EM DASH}c"


def test_double_quotes_open_after_whitespace_dash_or_bracket() -> None:
    assert _processed('"Hi," she said--"go" ("now")') == (
        "\N{LEFT DOUBLE QUOTATION MARK}Hi,\N{RIGHT DOUBLE QUOTATION MARK} she said\N{EM DASH}\N{LEFT DOUBLE QUOTATION MARK}go\N{RIGHT DOUBLE QUOTATION MARK} (\N{LEFT DOUBLE QUOTATION MARK}now\N{RIGHT DOUBLE QUOTATION MARK})"
    )


def test_apostrophes_in_contractions_and_plural_possessives_are_closing() -> None:
    assert _processed("don't and the boys' hats") == (
        "don\N{RIGHT SINGLE QUOTATION MARK}t and the boys\N{RIGHT SINGLE QUOTATION MARK} hats"
    )


def test_single_quotes_around_a_phrase_open_and_close() -> None:
    assert (
        _processed("He said 'go' now")
        == "He said \N{LEFT SINGLE QUOTATION MARK}go\N{RIGHT SINGLE QUOTATION MARK} now"
    )


def test_single_quote_opens_after_em_dash() -> None:
    assert (
        _processed("word--'Yes' no")
        == "word\N{EM DASH}\N{LEFT SINGLE QUOTATION MARK}Yes\N{RIGHT SINGLE QUOTATION MARK} no"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("'Tis true", "\N{RIGHT SINGLE QUOTATION MARK}Tis true"),
        ("'Twas the night", "\N{RIGHT SINGLE QUOTATION MARK}Twas the night"),
        (
            "rock 'n' roll",
            "rock \N{RIGHT SINGLE QUOTATION MARK}n\N{RIGHT SINGLE QUOTATION MARK} roll",
        ),
        (
            "in '95 and the '60s",
            "in \N{RIGHT SINGLE QUOTATION MARK}95 and the \N{RIGHT SINGLE QUOTATION MARK}60s",
        ),
        (
            '"\'Tis," said',
            "\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}Tis,\N{RIGHT DOUBLE QUOTATION MARK} said",
        ),
    ],
)
def test_leading_elisions_and_decades_get_apostrophes_not_opening_quotes(
    raw: str, expected: str
) -> None:
    assert PGDPResults.convert_straight_to_curly_quotes(raw) == expected


def test_export_from_json_builds_pages_under_prefix(tmp_path: Path) -> None:
    payload = json.dumps({"001.png": "'Tis one", "002.png": "[Blank Page]"})
    export = PGDPExport.from_json(payload, tmp_path / "proj_123")
    assert export.project_id == "proj_123"
    assert [page.png_file for page in export.pages] == [
        str(tmp_path / "proj_123" / "001.png"),
        str(tmp_path / "proj_123" / "002.png"),
    ]
    assert (
        export.pages[0].processed_page_text == "\N{RIGHT SINGLE QUOTATION MARK}Tis one"
    )
    assert export.pages[1].processed_page_text == ""


def test_export_from_json_accepts_string_prefix_with_no_pages() -> None:
    export = PGDPExport.from_json("{}", "some/dir/proj")
    assert export.pages == []
    assert export.project_id == "proj"


def test_export_from_json_file_reads_utf8_and_uses_parent_as_project(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "proj_9"
    project_dir.mkdir()
    source = project_dir / "export.json"
    source.write_text(json.dumps({"1.png": "caf['e]"}), encoding="utf-8")
    for arg in (source, str(source)):
        export = PGDPExport.from_json_file(arg)
        assert export.project_id == "proj_9"
        assert (
            export.pages[0].processed_page_text
            == "caf\N{LATIN SMALL LETTER E WITH ACUTE}"
        )


def test_export_from_json_file_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="File not found"):
        PGDPExport.from_json_file(tmp_path / "nope.json")


def test_export_from_json_file_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Not a file"):
        PGDPExport.from_json_file(tmp_path)
