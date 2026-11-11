from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.typography.book_manifest import (
    BookLabelingManifest,
    BookLabelingPage,
    BookMatchRelationReference,
)

TAXONOMY_HASH = "ee" * 32


def h(n: int) -> str:
    return f"{n:02x}" * 32


def page(index: int, /, **fields: object) -> BookLabelingPage:
    payload: dict[str, object] = {
        "page_index": index,
        "page_id": f"page-{index}",
        "labeling_bundle_id": h(10 + index),
        "materialization_relative_path": f"pages/{index}.json",
        "materialization_sha256": h(30 + index),
        "configuration_hash": h(50),
        "taxonomy_version": "t1",
        "taxonomy_hash": TAXONOMY_HASH,
        "relation_ids": (),
    }
    return BookLabelingPage.model_validate(payload | fields)


def relation(**fields: object) -> BookMatchRelationReference:
    payload: dict[str, object] = {
        "relation_id": "r1",
        "page_ids": ("page-0", "page-1"),
        "match_graph_id": h(70),
        "match_graph_relative_path": "graphs/g.json",
        "match_graph_sha256": h(71),
    }
    return BookMatchRelationReference.model_validate(payload | fields)


def manifest(**overrides: object) -> BookLabelingManifest:
    payload: dict[str, object] = {
        "book_id": "book",
        "pages": (
            page(0, relation_ids=("r1",)),
            page(1, relation_ids=("r1",)),
            page(2),
        ),
        "match_relations": (relation(),),
    }
    return BookLabelingManifest.model_validate(payload | overrides)


def test_manifest_derives_a_content_id_and_round_trips() -> None:
    built = manifest()
    assert built.manifest_id is not None
    restored = BookLabelingManifest.from_json_bytes(built.to_json_bytes())
    assert restored == built
    assert restored.manifest_id == built.manifest_id


def test_manifest_id_is_the_hash_of_the_payload_without_the_id() -> None:
    built = manifest()
    payload = built.model_dump(mode="json")
    del payload["manifest_id"]
    expected = hashlib.sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    assert built.manifest_id == expected


def test_manifest_id_depends_on_content_and_page_order() -> None:
    first = manifest()
    other_book = manifest(book_id="other")
    assert first.manifest_id != other_book.manifest_id
    assert manifest(match_relations=(), pages=(page(0),)).manifest_id != (
        manifest(match_relations=(), pages=(page(0), page(1))).manifest_id
    )


def test_a_stale_manifest_id_is_rejected() -> None:
    payload = manifest().model_dump(mode="json")
    payload["book_id"] = "other"
    with pytest.raises(ValidationError, match="manifest_id does not match"):
        BookLabelingManifest.model_validate(payload)


def test_model_copy_rederives_the_manifest_id_instead_of_keeping_a_stale_one() -> None:
    built = manifest()
    copied = built.model_copy(update={"book_id": "other"})
    assert copied.book_id == "other"
    assert copied.manifest_id == manifest(book_id="other").manifest_id
    assert copied.manifest_id != built.manifest_id


def test_model_copy_revalidates_the_update() -> None:
    with pytest.raises(ValidationError, match="book_id must not be empty"):
        manifest().model_copy(update={"book_id": " "})


def test_page_and_relation_model_copy_revalidate() -> None:
    assert page(0).model_copy(update={"page_id": "z"}).page_id == "z"
    with pytest.raises(ValidationError, match="page_id must not be empty"):
        page(0).model_copy(update={"page_id": ""})
    assert relation().model_copy(update={"relation_id": "z"}).relation_id == "z"
    with pytest.raises(ValidationError, match="at least one page"):
        relation().model_copy(update={"page_ids": ()})


def test_manifest_requires_at_least_one_page() -> None:
    with pytest.raises(ValidationError, match="at least one page"):
        manifest(pages=(), match_relations=())


def test_page_indexes_must_be_contiguous_from_zero_in_order() -> None:
    with pytest.raises(ValidationError, match="contiguous and ordered from zero"):
        manifest(pages=(page(1),), match_relations=())
    with pytest.raises(ValidationError, match="contiguous and ordered from zero"):
        manifest(pages=(page(0), page(2)), match_relations=())
    with pytest.raises(ValidationError, match="contiguous and ordered from zero"):
        manifest(pages=(page(1), page(0)), match_relations=())


