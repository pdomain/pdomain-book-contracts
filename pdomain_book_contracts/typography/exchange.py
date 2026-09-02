"""Content-addressed portable typography bundle models."""

from __future__ import annotations

import hashlib
import string
from enum import StrEnum
from itertools import pairwise
from pathlib import PurePosixPath
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from pdomain_book_contracts.typography.review import (
    REVIEW_CONTRACT_VERSION,
    CorrectionDecision,
    LabelState,
    TypographyCorrection,
    TypographyTaxonomy,
    WordTypography,
    canonical_json_bytes,
    validate_sha256,
)
from pdomain_book_contracts.typography.spans import CanonicalModel

_Coordinate = Annotated[float, Field(strict=True, allow_inf_nan=False)]
_StrictIndex = Annotated[int, Field(strict=True, ge=0)]


class SourceOrientation(StrEnum):
    """Orientation of the source image before a geometry transform."""

    UPRIGHT = "upright"
    ROTATE_90_CLOCKWISE = "rotate_90_clockwise"
    ROTATE_180 = "rotate_180"
    ROTATE_90_COUNTERCLOCKWISE = "rotate_90_counterclockwise"


class ModelRunPurpose(StrEnum):
    """The page-analysis role performed by a recorded model run."""

    OCR = "ocr"
    PAGE_REGION = "page_region"


class CoordinateTransformStage(StrEnum):
    """A required stage in the portable source-image geometry chain."""

    ORIENTATION = "orientation"
    CROP = "crop"


