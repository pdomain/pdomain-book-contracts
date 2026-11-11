from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from pdomain_book_contracts.geometry.bounding_box import BoundingBox
from pdomain_book_contracts.ocr.character import Character


def _box() -> BoundingBox:
    return BoundingBox.from_ltrb(10, 20, 30, 50, is_normalized=False)


def test_defaults_are_a_regular_unlabelled_character() -> None:
    char = Character("a", _box())
    assert char.ocr_confidence is None
    assert char.text_style_labels == ["regular"]
    assert char.word_components == []


def test_labels_are_normalized_on_construction() -> None:
    char = Character(
        "a",
        _box(),
        text_style_labels=["Small_Caps", "BOLD", "bold"],
        word_components=["Footnote-Marker", "superscript", "superscript"],
    )
    assert char.text_style_labels == ["small caps", "bold"]
    assert char.word_components == ["footnote marker", "superscript"]


def test_unknown_labels_are_rejected() -> None:
    with pytest.raises(ValueError, match="text style label"):
        Character("a", _box(), text_style_labels=["sparkly"])
    with pytest.raises(ValueError, match="character component"):
        Character("a", _box(), word_components=["wobbly"])


def test_to_dict_has_the_documented_shape() -> None:
    char = Character("q", _box(), 0.9, ["italics"], ["superscript"])
    assert char.to_dict() == {
        "type": "Character",
        "text": "q",
        "bounding_box": _box().to_dict(),
        "ocr_confidence": 0.9,
        "text_style_labels": ["italics"],
        "word_components": ["superscript"],
    }


def test_dict_round_trip() -> None:
    original = Character("q", _box(), 0.9, ["italics", "bold"], ["subscript"])
    assert Character.from_dict(original.to_dict()) == original


def test_from_dict_applies_defaults() -> None:
    char = Character.from_dict({"text": "x", "bounding_box": _box().to_dict()})
    assert char.ocr_confidence is None
    assert char.text_style_labels == ["regular"]
    assert char.word_components == []


def test_from_dict_coerces_an_integer_confidence_to_float() -> None:
    char = Character.from_dict(
        {"text": "x", "bounding_box": _box().to_dict(), "ocr_confidence": 1}
    )
    assert isinstance(char.ocr_confidence, float)
    assert char.ocr_confidence == 1.0


def test_from_dict_keeps_zero_confidence() -> None:
    char = Character.from_dict(
        {"text": "x", "bounding_box": _box().to_dict(), "ocr_confidence": 0}
    )
    assert char.ocr_confidence == 0.0


def test_from_dict_accepts_an_existing_bounding_box_object() -> None:
    box = _box()
    char = Character.from_dict({"text": "x", "bounding_box": box})
    assert char.bounding_box is box


def test_legacy_footnote_marker_flag_becomes_a_component() -> None:
    char = Character.from_dict(
        {
            "text": "1",
            "bounding_box": _box().to_dict(),
            "word_components": ["superscript"],
            "is_footnote_marker": True,
        }
    )
    assert char.word_components == ["superscript", "footnote marker"]


def test_legacy_footnote_marker_flag_is_not_duplicated() -> None:
    char = Character.from_dict(
        {
            "text": "1",
            "bounding_box": _box().to_dict(),
            "word_components": ["footnote marker"],
            "is_footnote_marker": True,
        }
    )
    assert char.word_components == ["footnote marker"]


def test_false_footnote_marker_flag_adds_nothing() -> None:
    char = Character.from_dict(
        {
            "text": "1",
            "bounding_box": _box().to_dict(),
            "is_footnote_marker": False,
        }
    )
    assert char.word_components == []


def test_from_dict_requires_text_and_box() -> None:
    with pytest.raises(KeyError):
        Character.from_dict({"bounding_box": _box().to_dict()})
    with pytest.raises(KeyError):
        Character.from_dict({"text": "x"})


def test_pydantic_validates_the_wire_shape() -> None:
    adapter = TypeAdapter(Character)
    original = Character("z", _box(), 0.25, ["bold"], ["drop cap"])
    restored = adapter.validate_python(original.to_dict())
    assert restored == original


def test_pydantic_accepts_a_minimal_payload() -> None:
    char = TypeAdapter(Character).validate_python(
        {"text": "m", "bounding_box": _box().to_dict()}
    )
    assert char.text == "m"
    assert char.ocr_confidence is None


def test_pydantic_dump_matches_to_dict() -> None:
    char = Character("z", _box(), 0.25)
    assert TypeAdapter(Character).dump_python(char) == char.to_dict()


def test_pydantic_rejects_a_payload_without_a_box() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Character).validate_python({"text": "m"})


def test_pydantic_rejects_the_wrong_type_marker() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Character).validate_python(
            {"type": "Word", "text": "m", "bounding_box": _box().to_dict()}
        )