def test_page_ids_and_bundle_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="page IDs must be unique"):
        manifest(pages=(page(0), page(1, page_id="page-0")), match_relations=())
    with pytest.raises(ValidationError, match="bundle IDs must be unique"):
        manifest(pages=(page(0), page(1, labeling_bundle_id=h(10))), match_relations=())


def test_all_pages_must_share_one_taxonomy_identity() -> None:
    with pytest.raises(ValidationError, match="one taxonomy identity"):
        manifest(pages=(page(0), page(1, taxonomy_version="t2")), match_relations=())
    with pytest.raises(ValidationError, match="one taxonomy identity"):
        manifest(pages=(page(0), page(1, taxonomy_hash=h(1))), match_relations=())


def test_relation_ids_must_be_unique() -> None:
    pages = (page(0, relation_ids=("r1",)), page(1, relation_ids=("r1",)))
    with pytest.raises(ValidationError, match="relation IDs must be unique"):
        manifest(pages=pages, match_relations=(relation(), relation()))


def test_relations_must_reference_declared_pages() -> None:
    with pytest.raises(ValidationError, match="reference declared pages"):
        manifest(match_relations=(relation(page_ids=("page-0", "ghost")),))


def test_relation_and_page_references_must_agree_exactly() -> None:
    with pytest.raises(ValidationError, match="reference exactly the affected pages"):
        manifest(
            pages=(page(0, relation_ids=("r1",)), page(1), page(2)),
        )
    with pytest.raises(ValidationError, match="reference exactly the affected pages"):
        manifest(
            pages=(
                page(0, relation_ids=("r1",)),
                page(1, relation_ids=("r1",)),
                page(2, relation_ids=("r1",)),
            ),
        )


def test_relation_page_order_must_follow_manifest_page_order() -> None:
    with pytest.raises(ValidationError, match="reference exactly the affected pages"):
        manifest(match_relations=(relation(page_ids=("page-1", "page-0")),))


def test_pages_cannot_reference_undeclared_relations() -> None:
    with pytest.raises(ValidationError, match="reference declared match relations"):
        manifest(
            pages=(page(0, relation_ids=("ghost",)),),
            match_relations=(),
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"page_index": -1}, "page_index"),
        ({"page_id": " "}, "page_id must not be empty"),
        ({"taxonomy_version": ""}, "taxonomy_version must not be empty"),
        ({"labeling_bundle_id": "abc"}, "labeling_bundle_id must be a 64"),
        ({"materialization_sha256": "zz" * 32}, "materialization_sha256 must be"),
        ({"configuration_hash": ""}, "configuration_hash must be"),
        ({"taxonomy_hash": "1"}, "taxonomy_hash must be"),
        ({"relation_ids": ("a", "a")}, "relation IDs must be unique"),
        ({"relation_ids": (" ",)}, "relation IDs must not be empty"),
    ],
)
def test_page_field_rejections(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        page(0, **overrides)


def test_page_hashes_are_normalised_to_lowercase() -> None:
    assert page(0, materialization_sha256="AB" * 32).materialization_sha256 == "ab" * 32


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"relation_id": " "}, "relation_id must not be empty"),
        ({"page_ids": ()}, "at least one page"),
        ({"page_ids": ("a", " ")}, "page IDs must not be empty"),
        ({"page_ids": ("a", "a")}, "page IDs must be unique"),
        ({"match_graph_id": "1"}, "match_graph_id must be"),
        ({"match_graph_sha256": "1"}, "match_graph_sha256 must be"),
    ],
)
def test_relation_field_rejections(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        relation(**overrides)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/abs/x.json",
        "../x.json",
        "a/../x.json",
        "a/./x.json",
        "./x.json",
        "a\\x.json",
        "C:/x.json",
    ],
)
def test_manifest_paths_must_be_confined_relative_posix_paths(path: str) -> None:
    with pytest.raises(ValidationError, match="safe relative POSIX path"):
        page(0, materialization_relative_path=path)
    with pytest.raises(ValidationError, match="safe relative POSIX path"):
        relation(match_graph_relative_path=path)


def test_manifest_accepts_nested_confined_paths() -> None:
    nested = page(0, materialization_relative_path="book/pages/0000.json")
    assert nested.materialization_relative_path == "book/pages/0000.json"
