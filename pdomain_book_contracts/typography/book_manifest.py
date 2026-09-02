"""Immutable, source-neutral index for a book's page labeling bundles."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Annotated, Self, override

from pydantic import Field, ValidationInfo, field_validator, model_validator

from pdomain_book_tools.typography.exchange import ArtifactReference
from pdomain_book_tools.typography.review import canonical_json_bytes, validate_sha256
from pdomain_book_tools.typography.spans import CanonicalModel

if TYPE_CHECKING:
    from collections.abc import Mapping


_PageIndex = Annotated[int, Field(strict=True, ge=0)]


def _require_identifier(value: str, *, field_name: str) -> str:
    """Return a nonblank stable identifier."""
    if not value.strip():
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    return value


def _manifest_content_id(payload: Mapping[str, object]) -> str:
    """Return the content address for a manifest payload without its own ID."""
    payload_without_id = {
        key: value for key, value in payload.items() if key != "manifest_id"
    }
    return hashlib.sha256(canonical_json_bytes(payload_without_id)).hexdigest()


def _validate_confined_relative_path(value: str) -> str:
    """Validate a raw, confined POSIX path without touching the filesystem."""
    if any(segment in {".", ".."} for segment in value.split("/")):
        msg = "relative_path must be a nonempty safe relative POSIX path"
        raise ValueError(msg)
    ArtifactReference(
        artifact_id="book-manifest-path-validation",
        relative_path=value,
        sha256="0" * 64,
    )
    return value


class BookMatchRelationReference(CanonicalModel):
    """A match relation and the pages it affects in reading order."""

    relation_id: str
    page_ids: tuple[str, ...]
    match_graph_id: str
    match_graph_relative_path: str
    match_graph_sha256: str

    @override
    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        """Return a revalidated relation reference."""
        del deep
        payload = {**self.model_dump(), **(update or {})}
        return type(self).model_validate(payload)

    @field_validator("relation_id")
    @classmethod
    def _validate_relation_id(cls, value: str) -> str:
        return _require_identifier(value, field_name="relation_id")

    @field_validator("page_ids")
    @classmethod
    def _validate_page_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            msg = "relations must affect at least one page"
            raise ValueError(msg)
        if any(not page_id.strip() for page_id in value):
            msg = "relation page IDs must not be empty"
            raise ValueError(msg)
        if len(set(value)) != len(value):
            msg = "relation page IDs must be unique"
            raise ValueError(msg)
        return value

    @field_validator("match_graph_id", "match_graph_sha256")
    @classmethod
    def _validate_graph_hashes(cls, value: str, info: ValidationInfo) -> str:
        return validate_sha256(value, str(info.field_name))

    @field_validator("match_graph_relative_path")
    @classmethod
    def _validate_match_graph_relative_path(cls, value: str) -> str:
        return _validate_confined_relative_path(value)


class BookLabelingPage(CanonicalModel):
    """One page bundle pin and the book-level relations that touch that page."""

    page_index: _PageIndex
    page_id: str
    labeling_bundle_id: str
    materialization_relative_path: str
    materialization_sha256: str
    configuration_hash: str
    taxonomy_version: str
    taxonomy_hash: str
    relation_ids: tuple[str, ...] = ()

    @override
    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        """Return a revalidated page bundle pin."""
        del deep
        payload = {**self.model_dump(), **(update or {})}
        return type(self).model_validate(payload)

    @field_validator("page_id", "taxonomy_version")
    @classmethod
    def _validate_identifiers(cls, value: str, info: ValidationInfo) -> str:
        return _require_identifier(value, field_name=str(info.field_name))

    @field_validator(
        "labeling_bundle_id",
        "materialization_sha256",
        "configuration_hash",
        "taxonomy_hash",
    )
    @classmethod
    def _validate_hashes(cls, value: str, info: ValidationInfo) -> str:
        return validate_sha256(value, str(info.field_name))

    @field_validator("materialization_relative_path")
    @classmethod
    def _validate_materialization_relative_path(cls, value: str) -> str:
        return _validate_confined_relative_path(value)

    @field_validator("relation_ids")
    @classmethod
    def _validate_relation_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not relation_id.strip() for relation_id in value):
            msg = "page relation IDs must not be empty"
            raise ValueError(msg)
        if len(set(value)) != len(value):
            msg = "page relation IDs must be unique"
            raise ValueError(msg)
        return value


class BookLabelingManifest(CanonicalModel):
    """Content-addressed book index over independently materialized page bundles."""

    book_id: str
    manifest_id: str | None = None
    pages: tuple[BookLabelingPage, ...]
    match_relations: tuple[BookMatchRelationReference, ...] = ()

    @field_validator("book_id")
    @classmethod
    def _validate_book_id(cls, value: str) -> str:
        return _require_identifier(value, field_name="book_id")

    @override
    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        """Return a revalidated copy with a freshly derived manifest identity."""
        del deep
        payload = {**self.model_dump(), **(update or {}), "manifest_id": None}
        return type(self).model_validate(payload)

    @model_validator(mode="after")
    def _validate_manifest(self) -> Self:
        pages = tuple(
            BookLabelingPage.model_validate(page.model_dump(mode="json"))
            for page in self.pages
        )
        match_relations = tuple(
            BookMatchRelationReference.model_validate(relation.model_dump(mode="json"))
            for relation in self.match_relations
        )
        object.__setattr__(self, "pages", pages)
        object.__setattr__(self, "match_relations", match_relations)
        if not pages:
            msg = "book labeling manifests require at least one page"
            raise ValueError(msg)
        page_indexes = tuple(page.page_index for page in pages)
        if page_indexes != tuple(range(len(pages))):
            msg = "page indexes must be contiguous and ordered from zero"
            raise ValueError(msg)
        page_ids = tuple(page.page_id for page in pages)
        if len(set(page_ids)) != len(page_ids):
            msg = "page IDs must be unique"
            raise ValueError(msg)
        bundle_ids = tuple(page.labeling_bundle_id for page in pages)
        if len(set(bundle_ids)) != len(bundle_ids):
            msg = "labeling bundle IDs must be unique"
            raise ValueError(msg)
        taxonomy_identities = {
            (page.taxonomy_version, page.taxonomy_hash) for page in pages
        }
        if len(taxonomy_identities) != 1:
            msg = "all pages must use one taxonomy identity"
            raise ValueError(msg)

        relation_by_id = {
            relation.relation_id: relation for relation in match_relations
        }
        if len(relation_by_id) != len(match_relations):
            msg = "relation IDs must be unique"
            raise ValueError(msg)
        known_page_ids = set(page_ids)
        for relation in match_relations:
            if not set(relation.page_ids).issubset(known_page_ids):
                msg = "match relation page IDs must reference declared pages"
                raise ValueError(msg)
            referencing_page_ids = tuple(
                page.page_id
                for page in pages
                if relation.relation_id in page.relation_ids
            )
            if relation.page_ids != referencing_page_ids:
                msg = "match relation IDs must reference exactly the affected pages"
                raise ValueError(msg)
        if any(
            relation_id not in relation_by_id
            for page in pages
            for relation_id in page.relation_ids
        ):
            msg = "page relation IDs must reference declared match relations"
            raise ValueError(msg)

        expected = _manifest_content_id(self.model_dump(mode="json"))
        if self.manifest_id is not None and self.manifest_id != expected:
            msg = "manifest_id does not match the canonical manifest payload"
            raise ValueError(msg)
        object.__setattr__(self, "manifest_id", expected)
        return self
