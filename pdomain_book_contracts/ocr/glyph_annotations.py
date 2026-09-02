"""Glyph-level side-channel annotations on Word.

Architecture: pdomain-book-tools/docs/architecture/glyph-annotations.md
Issue: pdomain/pdomain-book-tools#41

These types record glyph-level facts about the printed page (ligatures,
long-s substitutions, swash forms) **without** mutating the canonical /
semantic ground-truth string.

Key invariants (see spec section 1):
- ``Word.ground_truth_text`` must NEVER contain Unicode ligature codepoints
  U+FB00 through U+FB06 or the long-s U+017F -- these facts are side-channel only.
- ``glyph_annotations is None`` means "nobody has looked at this word yet"
  (unknown / unreviewed).
- ``glyph_annotations == GlyphAnnotations()`` means "reviewed; no glyph
  annotations for this word".  The two states are semantically distinct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, cast, get_args

if TYPE_CHECKING:
    from pdomain_book_tools.ocr.word import Word

# ---------------------------------------------------------------------------
# Codepoints banned from ground_truth_text (spec sections 1.1 and 4.1)
# ---------------------------------------------------------------------------

# Defined using Unicode escapes where ruff RUF001 would flag the literal.
_BANNED_GT_CODEPOINTS: frozenset[str] = frozenset(
    [
        "ﬀ",  # LATIN SMALL LIGATURE FF
        "ﬁ",  # LATIN SMALL LIGATURE FI
        "ﬂ",  # LATIN SMALL LIGATURE FL
        "ﬃ",  # LATIN SMALL LIGATURE FFI
        "ﬄ",  # LATIN SMALL LIGATURE FFL
        "ﬅ",  # LATIN SMALL LIGATURE LONG S T
        "ﬆ",  # LATIN SMALL LIGATURE ST
        "\u017f",  # LATIN SMALL LETTER LONG S (U+017F)
    ]
)


# ---------------------------------------------------------------------------
# LigatureKind (spec section 2.1)
# ---------------------------------------------------------------------------


class LigatureKind(StrEnum):
    """Controlled vocabulary for ligature types found in early-modern printing.

    Values are UPPERCASE plain strings so JSON serialization yields bare
    human-readable strings without extra encoding.

    Adding a new value requires a PR with: the printed form (image/fixture
    reference), the GT decomposition, and a note on the corpus it appeared in.
    Speculative additions are explicitly disallowed.

    Changed in plan #163: values uppercased; LONG_S_T renamed to LONG_ST;
    OE and AE added per pdomain-ocr-labeler-spa spec 20 §3.
    """

    # Latin ligatures common in early-modern printing
    FI = "FI"  # U+FB01 in print, "fi" in GT
    FL = "FL"  # U+FB02
    FF = "FF"  # U+FB00
    FFI = "FFI"  # U+FB03
    FFL = "FFL"  # U+FB04
    CT = "CT"  # decorative ct ligature, no Unicode codepoint
    ST = "ST"  # U+FB06 in print, "st" in GT
    LONG_ST = "LONG_ST"  # U+FB05 in print (long-s t), "st" in GT; renamed from LONG_S_T
    LONG_S_S = "LONG_S_S"  # long-s s, "ss" in GT
    LONG_S_I = (
        "LONG_S_I"  # long-s i, "si" in GT (less common, included for completeness)
    )
    SP = "SP"  # decorative sp ligature
    QU = "QU"  # decorative Qu ligature
    OE = "OE"  # oe ligature (new in plan #163 per SPA spec 20 §3)
    AE = "AE"  # ae ligature (new in plan #163 per SPA spec 20 §3)


# ---------------------------------------------------------------------------
# Migration helper (Phase 2, plan #163)
# ---------------------------------------------------------------------------

# Maps legacy pre-#163 kind strings (lowercase + old LONG_S_T name) to their
# new uppercase equivalents.  Called by LigatureMark.from_dict on the raw
# kind field.  May be removed after a release cycle once no persisted
# snapshots with lowercase values remain.
_LEGACY_KIND_MAP: dict[str, str] = {
    "fi": "FI",
    "fl": "FL",
    "ff": "FF",
    "ffi": "FFI",
    "ffl": "FFL",
    "ct": "CT",
    "st": "ST",
    "long_s_t": "LONG_ST",  # old name + lowercase value → new member
    "LONG_S_T": "LONG_ST",  # old name uppercase variant → new member
    "long_s_s": "LONG_S_S",
    "long_s_i": "LONG_S_I",
    "sp": "SP",
    "qu": "QU",
}


def _migrate_ligature_kind_value(raw: str) -> str:
    """Map a raw kind string to the canonical uppercase LigatureKind value.

    Accepts:
    - Current UPPERCASE values (passed through unchanged).
    - Legacy lowercase values from pre-#163 snapshots (mapped to uppercase).
    - Old ``LONG_S_T`` / ``long_s_t`` name (mapped to ``LONG_ST``).

    Raises:
        ValueError: indirectly, when the mapped value is not a valid
            :class:`LigatureKind` member (handled by the calling ``LigatureKind()``
            constructor in :meth:`LigatureMark.from_dict`).
    """
    return _LEGACY_KIND_MAP.get(raw, raw)


# ---------------------------------------------------------------------------
# LigatureMark (spec section 2.2)
# ---------------------------------------------------------------------------


@dataclass
class LigatureMark:
    """A single ligature occurrence within a Word's ground-truth text.

    Args:
        kind: Which ligature type this mark records.
        char_span: ``[start, end)`` char indices into ``Word.ground_truth_text``.
            ``None`` means "we know this ligature is somewhere in the word but
            don't know exactly where" (e.g. coarse-grained synth labels).
    """

    kind: LigatureKind
    char_span: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict.

        ``char_span`` is emitted as a list (JSON arrays) when set, or ``None``
        when absent.
        """
        return {
            "kind": self.kind.value,
            "char_span": list(self.char_span) if self.char_span is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> LigatureMark:
        """Deserialize from a dict produced by :meth:`to_dict`.

        Accepts both current UPPERCASE values and legacy lowercase values from
        pre-#163 snapshots (see :func:`_migrate_ligature_kind_value`).

        Raises:
            ValueError: if ``kind`` is not a recognised :class:`LigatureKind`
                value.  Unknown values must raise (spec section 4.4) to prevent
                silent schema drift.
        """
        raw_kind = _migrate_ligature_kind_value(cast("str", d["kind"]))
        kind = LigatureKind(raw_kind)  # raises ValueError for unknown strings
        span_raw = d.get("char_span")
        char_span: tuple[int, int] | None = None
        if span_raw is not None:
            span = cast("list[int]", span_raw)
            char_span = (int(span[0]), int(span[1]))
        return cls(kind=kind, char_span=char_span)


# ---------------------------------------------------------------------------
# GlyphAnnotations (spec section 2.3)
# ---------------------------------------------------------------------------

# Provenance vocabulary for GlyphAnnotations.source (object-level provenance).
# See pdomain-ocr-labeler-spa specs/20-glyph-annotations.md section 3 and ADR D-044:
#   "human"           -- entered/edited by a human, no classifier involvement
#   "predicted"       -- classifier-only output, awaiting human confirmation
#   "human_confirmed" -- classifier was right and a human kept it
GlyphSource = Literal["human", "predicted", "human_confirmed"]

_VALID_GLYPH_SOURCES: frozenset[str] = frozenset(get_args(GlyphSource))


@dataclass
class GlyphAnnotations:
    """Parallel annotation structure attached to a Word (spec section 2.3).

    Records glyph-level facts about the printed page without mutating the
    canonical ground-truth string.  See module docstring for the
    ``None`` vs ``GlyphAnnotations()`` semantics contract.

    Args:
        ligatures: List of ligature occurrences found in this word.
        long_s_positions: Char indices in GT where a printed U+017F (long-s) was
            normalised to ``s``.  The index refers to the GT string.
        swash: ``True`` iff at least one glyph in the word is a swash variant
            (coarse bool; per-glyph refinement is a future extension).
        source: Object-level provenance for this annotation set -- how the
            top-level signals got here.  One of ``"human"``, ``"predicted"``,
            or ``"human_confirmed"``.  Defaults to ``"human"``.  Provenance is
            per-``GlyphAnnotations`` object, not per-mark (ADR D-044).
    """

    ligatures: list[LigatureMark] = field(default_factory=list)
    long_s_positions: list[int] = field(default_factory=list)
    swash: bool = False
    source: GlyphSource = "human"

    def __post_init__(self) -> None:
        """Validate ``source`` against the controlled provenance vocabulary."""
        if self.source not in _VALID_GLYPH_SOURCES:
            raise ValueError(
                f"GlyphAnnotations.source={self.source!r} is not a recognised "
                + "provenance value.  Must be one of "
                + f"{sorted(_VALID_GLYPH_SOURCES)} (ADR D-044)."
            )

    def to_dict(self) -> dict[str, object]:
        """Serialize to the canonical JSON wire shape (spec section 3.1)."""
        return {
            "ligatures": [m.to_dict() for m in self.ligatures],
            "long_s_positions": list(self.long_s_positions),
            "swash": self.swash,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> GlyphAnnotations:
        """Deserialize from a dict produced by :meth:`to_dict`.

        Missing keys fall back to their default values (spec section 1.4 /
        backwards-compatibility guarantee).

        Raises:
            ValueError: if any ``LigatureMark`` contains an unknown ``kind``
                value (spec section 4.4).
        """
        raw_ligatures = cast("list[dict[str, object]]", d.get("ligatures") or [])
        ligatures = [LigatureMark.from_dict(m) for m in raw_ligatures]
        long_s_positions = list(cast("list[int]", d.get("long_s_positions") or []))
        swash = bool(d.get("swash", False))
        source = cast("GlyphSource", d.get("source", "human"))
        return cls(
            ligatures=ligatures,
            long_s_positions=long_s_positions,
            swash=swash,
            source=source,
        )

    def validate(self, word: Word) -> None:
        """Validate these annotations against *word* (spec section 4).

        Checks are ordered: GT preconditions first, then annotation internals.

        Args:
            word: The :class:`~pdomain_book_tools.ocr.word.Word` these annotations
                are attached to.

        Raises:
            ValueError: On any of the conditions listed in spec section 4.
        """
        gt = word.ground_truth_text or ""

        # Section 4.1 -- GT text must not contain banned codepoints
        for ch in gt:
            if ch in _BANNED_GT_CODEPOINTS:
                raise ValueError(
                    f"GT text contains banned codepoint U+{ord(ch):04X} ({ch!r}). "
                    + "Ligatures and long-s must be recorded via glyph_annotations, "
                    + "not embedded in ground_truth_text (spec section 1.1)."
                )

        gt_len = len(gt)

        # Section 4.2 -- LigatureMark bounds
        for i, mark in enumerate(self.ligatures):
            if mark.char_span is not None:
                start, end = mark.char_span
                if not (0 <= start < end <= gt_len):
                    raise ValueError(
                        f"ligatures[{i}].char_span ({start}, {end}) is invalid for "
                        + f"GT text of length {gt_len}.  Spans must satisfy "
                        + "0 <= start < end <= len(gt) (spec section 4.2).  "
                        + "Use char_span=None to express 'unknown location'."
                    )

        # Section 4.3 -- long_s_positions bounds and character check
        for j, idx in enumerate(self.long_s_positions):
            if not (0 <= idx < gt_len):
                raise ValueError(
                    f"long_s_positions[{j}]={idx} is out of range for GT text of "
                    + f"length {gt_len} (spec section 4.3)."
                )
            if gt[idx] not in ("s", "S"):
                raise ValueError(
                    f"long_s_positions[{j}]={idx} points at {gt[idx]!r}, not 's' or "
                    + "'S'.  Each long_s index must point at the normalised form of "
                    + "U+017F (spec section 4.3)."
                )
