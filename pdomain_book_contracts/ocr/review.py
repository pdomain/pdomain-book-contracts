"""Human-review metadata for OCR words, lines (blocks), and pages.

This module is foundation-level: it carries no per-app logic and is
designed to be shared across every consumer of pdomain-book-tools data models
(labeler, pgdp-prep, proofreader, simple-ocr-gui).

The dataclass is intentionally minimal in this first revision. A future
extension migrates ``ReviewMetadata`` to a list of per-pass review
records (P1/P2/P3/F1/F2 in Distributed Proofreaders parlance) once the
proofreader app spec lands. Until then, treat it as a single most-recent
review state.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewMetadata:
    """Human-review state on a Word, Block (line), or Page.

    Fields:
        validated:            A reviewer has confirmed this item is correct.
        reviewer_note:        Optional free-text note left by the reviewer.
        flagged_for_attention: Flagged for follow-up review by a different
                               reviewer or for an automated pass.
    """

    validated: bool = False
    reviewer_note: str | None = None
    flagged_for_attention: bool = False

    def to_dict(self) -> dict[str, bool | str | None]:
        return {
            "validated": self.validated,
            "reviewer_note": self.reviewer_note,
            "flagged_for_attention": self.flagged_for_attention,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> ReviewMetadata:
        return cls(
            validated=bool(d.get("validated", False)),
            reviewer_note=str(d["reviewer_note"])
            if d.get("reviewer_note") is not None
            else None,
            flagged_for_attention=bool(d.get("flagged_for_attention", False)),
        )
