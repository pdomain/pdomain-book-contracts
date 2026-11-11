from __future__ import annotations

import pytest

from pdomain_book_contracts.ocr.gt_orphans import GtOrphans


def test_new_orphans_are_empty() -> None:
    assert GtOrphans().is_empty()


@pytest.mark.parametrize(
    "orphans",
    [
        GtOrphans(words=["w"]),
        GtOrphans(lines=["l"]),
        GtOrphans(paragraphs=["p"]),
        GtOrphans(page=["text"]),
    ],
)
def test_any_populated_collection_makes_orphans_non_empty(orphans: GtOrphans) -> None:
    assert not orphans.is_empty()


def test_collections_are_not_shared_between_instances() -> None:
    first = GtOrphans()
    first.page.append("stray")
    assert GtOrphans().is_empty()