class ArtifactReference(CanonicalModel):
    """Path-safe content-addressed artifact metadata with no filesystem I/O."""

    artifact_id: str
    relative_path: str
    sha256: str
    media_type: str | None = None

    @field_validator("artifact_id")
    @classmethod
    def _require_artifact_id(cls, value: str) -> str:
        if not value.strip():
            msg = "artifact_id must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or "\\" in value
            or (len(value) >= 2 and value[0].isalpha() and value[1] == ":")
            or path.is_absolute()
            or ".." in path.parts
            or "." in path.parts
        ):
            msg = "relative_path must be a nonempty safe relative POSIX path"
            raise ValueError(msg)
        return value

    @field_validator("sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        return validate_sha256(value, "sha256")

    def verify_bytes(self, payload: bytes) -> bool:
        """Return whether in-memory bytes match this artifact's declared hash."""
        return hashlib.sha256(payload).hexdigest() == self.sha256


class ReplacementArtifact(CanonicalModel):
    """Path-safe declared output artifact created by an approved correction."""

    artifact_id: str
    relative_path: str
    sha256: str
    byte_size: Annotated[int, Field(strict=True, ge=0)]
    media_type: str

    @field_validator("artifact_id", "media_type")
    @classmethod
    def _require_value(cls, value: str) -> str:
        if not value.strip():
            msg = "replacement artifact values must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        ArtifactReference(
            artifact_id="validation",
            relative_path=value,
            sha256="0" * 64,
            media_type=None,
        )
        return value

    @field_validator("sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        return validate_sha256(value, "sha256")


class ModelRun(CanonicalModel):
    """Reproducibility metadata for a model-generated proposal."""

    run_id: str
    model_name: str
    model_version: str
    purpose: ModelRunPurpose | None = None
    input_artifact_sha256: str | None = None
    output_artifact_sha256: str | None = None
    model_artifact_sha256: str | None = None
    config_sha256: str | None = None
    preprocessing_sha256: str | None = None

    @field_validator("run_id", "model_name", "model_version")
    @classmethod
    def _require_value(cls, value: str) -> str:
        if not value.strip():
            msg = "model run identifiers must not be empty"
            raise ValueError(msg)
        return value

    @field_validator(
        "input_artifact_sha256",
        "output_artifact_sha256",
        "model_artifact_sha256",
        "config_sha256",
        "preprocessing_sha256",
    )
    @classmethod
    def _validate_artifact_hash(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        return validate_sha256(value, str(getattr(info, "field_name", "sha256")))


class CoordinateTransform(CanonicalModel):
    """Named affine transform between portable coordinate spaces."""

    transform_id: str
    stage: CoordinateTransformStage | None = None
    source_space: str
    target_space: str
    source_coordinate_space_id: str
    target_coordinate_space_id: str
    source_orientation: SourceOrientation
    source_artifact_sha256: str
    target_artifact_sha256: str
    crop_recipe: str
    crop_recipe_version: str
    padding_px: Annotated[int, Field(strict=True, ge=0)]
    resampling: str
    preprocessing_sha256: str
    transform_version: str
    affine: tuple[
        _Coordinate, _Coordinate, _Coordinate, _Coordinate, _Coordinate, _Coordinate
    ]
    source_width: Annotated[int, Field(strict=True, gt=0)] | None = None
    source_height: Annotated[int, Field(strict=True, gt=0)] | None = None
    target_width: Annotated[int, Field(strict=True, gt=0)] | None = None
    target_height: Annotated[int, Field(strict=True, gt=0)] | None = None

    @field_validator(
        "transform_id",
        "source_space",
        "target_space",
        "source_coordinate_space_id",
        "target_coordinate_space_id",
    )
    @classmethod
    def _require_value(cls, value: str) -> str:
        if not value.strip():
            msg = "coordinate transform values must not be empty"
            raise ValueError(msg)
        return value

    @field_validator(
        "source_artifact_sha256", "target_artifact_sha256", "preprocessing_sha256"
    )
    @classmethod
    def _validate_hash(cls, value: str, info: object) -> str:
        return validate_sha256(value, str(getattr(info, "field_name", "sha256")))

    @field_validator(
        "crop_recipe", "crop_recipe_version", "resampling", "transform_version"
    )
    @classmethod
    def _require_recipe_value(cls, value: str) -> str:
        if not value.strip():
            msg = "transform recipe values must not be empty"
            raise ValueError(msg)
        return value


class Evidence(CanonicalModel):
    """A precise half-open byte range supporting a label decision."""

    evidence_id: str
    artifact_id: str
    artifact_sha256: str
    byte_start: _StrictIndex
    byte_end: _StrictIndex
    note: str | None = None

    @field_validator("evidence_id", "artifact_id")
    @classmethod
    def _require_identifier(cls, value: str) -> str:
        if not value.strip():
            msg = "evidence identifiers must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("artifact_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        return validate_sha256(value, "artifact_sha256")

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.byte_start >= self.byte_end:
            msg = "evidence must use a nonempty half-open byte range"
            raise ValueError(msg)
        return self


class WordGeometry(CanonicalModel):
    """Optional axis-aligned word geometry in the bundle's declared space."""

    word_id: str
    word_revision: Annotated[int, Field(strict=True, ge=0)]
    page_sha256: str
    page_head_sha256: str
    image_artifact_sha256: str
    x0: _Coordinate
    y0: _Coordinate
    x1: _Coordinate
    y1: _Coordinate
    coordinate_space: str = "image_pixels"
    coordinate_space_id: str
    transform_id: str
    source_orientation: SourceOrientation

    @field_validator("word_id")
    @classmethod
    def _validate_word_id(cls, value: str) -> str:
        if not value.strip():
            msg = "word_id must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("page_sha256", "page_head_sha256", "image_artifact_sha256")
    @classmethod
    def _validate_hash(cls, value: str, info: object) -> str:
        return validate_sha256(value, str(getattr(info, "field_name", "sha256")))

    @model_validator(mode="after")
    def _validate_bounds(self) -> Self:
        if (
            not self.word_id.strip()
            or not self.coordinate_space.strip()
            or not self.coordinate_space_id.strip()
            or not self.transform_id.strip()
        ):
            msg = "geometry identifiers must not be empty"
            raise ValueError(msg)
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            msg = "geometry must have positive width and height"
            raise ValueError(msg)
        return self


class PageGeometry(CanonicalModel):
    """Reviewed page geometry and the model runs that generated it."""

    page_id: str
    page_sha256: str
    source_image_artifact_sha256: str
    source_image_width: Annotated[int, Field(strict=True, gt=0)]
    source_image_height: Annotated[int, Field(strict=True, gt=0)]
    image_artifact_sha256: str
    page_head_sha256: str
    ocr_artifact_sha256: str
    page_region_artifact_sha256: str
    coordinate_space: str
    coordinate_space_id: str
    source_orientation: SourceOrientation
    transform_ids: tuple[str, ...]
    ocr_model_run_id: str
    page_region_model_run_id: str
    image_width: Annotated[int, Field(strict=True, gt=0)]
    image_height: Annotated[int, Field(strict=True, gt=0)]

    @field_validator(
        "page_id",
        "coordinate_space",
        "coordinate_space_id",
        "ocr_model_run_id",
        "page_region_model_run_id",
    )
    @classmethod
    def _require_identifier(cls, value: str) -> str:
        if not value.strip():
            msg = "page geometry identifiers must not be empty"
            raise ValueError(msg)
        return value

    @field_validator(
        "page_sha256",
        "source_image_artifact_sha256",
        "image_artifact_sha256",
        "page_head_sha256",
        "ocr_artifact_sha256",
        "page_region_artifact_sha256",
    )
    @classmethod
    def _validate_hash(cls, value: str, info: object) -> str:
        return validate_sha256(value, str(getattr(info, "field_name", "sha256")))

    @field_validator("transform_ids")
    @classmethod
    def _validate_transform_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if (
            not value
            or any(not transform_id.strip() for transform_id in value)
            or len(set(value)) != len(value)
        ):
            msg = "page geometry transform IDs must be nonempty and unique"
            raise ValueError(msg)
        return value


def _bundle_content_id(payload: dict[str, object]) -> str:
    """Hash canonical JSON payload after omitting its self-referential ID."""
    payload_without_id = {
        key: value for key, value in payload.items() if key != "bundle_id"
    }
    return hashlib.sha256(canonical_json_bytes(payload_without_id)).hexdigest()


def _model_runs_by_id(
    model_runs: tuple[ModelRun, ...],
    artifact_hashes: set[str],
    *,
    require_complete: bool,
) -> dict[str, ModelRun]:
    """Validate model artifact bindings and return runs by their stable ID."""
    runs = {run.run_id: run for run in model_runs}
    if len(runs) != len(model_runs):
        msg = "model run IDs must be unique"
        raise ValueError(msg)
    for run in model_runs:
        run_hashes = (
            run.input_artifact_sha256,
            run.output_artifact_sha256,
            run.model_artifact_sha256,
            run.config_sha256,
            run.preprocessing_sha256,
        )
        if require_complete and (
            run.purpose is None or any(value is None for value in run_hashes)
        ):
            msg = "geometry model runs require purpose, model, config, and preprocessing hashes"
            raise ValueError(msg)
        if any(
            value is not None and value not in artifact_hashes for value in run_hashes
        ):
            msg = "model run hashes must reference declared artifacts"
            raise ValueError(msg)
    return runs


def _transforms_by_id(
    transforms: tuple[CoordinateTransform, ...], artifact_hashes: set[str]
) -> dict[str, CoordinateTransform]:
    """Validate transform artifact bindings and return transforms by ID."""
    by_id = {transform.transform_id: transform for transform in transforms}
    if len(by_id) != len(transforms):
        msg = "coordinate transform IDs must be unique"
        raise ValueError(msg)
    if any(
        transform.source_artifact_sha256 not in artifact_hashes
        or transform.target_artifact_sha256 not in artifact_hashes
        or transform.preprocessing_sha256 not in artifact_hashes
        for transform in transforms
    ):
        msg = "coordinate transforms must reference declared artifacts"
        raise ValueError(msg)
    return by_id


def _validate_page_geometry(
    page_geometry: PageGeometry,
    transforms: dict[str, CoordinateTransform],
    model_runs: dict[str, ModelRun],
    artifact_hashes: set[str],
) -> None:
    """Validate the exact model and transform chain behind returned geometry."""
    if not {
        page_geometry.page_sha256,
        page_geometry.source_image_artifact_sha256,
        page_geometry.image_artifact_sha256,
        page_geometry.page_head_sha256,
        page_geometry.ocr_artifact_sha256,
        page_geometry.page_region_artifact_sha256,
    }.issubset(artifact_hashes):
        msg = "page geometry hashes must reference declared artifacts"
        raise ValueError(msg)
    transform_chain: list[CoordinateTransform] = []
    for transform_id in page_geometry.transform_ids:
        transform = transforms.get(transform_id)
        if transform is None:
            msg = "page geometry must reference declared coordinate transforms"
            raise ValueError(msg)
        transform_chain.append(transform)
    if tuple(transform.stage for transform in transform_chain) != (
        CoordinateTransformStage.ORIENTATION,
        CoordinateTransformStage.CROP,
    ):
        msg = "page geometry requires explicit orientation and crop transform stages"
        raise ValueError(msg)
    if any(
        earlier.target_space != later.source_space
        or earlier.target_coordinate_space_id != later.source_coordinate_space_id
        or earlier.target_artifact_sha256 != later.source_artifact_sha256
        for earlier, later in pairwise(transform_chain)
    ):
        msg = "page geometry transforms must form a contiguous artifact chain"
        raise ValueError(msg)
    final_transform = transform_chain[-1]
    orientation_transform = transform_chain[0]
    transform_bounds = (
        orientation_transform.source_width,
        orientation_transform.source_height,
        orientation_transform.target_width,
        orientation_transform.target_height,
        final_transform.source_width,
        final_transform.source_height,
        final_transform.target_width,
        final_transform.target_height,
    )
    if any(value is None for value in transform_bounds):
        msg = "page geometry transforms require declared source and target bounds"
        raise ValueError(msg)
    orientation_target_size = (
        (page_geometry.source_image_height, page_geometry.source_image_width)
        if page_geometry.source_orientation
        in {
            SourceOrientation.ROTATE_90_CLOCKWISE,
            SourceOrientation.ROTATE_90_COUNTERCLOCKWISE,
        }
        else (page_geometry.source_image_width, page_geometry.source_image_height)
    )
    if (
        (orientation_transform.source_width, orientation_transform.source_height)
        != (page_geometry.source_image_width, page_geometry.source_image_height)
        or (orientation_transform.target_width, orientation_transform.target_height)
        != orientation_target_size
        or (final_transform.source_width, final_transform.source_height)
        != (orientation_transform.target_width, orientation_transform.target_height)
        or (final_transform.target_width, final_transform.target_height)
        != (page_geometry.image_width, page_geometry.image_height)
    ):
        msg = "page geometry transform bounds must match the declared image chain"
        raise ValueError(msg)
    identity_affine = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    crop_bounds_unchanged = (
        final_transform.source_width,
        final_transform.source_height,
    ) == (
        final_transform.target_width,
        final_transform.target_height,
    )
    if final_transform.crop_recipe == "identity" and (
        final_transform.affine != identity_affine or not crop_bounds_unchanged
    ):
        msg = "identity crop must use an identity affine and unchanged bounds"
        raise ValueError(msg)
    if final_transform.affine == identity_affine and not crop_bounds_unchanged:
        msg = "identity crop transform bounds must be unchanged"
        raise ValueError(msg)
    expected_orientation_affines = {
        SourceOrientation.UPRIGHT: (1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        SourceOrientation.ROTATE_90_CLOCKWISE: (
            0.0,
            -1.0,
            float(page_geometry.source_image_height),
            1.0,
            0.0,
            0.0,
        ),
        SourceOrientation.ROTATE_180: (
            -1.0,
            0.0,
            float(page_geometry.source_image_width),
            0.0,
            -1.0,
            float(page_geometry.source_image_height),
        ),
        SourceOrientation.ROTATE_90_COUNTERCLOCKWISE: (
            0.0,
            1.0,
            0.0,
            -1.0,
            0.0,
            float(page_geometry.source_image_width),
        ),
    }
    if (
        orientation_transform.affine
        != expected_orientation_affines[page_geometry.source_orientation]
    ):
        msg = "orientation-stage affine does not match source orientation"
        raise ValueError(msg)
    if (
        orientation_transform.source_artifact_sha256
        != page_geometry.source_image_artifact_sha256
        or orientation_transform.source_orientation != page_geometry.source_orientation
        or final_transform.source_orientation is not SourceOrientation.UPRIGHT
        or final_transform.target_space != page_geometry.coordinate_space
        or final_transform.target_coordinate_space_id
        != page_geometry.coordinate_space_id
        or final_transform.target_artifact_sha256 != page_geometry.image_artifact_sha256
    ):
        msg = "page geometry must match its final coordinate transform"
        raise ValueError(msg)
    ocr_run = model_runs.get(page_geometry.ocr_model_run_id)
    region_run = model_runs.get(page_geometry.page_region_model_run_id)
    if (
        ocr_run is None
        or ocr_run.purpose is not ModelRunPurpose.OCR
        or region_run is None
        or region_run.purpose is not ModelRunPurpose.PAGE_REGION
    ):
        msg = "page geometry must reference declared OCR and page-region model runs"
        raise ValueError(msg)
    if (
        ocr_run.input_artifact_sha256 != page_geometry.image_artifact_sha256
        or ocr_run.output_artifact_sha256 != page_geometry.ocr_artifact_sha256
        or region_run.input_artifact_sha256 != page_geometry.image_artifact_sha256
        or region_run.output_artifact_sha256
        != page_geometry.page_region_artifact_sha256
        or final_transform.preprocessing_sha256 != ocr_run.preprocessing_sha256
    ):
        msg = "page geometry must bind model inputs, outputs, and OCR preprocessing"
        raise ValueError(msg)


def _validate_word_geometry(
    geometry: tuple[WordGeometry, ...],
    page_geometry: PageGeometry,
    transforms: dict[str, CoordinateTransform],
) -> None:
    """Validate word boxes against one returned reviewed page geometry."""
    word_ids = {item.word_id for item in geometry}
    if len(word_ids) != len(geometry):
        msg = "geometry word IDs must be unique"
        raise ValueError(msg)
    for item in geometry:
        transform = transforms.get(item.transform_id)
        if transform is None or item.transform_id not in page_geometry.transform_ids:
            msg = "geometry must reference a transform in the declared page chain"
            raise ValueError(msg)
        if (
            item.page_sha256 != page_geometry.page_sha256
            or item.page_head_sha256 != page_geometry.page_head_sha256
            or item.image_artifact_sha256 != page_geometry.image_artifact_sha256
            or item.coordinate_space != page_geometry.coordinate_space
            or item.coordinate_space_id != page_geometry.coordinate_space_id
            or item.source_orientation != page_geometry.source_orientation
            or transform.target_space != item.coordinate_space
            or transform.target_coordinate_space_id != item.coordinate_space_id
            or transform.target_artifact_sha256 != item.image_artifact_sha256
        ):
            msg = "word geometry must match the returned page geometry and transform"
            raise ValueError(msg)
        if (
            item.x0 < 0
            or item.y0 < 0
            or item.x1 > page_geometry.image_width
            or item.y1 > page_geometry.image_height
        ):
            msg = "word geometry must remain within the returned image bounds"
            raise ValueError(msg)


class LabelingBundle(CanonicalModel):
    """Complete portable review input for a page, optionally with geometry."""

    bundle_id: str | None = None
    schema_version: str
    configuration_hash: str
    taxonomy: TypographyTaxonomy
    page_id: str
    page_sha256: str
    image_sha256: str
    text_sha256: str
    page_head_sha256: str
    artifacts: tuple[ArtifactReference, ...]
    words: tuple[WordTypography, ...]
    page_geometry: PageGeometry | None = None
    geometry: tuple[WordGeometry, ...] | None = None
    evidence: tuple[Evidence, ...] = ()
    model_runs: tuple[ModelRun, ...] = ()
    coordinate_transforms: tuple[CoordinateTransform, ...] = ()

    @field_validator("page_id")
    @classmethod
    def _require_page_id(cls, value: str) -> str:
        if not value.strip():
            msg = "page_id must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        if value != REVIEW_CONTRACT_VERSION:
            msg = "schema_version must equal the review contract version"
            raise ValueError(msg)
        return value

    @field_validator(
        "configuration_hash",
        "page_sha256",
        "image_sha256",
        "text_sha256",
        "page_head_sha256",
    )
    @classmethod
    def _validate_hash(cls, value: str, info: object) -> str:
        return validate_sha256(value, str(getattr(info, "field_name", "sha256")))

    @model_validator(mode="after")
    def _validate_bundle(self) -> Self:
        for word in self.words:
            word.validate_taxonomy(self.taxonomy)
            if (
                word.page_content_sha256 != self.page_sha256
                or word.image_artifact_sha256 != self.image_sha256
            ):
                msg = "word page and image hashes must match the containing bundle"
                raise ValueError(msg)
        artifact_hashes = {
            artifact.artifact_id: artifact.sha256 for artifact in self.artifacts
        }
        if len(artifact_hashes) != len(self.artifacts):
            msg = "bundle artifact IDs must be unique"
            raise ValueError(msg)
        for item in self.evidence:
            if artifact_hashes.get(item.artifact_id) != item.artifact_sha256:
                msg = "evidence artifact ID and hash must identify a declared artifact"
                raise ValueError(msg)
        evidence_ids = {item.evidence_id for item in self.evidence}
        if any(
            not set(word.source_evidence_ids).issubset(evidence_ids)
            for word in self.words
        ):
            msg = "word source evidence IDs must be declared by the containing bundle"
            raise ValueError(msg)
        if any(
            span.alignment_evidence_id not in evidence_ids
            for word in self.words
            for span in word.spans
        ):
            msg = (
                "span alignment evidence IDs must be declared by the containing bundle"
            )
            raise ValueError(msg)
        word_ids = {word.word_id for word in self.words}
        if len(word_ids) != len(self.words):
            msg = "bundle word IDs must be unique"
            raise ValueError(msg)
        artifact_hash_values = set(artifact_hashes.values())
        _model_runs_by_id(
            self.model_runs,
            artifact_hash_values,
            require_complete=self.page_geometry is not None,
        )
        transforms = _transforms_by_id(self.coordinate_transforms, artifact_hash_values)
        if (self.page_geometry is None) != (self.geometry is None):
            msg = "inbound page and word geometry must be present together"
            raise ValueError(msg)
        if self.page_geometry is not None and self.geometry is not None:
            if (
                self.page_geometry.page_id != self.page_id
                or self.page_geometry.page_sha256 != self.page_sha256
                or self.page_geometry.image_artifact_sha256 != self.image_sha256
                or self.page_geometry.page_head_sha256 != self.page_head_sha256
            ):
                msg = "inbound page geometry must match bundle page provenance"
                raise ValueError(msg)
            _validate_page_geometry(
                self.page_geometry,
                transforms,
                _model_runs_by_id(
                    self.model_runs, artifact_hash_values, require_complete=True
                ),
                artifact_hash_values,
            )
            _validate_word_geometry(self.geometry, self.page_geometry, transforms)
            if any(item.word_id not in word_ids for item in self.geometry):
                msg = "geometry must reference a declared word"
                raise ValueError(msg)
            for item in self.geometry:
                word = next(word for word in self.words if word.word_id == item.word_id)
                if (
                    item.word_revision != word.word_revision
                    or item.page_sha256 != self.page_sha256
                    or item.page_head_sha256 != self.page_head_sha256
                    or item.image_artifact_sha256 != self.image_sha256
                ):
                    msg = (
                        "geometry must match its word, bundle, and coordinate transform"
                    )
                    raise ValueError(msg)
        expected = _bundle_content_id(self.model_dump(mode="json"))
        if self.bundle_id is not None and self.bundle_id != expected:
            msg = "bundle_id does not match the canonical bundle payload"
            raise ValueError(msg)
        object.__setattr__(self, "bundle_id", expected)
        return self

    def rebuild(self, **updates: object) -> Self:
        """Apply updates through validation and derive a new content ID.

        Do not use Pydantic's ``model_copy`` for content-addressed bundles:
        it intentionally skips validation and can preserve a stale ``bundle_id``.
        """
        data = self.model_dump(mode="json")
        data.update(updates)
        data["bundle_id"] = None
        return type(self).model_validate(data)


class CorrectionBundle(CanonicalModel):
    """Content-addressed reviewed corrections and optional returned geometry."""

    bundle_id: str | None = None
    schema_version: str
    configuration_hash: str
    labeling_bundle_id: str
    corrections: tuple[TypographyCorrection, ...]
    replacement_artifacts: tuple[ReplacementArtifact, ...] = ()
    page_geometry: PageGeometry | None = None
    geometry: tuple[WordGeometry, ...] | None = None
    model_runs: tuple[ModelRun, ...] = ()
    coordinate_transforms: tuple[CoordinateTransform, ...] = ()

    @field_validator("labeling_bundle_id")
    @classmethod
    def _require_labeling_bundle_id(cls, value: str) -> str:
        if len(value) != 64 or any(char not in string.hexdigits for char in value):
            msg = "labeling_bundle_id must be a 64-character hexadecimal content ID"
            raise ValueError(msg)
        return value.lower()

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        if value != REVIEW_CONTRACT_VERSION:
            msg = "schema_version must equal the review contract version"
            raise ValueError(msg)
        return value

    @field_validator("configuration_hash")
    @classmethod
    def _validate_configuration_hash(cls, value: str) -> str:
        return validate_sha256(value, "configuration_hash")

    @model_validator(mode="after")
    def _validate_bundle(self) -> Self:
        correction_ids = {correction.correction_id for correction in self.corrections}
        if len(correction_ids) != len(self.corrections):
            msg = "correction IDs must be unique"
            raise ValueError(msg)
        replacement_ids = {
            artifact.artifact_id for artifact in self.replacement_artifacts
        }
        if len(replacement_ids) != len(self.replacement_artifacts):
            msg = "replacement artifact IDs must be unique"
            raise ValueError(msg)
        corrections_by_word: dict[str, list[TypographyCorrection]] = {}
        for correction in self.corrections:
            corrections_by_word.setdefault(correction.word_id, []).append(correction)
        if any(
            current.base_page_sha256 != previous.effective_page_sha256
            or current.base_image_sha256 != previous.effective_image_sha256
            or current.page_head_sha256 != previous.effective_page_head_sha256
            for previous, current in pairwise(self.corrections)
        ):
            msg = "correction page bases must follow the preceding global page revision"
            raise ValueError(msg)
        latest_by_word: dict[str, TypographyCorrection] = {}
        for word_id, revisions in corrections_by_word.items():
            expected_revisions = tuple(range(1, len(revisions) + 1))
            if tuple(item.revision for item in revisions) != expected_revisions:
                msg = (
                    "correction revision order must be contiguous from 1 for each word"
                )
                raise ValueError(msg)
            if any(
                current.supersedes_id != previous.correction_id
                for previous, current in pairwise(revisions)
            ):
                msg = "correction supersedes_id must reference the preceding word revision"
                raise ValueError(msg)
            if any(
                current.base_text_sha256 != previous.effective_text_sha256
                or current.base_word_revision != previous.effective_word_revision
                for previous, current in pairwise(revisions)
            ):
                msg = "successor word bases must equal predecessor word replacements"
                raise ValueError(msg)
            latest_by_word[word_id] = revisions[-1]
        artifact_hashes = {artifact.sha256 for artifact in self.replacement_artifacts}
        model_runs = _model_runs_by_id(
            self.model_runs,
            artifact_hashes,
            require_complete=self.page_geometry is not None,
        )
        transforms = _transforms_by_id(self.coordinate_transforms, artifact_hashes)
        if (self.page_geometry is None) != (self.geometry is None):
            msg = "returned page and word geometry must be present together"
            raise ValueError(msg)
        if self.page_geometry is not None and self.geometry is not None:
            _validate_page_geometry(
                self.page_geometry, transforms, model_runs, artifact_hashes
            )
            _validate_word_geometry(self.geometry, self.page_geometry, transforms)
            geometry_by_word = {item.word_id: item for item in self.geometry}
            if not set(latest_by_word).issubset(geometry_by_word):
                msg = "returned geometry must include every corrected word"
                raise ValueError(msg)
            final_correction = self.corrections[-1] if self.corrections else None
            if final_correction is not None and (
                self.page_geometry.page_sha256 != final_correction.effective_page_sha256
                or self.page_geometry.page_head_sha256
                != final_correction.effective_page_head_sha256
                or self.page_geometry.image_artifact_sha256
                != final_correction.effective_image_sha256
            ):
                msg = "returned page geometry must match the final correction page"
                raise ValueError(msg)
            for word_id, correction in latest_by_word.items():
                item = geometry_by_word[word_id]
                if (
                    final_correction is None
                ):  # pragma: no cover - latest_by_word is empty
                    raise AssertionError(
                        "corrected word geometry requires a correction"
                    )
                if (
                    item.word_revision != correction.effective_word_revision
                    or item.page_sha256 != final_correction.effective_page_sha256
                    or item.page_head_sha256
                    != final_correction.effective_page_head_sha256
                    or item.image_artifact_sha256
                    != final_correction.effective_image_sha256
                ):
                    msg = (
                        "returned geometry must match the latest correction provenance"
                    )
                    raise ValueError(msg)
        expected = _bundle_content_id(self.model_dump(mode="json"))
        if self.bundle_id is not None and self.bundle_id != expected:
            msg = "bundle_id does not match the canonical bundle payload"
            raise ValueError(msg)
        object.__setattr__(self, "bundle_id", expected)
        return self

    def validate_against(self, labeling_bundle: LabelingBundle) -> None:
        """Verify every correction is bound to one exact labeling bundle."""
        if self.labeling_bundle_id != labeling_bundle.bundle_id:
            msg = "correction bundle does not reference the supplied labeling bundle"
            raise ValueError(msg)
        if (
            self.page_geometry is not None
            and self.page_geometry.page_id != labeling_bundle.page_id
        ):
            msg = "returned page geometry must match the labeling bundle page"
            raise ValueError(msg)
        if (
            self.page_geometry is not None
            and not self.corrections
            and (
                self.page_geometry.page_sha256 != labeling_bundle.page_sha256
                or self.page_geometry.image_artifact_sha256
                != labeling_bundle.image_sha256
                or self.page_geometry.page_head_sha256
                != labeling_bundle.page_head_sha256
            )
        ):
            msg = "geometry-only return must match the labeling bundle provenance"
            raise ValueError(msg)
        words = {word.word_id: word for word in labeling_bundle.words}
        for index, correction in enumerate(self.corrections):
            word = words.get(correction.word_id)
            if word is None:
                msg = "correction word_id is absent from labeling bundle"
                raise ValueError(msg)
            if index == 0 and (
                correction.base_page_sha256 != labeling_bundle.page_sha256
                or correction.base_image_sha256 != labeling_bundle.image_sha256
                or correction.page_head_sha256 != labeling_bundle.page_head_sha256
            ):
                msg = "first correction page bases do not match the labeling bundle"
                raise ValueError(msg)
            if correction.revision == 1 and (
                correction.base_text_sha256 != word.text_sha256
                or correction.base_word_revision != word.word_revision
                or correction.taxonomy_version != labeling_bundle.taxonomy.version
                or correction.taxonomy_hash != labeling_bundle.taxonomy.taxonomy_hash
                or correction.grapheme_map_version != word.grapheme_map_version
            ):
                msg = "initial word correction does not match the labeling bundle word"
                raise ValueError(msg)
            if correction.replacement is not None:
                correction.replacement.validate_taxonomy(labeling_bundle.taxonomy)
                if correction.decision is CorrectionDecision.REVIEWED_REGULAR and any(
                    correction.replacement.label_states.get(label.value)
                    is not LabelState.NEGATIVE
                    for label in labeling_bundle.taxonomy.labels
                    if label.required_for_completion
                ):
                    msg = "reviewed_regular correction requires all required labels negative"
                    raise ValueError(msg)
                declared_hashes = {
                    artifact.sha256 for artifact in self.replacement_artifacts
                }
                if not {
                    correction.replacement_page_sha256,
                    correction.replacement_image_sha256,
                    correction.replacement_page_head_sha256,
                }.issubset(declared_hashes):
                    msg = "approved correction replacement hashes require declared artifacts"
                    raise ValueError(msg)
                if (
                    correction.replacement.page_content_sha256
                    != correction.replacement_page_sha256
                    or correction.replacement.image_artifact_sha256
                    != correction.replacement_image_sha256
                    or correction.replacement.word_revision
                    != correction.replacement_word_revision
                ):
                    msg = "replacement does not match correction or labeling bundle provenance"
                    raise ValueError(msg)
        if self.geometry is not None:
            for item in self.geometry:
                word = words.get(item.word_id)
                if word is None:
                    msg = "returned geometry word_id is absent from labeling bundle"
                    raise ValueError(msg)
                if (
                    not any(
                        correction.word_id == item.word_id
                        for correction in self.corrections
                    )
                    and item.word_revision != word.word_revision
                ):
                    msg = "uncorrected returned geometry must retain the inbound word revision"
                    raise ValueError(msg)

    def rebuild(self, **updates: object) -> Self:
        """Apply updates through validation and derive a new content ID.

        Do not use Pydantic's ``model_copy`` for content-addressed bundles:
        it intentionally skips validation and can preserve a stale ``bundle_id``.
        """
        data = self.model_dump(mode="json")
        data.update(updates)
        data["bundle_id"] = None
        return type(self).model_validate(data)
