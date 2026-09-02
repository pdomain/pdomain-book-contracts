from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GtOrphans:
    """GT entries that could not be matched to any OCR content during GtMapped.

    Preserved so the labeler can surface unmatched ground truth to the reviewer.
    Pages with no GT mapping will never populate this — it stays None on Page.
    """

    words: list[object] = field(default_factory=list)
    lines: list[object] = field(default_factory=list)
    paragraphs: list[object] = field(default_factory=list)
    page: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True if all orphan collections are empty."""
        return not (self.words or self.lines or self.paragraphs or self.page)
