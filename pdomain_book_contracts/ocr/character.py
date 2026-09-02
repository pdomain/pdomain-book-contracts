from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict, cast

from pydantic_core import CoreSchema, core_schema

from pdomain_book_tools.geometry.bounding_box import BoundingBox
from pdomain_book_tools.ocr.label_normalization import (
    normalize_character_components,
    normalize_text_style_labels,
)
from pdomain_book_tools.schemas._helpers import (
    NUMBER_SCHEMA,
    STR_LIST_SCHEMA,
)

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler


class _PointDict(TypedDict, total=False):
    x: float
    y: float
    is_normalized: bool | None


class _BoundingBoxDict(TypedDict):
    top_left: _PointDict
    bottom_right: _PointDict
    is_normalized: bool | None


@dataclass
class Character:
    """Represents a single OCR character with its own bounding box and labels."""

    text: str
    bounding_box: BoundingBox
    ocr_confidence: float | None = None
    text_style_labels: list[str] = field(default_factory=list)
    word_components: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.text_style_labels = normalize_text_style_labels(self.text_style_labels)
        self.word_components = normalize_character_components(self.word_components)

    def to_dict(self) -> dict[str, object]:
        """Convert to JSON-serializable dictionary."""
        return {
            "type": "Character",
            "text": self.text,
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
            "ocr_confidence": self.ocr_confidence,
            "text_style_labels": self.text_style_labels,
            "word_components": self.word_components,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Character:
        """Create Character from dictionary."""
        raw_word_components = data.get("word_components")
        word_components: list[str] = (
            cast("list[str]", raw_word_components)
            if raw_word_components is not None
            else []
        )
        if data.get("is_footnote_marker"):
            word_components = [*word_components, "footnote marker"]

        bb_raw = data["bounding_box"]
        if isinstance(bb_raw, BoundingBox):
            bounding_box = bb_raw
        else:
            # bb_raw is the dict-serialised form; BoundingBox.from_dict validates it.
            # Cast is needed because bb_raw is typed as object at this point.
            bounding_box = BoundingBox.from_dict(cast("_BoundingBoxDict", bb_raw))

        raw_confidence = data.get("ocr_confidence")
        ocr_confidence = (
            float(cast("float | int", raw_confidence))
            if raw_confidence is not None
            else None
        )
        return Character(
            text=cast("str", data["text"]),
            bounding_box=bounding_box,
            ocr_confidence=ocr_confidence,
            text_style_labels=cast("list[str]", data.get("text_style_labels") or []),
            word_components=word_components,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        # Local import to avoid a circular: BoundingBox imports Point,
        # Character imports BoundingBox. Module-level is fine here since
        # this module is loaded after both.
        bb_schema = handler.generate_schema(BoundingBox)
        return core_schema.no_info_after_validator_function(
            function=cls.from_dict,
            schema=core_schema.typed_dict_schema(
                {
                    "type": core_schema.typed_dict_field(
                        core_schema.literal_schema(["Character"]),
                        required=False,
                    ),
                    "text": core_schema.typed_dict_field(
                        core_schema.str_schema(),
                    ),
                    "bounding_box": core_schema.typed_dict_field(bb_schema),
                    "ocr_confidence": core_schema.typed_dict_field(
                        core_schema.nullable_schema(NUMBER_SCHEMA),
                        required=False,
                    ),
                    "text_style_labels": core_schema.typed_dict_field(
                        STR_LIST_SCHEMA,
                        required=False,
                    ),
                    "word_components": core_schema.typed_dict_field(
                        STR_LIST_SCHEMA,
                        required=False,
                    ),
                }
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls.to_dict,
            ),
        )
