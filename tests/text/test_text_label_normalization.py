from __future__ import annotations

import pytest

from pdomain_book_contracts.text.label_normalization import (
    normalize_character_component,
    normalize_character_components,
    normalize_text_style_label,
    normalize_text_style_label_scope,
    normalize_text_style_label_scopes,
    normalize_text_style_labels,
    normalize_word_component,
    normalize_word_components,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Italics ", "italics"),
        ("SMALL_CAPS", "small caps"),
        ("all-caps", "all caps"),
        ("smallcaps", "small caps"),
        ("Strike  Through", "strikethrough"),
        ("black-letter", "blackletter"),
    ],
)
def test_style_label_is_canonicalised(raw: str, expected: str) -> None:
    assert normalize_text_style_label(raw) == expected


def test_unknown_style_label_error_lists_allowed_labels() -> None:
    with pytest.raises(ValueError, match="Invalid text style label 'wavy'") as info:
        normalize_text_style_label("wavy")
    assert "small caps" in str(info.value)


def test_style_labels_empty_or_none_default_to_regular() -> None:
    assert normalize_text_style_labels(None) == ["regular"]
    assert normalize_text_style_labels([]) == ["regular"]


def test_style_labels_dedupe_in_order_and_drop_redundant_regular() -> None:
    result = normalize_text_style_labels(["Regular", "Bold", "ITALICS", "bold"])
    assert result == ["bold", "italics"]


def test_style_labels_keep_lone_regular() -> None:
    assert normalize_text_style_labels(["regular", "Regular"]) == ["regular"]


def test_style_labels_reject_unknown_member() -> None:
    with pytest.raises(ValueError, match="Invalid text style label"):
        normalize_text_style_labels(["bold", "nope"])


def test_scope_none_means_whole() -> None:
    assert normalize_text_style_label_scope(None) == "whole"


def test_scope_is_case_and_space_insensitive() -> None:
    assert normalize_text_style_label_scope(" PART ") == "part"


def test_scope_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="Invalid text style label scope 'half'"):
        normalize_text_style_label_scope("half")


def test_scopes_default_every_label_to_whole() -> None:
    assert normalize_text_style_label_scopes(["Bold", "small_caps"], None) == {
        "bold": "whole",
        "small caps": "whole",
    }


def test_scopes_empty_labels_fall_back_to_regular() -> None:
    assert normalize_text_style_label_scopes([], {}) == {"regular": "whole"}


def test_scopes_apply_override_with_normalised_label_and_scope() -> None:
    result = normalize_text_style_label_scopes(
        ["bold", "italics"], {"ITALICS": " Part "}
    )
    assert result == {"bold": "whole", "italics": "part"}


def test_scopes_follow_regular_stripping_of_labels() -> None:
    result = normalize_text_style_label_scopes(["regular", "bold"], None)
    assert result == {"bold": "whole"}


def test_scopes_silently_drop_redundant_regular_entry() -> None:
    result = normalize_text_style_label_scopes(
        ["regular", "bold"], {"regular": "part", "bold": "part"}
    )
    assert result == {"bold": "part"}


def test_scopes_reject_label_not_in_labels() -> None:
    with pytest.raises(ValueError, match="Unknown style label 'italics'") as info:
        normalize_text_style_label_scopes(["bold"], {"italics": "part"})
    assert "bold" in str(info.value)


def test_scopes_reject_bad_scope_value() -> None:
    with pytest.raises(ValueError, match="Invalid text style label scope"):
        normalize_text_style_label_scopes(["bold"], {"bold": "half"})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Superscript", "superscript"),
        ("footnote_marker", "footnote marker"),
        ("footnotemarker", "footnote marker"),
        ("drop-cap", "drop cap"),
        ("dropcap unrecovered", "drop cap unrecovered"),
    ],
)
def test_word_and_character_components_are_canonicalised(
    raw: str, expected: str
) -> None:
    assert normalize_word_component(raw) == expected
    assert normalize_character_component(raw) == expected


def test_word_component_error_names_the_label_type() -> None:
    with pytest.raises(ValueError, match="Invalid word component 'sideways'"):
        normalize_word_component("sideways")


def test_character_component_error_names_the_label_type() -> None:
    with pytest.raises(ValueError, match="Invalid character component 'sideways'"):
        normalize_character_component("sideways")


def test_component_lists_dedupe_preserving_order() -> None:
    raw = ["Subscript", "superscript", "sub_script"]
    expected = ["subscript", "superscript"]
    assert normalize_word_components(raw) == expected
    assert normalize_character_components(raw) == expected


def test_component_lists_empty_or_none_give_empty_list() -> None:
    assert normalize_word_components(None) == []
    assert normalize_word_components([]) == []
    assert normalize_character_components(None) == []
    assert normalize_character_components([]) == []


def test_component_lists_reject_unknown_member() -> None:
    with pytest.raises(ValueError, match="word component"):
        normalize_word_components(["subscript", "bad"])
    with pytest.raises(ValueError, match="character component"):
        normalize_character_components(["subscript", "bad"])
