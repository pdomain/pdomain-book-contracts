"""Region-adjacency helpers used by reorg and the illustration extractor.

These are deliberately decoupled from :class:`pdomain_book_tools.geometry.BoundingBox`
because layout regions live in pixel space and don't participate in
normalize/scale operations. Keeping them here avoids cross-coupling and makes
the helpers easy to reason about.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdomain_book_tools.layout.types import LayoutRegion, RegionType

if TYPE_CHECKING:
    from collections.abc import Iterable


def iou(a: LayoutRegion, b: LayoutRegion) -> float:
    """Intersection-over-union for two regions.

    Returns 0.0 if either input is degenerate (zero width or zero height),
    *including the case where two identical zero-area boxes are compared*.

    The mathematical IoU of two identical sets is 1.0 even when they have
    zero measure, but layout code here uses IoU as a "do these rectangles
    meaningfully overlap" signal — and a pair of zero-area boxes carries no
    spatial coverage to overlap on. Treating them as non-overlapping
    (returning 0.0) is the intentional convention for this module so
    deduplication / cluster passes don't collapse degenerate point-regions
    against each other. Callers that need exact-equality detection on
    layout regions should compare coordinates directly, not via IoU.

    The 0.0 floor is enforced two ways: the intersection-area early
    return (`if inter <= 0`) catches mismatched zero-area inputs; the
    union-area early return (`if union <= 0`) catches the matched case,
    where both inputs collapse to the same point/line.
    """
    inter_l = max(a.L, b.L)
    inter_t = max(a.T, b.T)
    inter_r = min(a.R, b.R)
    inter_b = min(a.B, b.B)
    iw = max(0, inter_r - inter_l)
    ih = max(0, inter_b - inter_t)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = a.area + b.area - inter
    if union <= 0:
        # Both inputs are zero-area and coincident. By module convention
        # (see docstring) this is not a meaningful overlap signal.
        return 0.0
    return inter / union


def contains(outer: LayoutRegion, inner: LayoutRegion, tol: int = 0) -> bool:
    """``inner`` is fully inside ``outer`` (with optional pixel tolerance)."""
    return (
        outer.L - tol <= inner.L
        and outer.T - tol <= inner.T
        and outer.R + tol >= inner.R
        and outer.B + tol >= inner.B
    )


def horizontal_overlap_ratio(a: LayoutRegion, b: LayoutRegion) -> float:
    """Width of horizontal overlap divided by the smaller of the two widths.

    Used to decide "is this caption directly under that figure" — they should
    share most of their horizontal extent.
    """
    inter_l = max(a.L, b.L)
    inter_r = min(a.R, b.R)
    inter_w = max(0, inter_r - inter_l)
    if inter_w == 0:
        return 0.0
    smaller = min(a.width, b.width)
    if smaller <= 0:
        return 0.0
    return inter_w / smaller


def caption_for_figure(
    figure: LayoutRegion,
    regions: Iterable[LayoutRegion],
    max_gap_px: int = 80,
    min_horizontal_overlap: float = 0.3,
    above: bool = False,
) -> LayoutRegion | None:
    """Return the caption/text region directly below (or above) ``figure``, if any.

    Heuristic per the plan's "Caption association distance" question — choose
    the closest region of type :attr:`RegionType.caption` (preferred) or
    :attr:`RegionType.text` (fallback) whose top edge is within ``max_gap_px``
    of the figure's bottom and whose horizontal overlap with the figure is at
    least ``min_horizontal_overlap`` of the smaller width.

    When ``above=True``, also consider regions immediately above the figure
    (`gap = figure.T - r.B`). Some Victorian and 18th-century book styles
    place captions, plate numbers, or headings above the figure rather than
    below; the default below-only behaviour is preserved for back-compat
    (L-06).
    """
    best: LayoutRegion | None = None
    best_gap = max_gap_px + 1
    best_is_caption = False
    for r in regions:
        if r is figure:
            continue
        if r.type not in (RegionType.caption, RegionType.text):
            continue
        gap_below = r.T - figure.B
        gap_above = figure.T - r.B if above else -1
        # Pick the smaller non-negative gap (i.e. whichever side the region
        # is on). If both somehow non-negative (overlapping figure), prefer
        # below for back-compat.
        candidates = [g for g in (gap_below, gap_above) if g >= 0]
        if not candidates:
            continue
        gap = min(candidates)
        if gap > max_gap_px:
            continue
        if horizontal_overlap_ratio(figure, r) < min_horizontal_overlap:
            continue
        is_caption = r.type == RegionType.caption
        # Prefer explicit captions over generic text; among same type, prefer
        # the smaller gap.
        if best is None:
            best, best_gap, best_is_caption = r, gap, is_caption
            continue
        if is_caption and not best_is_caption:
            best, best_gap, best_is_caption = r, gap, is_caption
            continue
        if is_caption == best_is_caption and gap < best_gap:
            best, best_gap = r, gap
    return best


def _detect_columns(regions: list[LayoutRegion]) -> list[list[LayoutRegion]] | None:
    """Cluster ``regions`` into left-to-right columns by horizontal gap.

    Returns a list of column groups (each itself a list of regions) when
    a stable multi-column structure is detected; returns ``None`` when
    the input is single-column or when at least one region spans more
    than one would-be column (which means columns can't be cleanly
    separated and a fall-back (T, L) sort is more honest than an
    arbitrary assignment).

    The algorithm sweeps the regions left-to-right by ``L`` and groups
    consecutive regions whose horizontal extents overlap into a single
    column. A clean break (the next region's ``L`` exceeds the running
    column's ``R``) starts a new column. If any region spans across a
    detected column boundary (``r.L < column_R`` and ``r.R > next.L``),
    we bail out of column detection.
    """
    if len(regions) < 2:
        return None
    # Sort by L for the sweep.
    by_left = sorted(regions, key=lambda r: r.L)
    columns: list[list[LayoutRegion]] = [[by_left[0]]]
    column_R = by_left[0].R
    for r in by_left[1:]:
        if column_R <= r.L:
            # Clean horizontal gap — start a new column.
            columns.append([r])
            column_R = r.R
        else:
            # Horizontal overlap with the running column — same column.
            columns[-1].append(r)
            column_R = max(column_R, r.R)
    if len(columns) < 2:
        return None
    # Sanity: a region must fit entirely inside its assigned column. A
    # full-width header (overlapping multiple would-be columns) ends up
    # in the first column in the sweep above, so ``column_R`` for that
    # column extends past the next column's ``L``. Detect that and bail.
    for i in range(len(columns) - 1):
        cur_R = max(r.R for r in columns[i])
        next_L = min(r.L for r in columns[i + 1])
        if cur_R > next_L:
            return None
    return columns


def region_reading_order(regions: Iterable[LayoutRegion]) -> list[LayoutRegion]:
    """Column-aware reading-order sort.

    Detects vertical column gaps via a left-to-right sweep on ``L``: a
    region whose left edge lies past the running column's right edge
    starts a new column. When two or more clean columns are detected,
    each column is sorted top-to-bottom (``T``, then ``L`` as a stable
    tiebreaker) and the columns are concatenated left-to-right. This
    matches typeset reading order for two- and three-column layouts.

    Falls back to a single (T, L) sort when:

    - Input has fewer than two regions.
    - No column gap is detected (single-column page).
    - At least one region spans across a detected column boundary
      (e.g. a full-page-width header above two body columns) — the
      column assignment can't be done cleanly so the legacy sort is
      used; the wide region naturally lands at the top of the result.

    No regions are silently dropped: every input is present in the
    returned list exactly once.
    """
    region_list = list(regions)
    columns = _detect_columns(region_list)
    if columns is None:
        return sorted(region_list, key=lambda r: (r.T, r.L))
    ordered: list[LayoutRegion] = []
    for column in columns:
        ordered.extend(sorted(column, key=lambda r: (r.T, r.L)))
    return ordered


__all__ = [
    "caption_for_figure",
    "contains",
    "horizontal_overlap_ratio",
    "iou",
    "region_reading_order",
]
