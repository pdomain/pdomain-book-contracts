"""Layout types — :class:`RegionType`, :class:`LayoutRegion`, :class:`PageLayout`.

Coordinates are pixel-space integers in the source image's frame. The plan
deliberately keeps these dataclasses thin: a layout pass is an annotation
over the source image, not a participant in the OCR coordinate-system gymnastics
that ``Word`` / ``BoundingBox`` / ``Page`` perform.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class LayoutRegionDict(TypedDict):
    """Serialised form of :class:`LayoutRegion` as returned by ``to_dict()``."""

    type: str
    L: int
    R: int
    T: int
    B: int
    confidence: float
    raw_label: str


class PageLayoutDict(TypedDict):
    """Serialised form of :class:`PageLayout` as returned by ``to_dict()``."""

    regions: list[LayoutRegionDict]
    image_width: int
    image_height: int
    detector: str
    inference_ms: int


class RegionType(StrEnum):
    """Region categories the reorg / illustration extractor consume.

    The full PP-DocLayout 20-label vocabulary is collapsed to this set via
    :data:`pdomain_book_tools.layout._mappings.PP_DOCLAYOUT_TO_PGDP`. Other adapters
    map to the same enum.
    """

    text = "text"
    title = "title"  # pyright: ignore[reportAssignmentType]  # str.title() method clash; Literal["title"] conflicts with inherited str.title overload
    section = "section"
    list = "list"
    table = "table"
    figure = "figure"
    decoration = "decoration"
    caption = "caption"
    header = "header"
    footer = "footer"
    footnote = "footnote"
    formula = "formula"
    abandoned = "abandoned"
    # Geometric heuristic — left/right-margin sidenote column detected by
    # whitespace analysis when the layout model misses it. Treated the same
    # as a model-emitted region for tagging / block-role bubble-up.
    sidenote = "sidenote"


@dataclass(unsafe_hash=True)
class LayoutRegion:
    """One typed rectangle from a layout detector.

    Coordinates are pixel-space integers (L,R,T,B) in the source image frame.
    ``confidence`` is the model's score (0..1); rule-based detectors emit
    ``1.0``. ``raw_label`` preserves the adapter's native label so diagnostics
    can show "what the model actually said" before mapping to :class:`RegionType`.
    """

    type: RegionType
    L: int
    R: int
    T: int
    B: int
    confidence: float = 1.0
    raw_label: str = ""

    def __post_init__(self) -> None:
        # #176: coerce string ``type`` to ``RegionType`` so direct construction
        # with ``type="text"`` doesn't silently accept a plain string that will
        # crash later in ``to_dict()`` when ``self.type.value`` is called.
        # ``RegionType(value)`` raises ``ValueError`` for unknown strings,
        # giving callers an early, clear diagnostic.
        # ``RegionType(RegionType.text)`` is idempotent — enum constructors
        # accept both strings and existing members — so no isinstance guard is
        # needed.
        self.type = RegionType(
            self.type
        )  # dataclass field reassignment in __post_init__

        # #176: reject non-finite and out-of-range confidence values. NaN and
        # infinity produce non-standard JSON (json.dumps raises or emits
        # "Infinity") and break sort-by-confidence comparisons.  Rule-based
        # detectors always emit 1.0; model adapters clamp to [0, 1] before
        # creating LayoutRegion, so a value outside this range indicates a
        # bug upstream.
        if not math.isfinite(self.confidence) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"LayoutRegion confidence must be a finite value in [0, 1]; got {self.confidence!r}"
            )

        # Reject inverted rectangles up front. Without this, ``width`` /
        # ``height`` go negative, ``area`` silently returns 0 (masking the
        # bad input), and ``contains_point`` returns the wrong answer for
        # every query. Adapters that emit pixel-space rectangles (model
        # adapters, contour fallback) always have L<=R / T<=B by
        # construction; a violation here means a coordinate-system mix-up
        # upstream, which we want to surface loudly. Zero-width or
        # zero-height boxes (L == R or T == B) are still accepted — they're
        # degenerate but well-formed and produce ``area == 0``. Negative
        # absolute coordinates are clamped to 0 (the source-image frame
        # never has negative pixel indices).
        if self.L > self.R:
            raise ValueError(
                f"LayoutRegion has L > R ({self.L} > {self.R}); coordinates must satisfy L <= R"
            )
        if self.T > self.B:
            raise ValueError(
                f"LayoutRegion has T > B ({self.T} > {self.B}); coordinates must satisfy T <= B"
            )
        self.L = max(self.L, 0)  # pyright: ignore[reportConstantRedefinition]  # dataclass field; ALL_CAPS is LTRB convention
        self.T = max(self.T, 0)  # pyright: ignore[reportConstantRedefinition]  # dataclass field; ALL_CAPS is LTRB convention
        self.R = max(self.R, 0)  # pyright: ignore[reportConstantRedefinition]  # dataclass field; ALL_CAPS is LTRB convention
        self.B = max(self.B, 0)  # pyright: ignore[reportConstantRedefinition]  # dataclass field; ALL_CAPS is LTRB convention

    @property
    def width(self) -> int:
        return self.R - self.L

    @property
    def height(self) -> int:
        return self.B - self.T

    @property
    def area(self) -> int:
        w = self.width
        h = self.height
        if w <= 0 or h <= 0:
            return 0
        return w * h

    @property
    def center(self) -> tuple[float, float]:
        return ((self.L + self.R) / 2.0, (self.T + self.B) / 2.0)

    def contains_point(self, x: float, y: float) -> bool:
        return self.L <= x <= self.R and self.T <= y <= self.B

    def to_dict(self) -> LayoutRegionDict:
        return {
            "type": self.type.value,
            "L": int(self.L),
            "R": int(self.R),
            "T": int(self.T),
            "B": int(self.B),
            "confidence": float(self.confidence),
            "raw_label": self.raw_label,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> LayoutRegion:
        return cls(
            type=RegionType(str(data["type"])),
            L=int(cast("int", data["L"])),
            R=int(cast("int", data["R"])),
            T=int(cast("int", data["T"])),
            B=int(cast("int", data["B"])),
            confidence=float(cast("float", data.get("confidence", 1.0))),
            raw_label=str(data.get("raw_label", "")),
        )


@dataclass
class PageLayout:
    """All regions detected for a single page, plus detector metadata.

    ``image_width`` / ``image_height`` are the dimensions of the image the
    detector saw — coordinates in :class:`LayoutRegion` are in this frame.
    """

    regions: list[LayoutRegion] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0
    detector: str = ""
    inference_ms: int = 0

    def __iter__(self) -> Iterator[LayoutRegion]:
        return iter(self.regions)

    def __len__(self) -> int:
        return len(self.regions)

    def of_type(self, *types: RegionType) -> list[LayoutRegion]:
        # R-26: ``of_type()`` with no arguments previously returned ``[]``
        # because ``r.type in set()`` is always False — indistinguishable
        # at the call site from "no regions of these types found", and
        # almost never the caller's intent. Raise instead so the bug
        # is surfaced. Use ``layout.regions`` directly to iterate all
        # regions.
        if not types:
            raise ValueError(
                "of_type() requires at least one RegionType; use `layout.regions` to iterate all regions"
            )
        s = set(types)
        return [r for r in self.regions if r.type in s]

    def to_dict(self) -> PageLayoutDict:
        return {
            "regions": [r.to_dict() for r in self.regions],
            "image_width": int(self.image_width),
            "image_height": int(self.image_height),
            "detector": self.detector,
            "inference_ms": int(self.inference_ms),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> PageLayout:
        raw_regions = cast("list[Mapping[str, object]]", data.get("regions", []))
        return cls(
            regions=[LayoutRegion.from_dict(r) for r in raw_regions],
            image_width=int(cast("int", data.get("image_width", 0))),
            image_height=int(cast("int", data.get("image_height", 0))),
            detector=str(data.get("detector", "")),
            inference_ms=int(cast("int", data.get("inference_ms", 0))),
        )
