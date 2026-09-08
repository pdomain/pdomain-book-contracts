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
from typing import TYPE_CHECKING

from pdomain_book_contracts.annotation.provenance import KnowledgeState, LabelSource

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class ReviewMetadata:
    """Human-review state on a Word, Block (line), or Page.

    Fields:
        validated:            A reviewer has confirmed this item is correct.
        reviewer_note:        Optional free-text note left by the reviewer.
        flagged_for_attention: Flagged for follow-up review by a different
                               reviewer or for an automated pass.
        source:               Which source produced the answer this guards.
                              ``None`` means nothing has been recorded, which is
                              distinct from a recorded machine or human origin.
        state:                How much is known. Defaults to ``UNKNOWN`` so an
                              untouched record does not claim to be positive.
    """

    validated: bool = False
    reviewer_note: str | None = None
    flagged_for_attention: bool = False
    source: LabelSource | None = None
    state: KnowledgeState = KnowledgeState.UNKNOWN

    def to_dict(self) -> dict[str, bool | str | None]:
        return {
            "validated": self.validated,
            "reviewer_note": self.reviewer_note,
            "flagged_for_attention": self.flagged_for_attention,
            "source": self.source.value if self.source is not None else None,
            "state": self.state.value,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, object]) -> ReviewMetadata:
        raw_source = d.get("source")
        raw_state = d.get("state")
        return cls(
            validated=bool(d.get("validated", False)),
            reviewer_note=str(d["reviewer_note"])
            if d.get("reviewer_note") is not None
            else None,
            flagged_for_attention=bool(d.get("flagged_for_attention", False)),
            source=LabelSource(str(raw_source)) if raw_source is not None else None,
            state=KnowledgeState(str(raw_state))
            if raw_state is not None
            else KnowledgeState.UNKNOWN,
        )
