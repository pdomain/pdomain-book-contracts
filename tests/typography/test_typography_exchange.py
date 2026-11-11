from __future__ import annotations

import hashlib
import json
from typing import TypeVar

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.typography.exchange import (
    ArtifactReference,
    CoordinateTransform,
    CorrectionBundle,
    Evidence,
    LabelingBundle,
    ModelRun,
    PageGeometry,
    ReplacementArtifact,
    SourceOrientation,
    WordGeometry,
)
from pdomain_book_contracts.typography.labels import ConfidenceTier, LabelSource
from pdomain_book_contracts.typography.review import (
    REVIEW_CONTRACT_VERSION,
    CorrectionDecision,
    LabelState,
    ReviewState,
    TypographyCorrection,
    TypographySpan,
    TypographyTaxonomy,
    TypographyTaxonomyLabel,
    WordTypography,
    make_word_id,
)
from pdomain_book_contracts.typography.spans import (
    GRAPHEME_SEGMENTATION_VERSION,
    CanonicalModel,
)

M = TypeVar("M", bound=CanonicalModel)


def h(n: int) -> str:
    return f"{n:02x}" * 32


PAGE, IMAGE, HEAD = h(1), h(2), h(3)
SRC, ORI, OCR, REG = h(4), h(5), h(6), h(7)
MODEL, CONFIG, PREP = h(8), h(9), h(10)
NEW_PAGE, NEW_IMAGE, NEW_HEAD = h(11), h(12), h(13)
CFG_HASH = h(14)
WORD_TEXT = "word"
WORD_ID = make_word_id(project_id="p", page_id="pg", reading_order=0, text=WORD_TEXT)
TAXONOMY = TypographyTaxonomy(
    version="t1",
    labels=(
        TypographyTaxonomyLabel(
            value="italic",
            display_name="Italic",
            required_for_completion=True,
            trainable=True,
        ),
    ),
)


def replace(model: M, **updates: object) -> M:
    """Revalidate a model with some JSON-level fields replaced."""
    return type(model).model_validate({**model.model_dump(mode="json"), **updates})


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def artifact(name: str, digest: str) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=name, relative_path=f"artifacts/{name}.bin", sha256=digest
    )


def word(
    *,
    page: str = PAGE,
    image: str = IMAGE,
    revision: int = 0,
    state: LabelState = LabelState.NEGATIVE,
    review_state: ReviewState = ReviewState.REVIEWED,
    evidence_id: str = "ev",
) -> WordTypography:
    spans = ()
    if state is LabelState.POSITIVE:
        spans = (
            TypographySpan(
                span_id="s",
                label="italic",
                start=0,
                end=4,
                label_source=LabelSource.HUMAN,
                confidence_tier=ConfidenceTier.GOLD,
                alignment_evidence_id=evidence_id,
            ),
        )
    return WordTypography(
        word_id=WORD_ID,
        text=WORD_TEXT,
        text_sha256=sha(WORD_TEXT),
        page_content_sha256=page,
        image_artifact_sha256=image,
        grapheme_map_version=GRAPHEME_SEGMENTATION_VERSION,
        taxonomy_version=TAXONOMY.version,
        taxonomy_hash=TAXONOMY.taxonomy_hash,
        label_states={"italic": state},
        spans=spans,
        source_evidence_ids=(evidence_id,),
        word_revision=revision,
        review_state=review_state,
    )


def transforms(
    *, image: str = IMAGE, orientation_affine: tuple[float, ...] | None = None
) -> tuple[CoordinateTransform, CoordinateTransform]:
    orient = CoordinateTransform.model_validate(
        {
            "transform_id": "t-orient",
            "stage": "orientation",
            "source_space": "source",
            "target_space": "oriented",
            "source_coordinate_space_id": "src-space",
            "target_coordinate_space_id": "ori-space",
            "source_orientation": "upright",
            "source_artifact_sha256": SRC,
            "target_artifact_sha256": ORI,
            "crop_recipe": "none",
            "crop_recipe_version": "1",
            "padding_px": 0,
            "resampling": "none",
            "preprocessing_sha256": PREP,
            "transform_version": "1",
            "affine": orientation_affine or (1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            "source_width": 100,
            "source_height": 200,
            "target_width": 100,
            "target_height": 200,
        }
    )
    crop = replace(
        orient,
        transform_id="t-crop",
        stage="crop",
        source_space="oriented",
        target_space="image_pixels",
        source_coordinate_space_id="ori-space",
        target_coordinate_space_id="img-space",
        source_artifact_sha256=ORI,
        target_artifact_sha256=image,
        crop_recipe="box",
        affine=(1.0, 0.0, -10.0, 0.0, 1.0, -20.0),
        target_width=80,
        target_height=150,
        source_width=100,
        source_height=200,
    )
    return orient, crop


def model_runs(*, image: str = IMAGE) -> tuple[ModelRun, ModelRun]:
    ocr = ModelRun.model_validate(
        {
            "run_id": "ocr-run",
            "model_name": "ocr",
            "model_version": "1",
            "purpose": "ocr",
            "input_artifact_sha256": image,
            "output_artifact_sha256": OCR,
            "model_artifact_sha256": MODEL,
            "config_sha256": CONFIG,
            "preprocessing_sha256": PREP,
        }
    )
    region = replace(
        ocr,
        run_id="region-run",
        model_name="region",
        purpose="page_region",
        output_artifact_sha256=REG,
    )
    return ocr, region


def page_geometry(
    *, page: str = PAGE, image: str = IMAGE, head: str = HEAD
) -> PageGeometry:
    return PageGeometry(
        page_id="pg",
        page_sha256=page,
        source_image_artifact_sha256=SRC,
        source_image_width=100,
        source_image_height=200,
        image_artifact_sha256=image,
        page_head_sha256=head,
        ocr_artifact_sha256=OCR,
        page_region_artifact_sha256=REG,
        coordinate_space="image_pixels",
        coordinate_space_id="img-space",
        source_orientation=SourceOrientation.UPRIGHT,
        transform_ids=("t-orient", "t-crop"),
        ocr_model_run_id="ocr-run",
        page_region_model_run_id="region-run",
        image_width=80,
        image_height=150,
    )


def word_geometry(
    *, page: str = PAGE, image: str = IMAGE, head: str = HEAD, revision: int = 0
) -> WordGeometry:
    return WordGeometry(
        word_id=WORD_ID,
        word_revision=revision,
        page_sha256=page,
        page_head_sha256=head,
        image_artifact_sha256=image,
        x0=1.0,
        y0=2.0,
        x1=30.0,
        y1=40.0,
        coordinate_space_id="img-space",
        transform_id="t-crop",
        source_orientation=SourceOrientation.UPRIGHT,
    )


def labeling(*, geometry: bool = False, **updates: object) -> LabelingBundle:
    named = {
        "page": PAGE,
        "image": IMAGE,
        "head": HEAD,
        "src": SRC,
        "ori": ORI,
        "ocr": OCR,
        "reg": REG,
        "model": MODEL,
        "config": CONFIG,
        "prep": PREP,
    }
    payload: dict[str, object] = {
        "schema_version": REVIEW_CONTRACT_VERSION,
        "configuration_hash": CFG_HASH,
        "taxonomy": TAXONOMY,
        "page_id": "pg",
        "page_sha256": PAGE,
        "image_sha256": IMAGE,
        "text_sha256": sha(WORD_TEXT),
        "page_head_sha256": HEAD,
        "artifacts": tuple(artifact(n, d) for n, d in named.items()),
        "words": (word(),),
        "evidence": (
            Evidence(
                evidence_id="ev",
                artifact_id="page",
                artifact_sha256=PAGE,
                byte_start=0,
                byte_end=4,
            ),
        ),
    }
    if geometry:
        payload |= {
            "page_geometry": page_geometry(),
            "geometry": (word_geometry(),),
            "model_runs": model_runs(),
            "coordinate_transforms": transforms(),
        }
    return LabelingBundle.model_validate(payload | updates)


def replacement_artifacts(*digests: str) -> tuple[ReplacementArtifact, ...]:
    return tuple(
        ReplacementArtifact(
            artifact_id=f"r{index}",
            relative_path=f"out/r{index}.bin",
            sha256=digest,
            byte_size=10,
            media_type="application/octet-stream",
        )
        for index, digest in enumerate(digests)
    )


def correction(
    *,
    correction_id: str = "c1",
    decision: CorrectionDecision = CorrectionDecision.APPROVED_EDIT,
    revision: int = 1,
    supersedes_id: str | None = None,
    base: tuple[str, str, str] = (PAGE, IMAGE, HEAD),
    base_revision: int = 0,
    result: tuple[str, str, str] = (NEW_PAGE, NEW_IMAGE, NEW_HEAD),
) -> TypographyCorrection:
    accepting = decision in {
        CorrectionDecision.APPROVED_EDIT,
        CorrectionDecision.ACCEPT,
        CorrectionDecision.REVIEWED_REGULAR,
    }
    replacement = (
        word(page=result[0], image=result[1], revision=base_revision + 1)
        if accepting
        else None
    )
    return TypographyCorrection(
        correction_id=correction_id,
        word_id=WORD_ID,
        revision=revision,
        supersedes_id=supersedes_id,
        base_page_sha256=base[0],
        base_image_sha256=base[1],
        base_text_sha256=sha(WORD_TEXT),
        base_word_revision=base_revision,
        replacement_text_sha256=sha(WORD_TEXT) if accepting else None,
        replacement_page_sha256=result[0] if accepting else None,
        replacement_image_sha256=result[1] if accepting else None,
        replacement_page_head_sha256=result[2] if accepting else None,
        replacement_word_revision=base_revision + 1 if accepting else None,
        taxonomy_version=TAXONOMY.version,
        taxonomy_hash=TAXONOMY.taxonomy_hash,
        grapheme_map_version=GRAPHEME_SEGMENTATION_VERSION,
        page_head_sha256=base[2],
        labeler_id="lab",
        decision=decision,
        replacement=replacement,
    )


def returns(
    labeling_bundle: LabelingBundle,
    *corrections: TypographyCorrection,
    **updates: object,
) -> CorrectionBundle:
    payload: dict[str, object] = {
        "schema_version": REVIEW_CONTRACT_VERSION,
        "configuration_hash": CFG_HASH,
        "labeling_bundle_id": labeling_bundle.bundle_id,
        "corrections": corrections,
        "replacement_artifacts": replacement_artifacts(NEW_PAGE, NEW_IMAGE, NEW_HEAD),
    }
    return CorrectionBundle.model_validate(payload | updates)


def geometry_return(labeling_bundle: LabelingBundle) -> CorrectionBundle:
    digests = (NEW_PAGE, NEW_IMAGE, NEW_HEAD, SRC, ORI, OCR, REG, MODEL, CONFIG, PREP)
    return returns(
        labeling_bundle,
        correction(),
        replacement_artifacts=replacement_artifacts(*digests),
        page_geometry=page_geometry(page=NEW_PAGE, image=NEW_IMAGE, head=NEW_HEAD),
        geometry=(
            word_geometry(page=NEW_PAGE, image=NEW_IMAGE, head=NEW_HEAD, revision=1),
        ),
        model_runs=model_runs(image=NEW_IMAGE),
        coordinate_transforms=transforms(image=NEW_IMAGE),
    )


@pytest.mark.parametrize(
    "path", ["a/b.json", "a", "deep/er/file.txt", "name with space.bin"]
)
def test_artifact_reference_accepts_safe_relative_paths(path: str) -> None:
    ref = ArtifactReference(artifact_id="x", relative_path=path, sha256=h(1))
    assert ref.relative_path == path


@pytest.mark.parametrize(
    "path", ["", "/etc/passwd", "../x", "a/../b", "a\\b", "C:/x", "c:rel", "a/.."]
)
def test_artifact_reference_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValidationError, match="safe relative POSIX path"):
        ArtifactReference(artifact_id="x", relative_path=path, sha256=h(1))


def test_artifact_reference_verifies_bytes_against_the_declared_hash() -> None:
    ref = ArtifactReference(
        artifact_id="x",
        relative_path="a.bin",
        sha256=sha("payload").upper(),
        media_type="text/plain",
    )
    assert ref.sha256 == sha("payload")
    assert ref.verify_bytes(b"payload")
    assert not ref.verify_bytes(b"payload2")
    assert ArtifactReference.from_json_bytes(ref.to_json_bytes()) == ref


def test_artifact_reference_rejects_blank_ids_and_bad_hashes() -> None:
    with pytest.raises(ValidationError, match="artifact_id must not be empty"):
        ArtifactReference(artifact_id=" ", relative_path="a", sha256=h(1))
    with pytest.raises(ValidationError, match="64-character"):
        ArtifactReference(artifact_id="x", relative_path="a", sha256="abc")


def test_replacement_artifact_validates_path_hash_size_and_strings() -> None:
    good = ReplacementArtifact(
        artifact_id="r", relative_path="o/a", sha256=h(1), byte_size=0, media_type="x/y"
    )
    assert ReplacementArtifact.from_json_bytes(good.to_json_bytes()) == good
    with pytest.raises(ValidationError, match="safe relative POSIX path"):
        replace(good, relative_path="../o")
    with pytest.raises(ValidationError, match="must not be empty"):
        replace(good, media_type=" ")
    with pytest.raises(ValidationError, match="must not be empty"):
        replace(good, artifact_id="")
    with pytest.raises(ValidationError):
        replace(good, byte_size=-1)
    with pytest.raises(ValidationError, match="64-character"):
        replace(good, sha256="1")


def test_model_run_hashes_are_optional_but_validated_when_present() -> None:
    run = ModelRun(run_id="r", model_name="m", model_version="1")
    assert run.purpose is None
    assert replace(run, config_sha256=h(1).upper()).config_sha256 == h(1)
    with pytest.raises(ValidationError, match="64-character"):
        replace(run, config_sha256="bad")
    with pytest.raises(ValidationError, match="must not be empty"):
        replace(run, model_name=" ")
    assert ModelRun.from_json_bytes(run.to_json_bytes()) == run


def test_coordinate_transform_field_rejections() -> None:
    orient, _ = transforms()
    assert CoordinateTransform.from_json_bytes(orient.to_json_bytes()) == orient
    with pytest.raises(ValidationError, match="coordinate transform values"):
        replace(orient, transform_id=" ")
    with pytest.raises(ValidationError, match="transform recipe values"):
        replace(orient, crop_recipe="")
    with pytest.raises(ValidationError, match="64-character"):
        replace(orient, preprocessing_sha256="x")
    with pytest.raises(ValidationError):
        replace(orient, padding_px=-1)
    with pytest.raises(ValidationError):
        replace(orient, affine=[1.0, 0.0, 0.0, 0.0, 1.0])
    with pytest.raises(ValidationError):
        replace(orient, source_width=0)


def test_evidence_requires_a_nonempty_half_open_byte_range() -> None:
    ev = Evidence(
        evidence_id="e", artifact_id="a", artifact_sha256=h(1), byte_start=0, byte_end=1
    )
    assert Evidence.from_json_bytes(ev.to_json_bytes()) == ev
    with pytest.raises(ValidationError, match="nonempty half-open byte range"):
        replace(ev, byte_end=0)
    with pytest.raises(ValidationError, match="must not be empty"):
        replace(ev, evidence_id=" ")
    with pytest.raises(ValidationError, match="64-character"):
        replace(ev, artifact_sha256="1")


def test_word_geometry_requires_positive_extent_and_finite_strict_floats() -> None:
    geo = word_geometry()
    assert WordGeometry.from_json_bytes(geo.to_json_bytes()) == geo
    with pytest.raises(ValidationError, match="positive width and height"):
        replace(geo, x1=geo.x0)
    with pytest.raises(ValidationError, match="positive width and height"):
        replace(geo, y1=-5.0)
    with pytest.raises(ValidationError, match="word_id must not be empty"):
        replace(geo, word_id=" ")
    with pytest.raises(ValidationError, match="geometry identifiers"):
        replace(geo, transform_id=" ")
    with pytest.raises(ValidationError, match="geometry identifiers"):
        replace(geo, coordinate_space=" ")
    with pytest.raises(ValidationError):
        WordGeometry.model_validate_json(
            geo.to_json_bytes().replace(b'"x0":1.0', b'"x0":"1"')
        )
    with pytest.raises(ValidationError, match="64-character"):
        replace(geo, page_sha256="z")


def test_page_geometry_requires_unique_nonempty_transform_ids() -> None:
    geo = page_geometry()
    assert PageGeometry.from_json_bytes(geo.to_json_bytes()) == geo
    for ids in ([], ["a", "a"], ["a", " "]):
        with pytest.raises(ValidationError, match="nonempty and unique"):
            replace(geo, transform_ids=ids)
    with pytest.raises(ValidationError, match="identifiers must not be empty"):
        replace(geo, page_id=" ")
    with pytest.raises(ValidationError, match="64-character"):
        replace(geo, ocr_artifact_sha256="1")
    with pytest.raises(ValidationError):
        replace(geo, image_width=0)


def test_labeling_bundle_gets_a_content_id_and_round_trips() -> None:
    bundle = labeling()
    assert bundle.bundle_id is not None
    assert len(bundle.bundle_id) == 64
    restored = LabelingBundle.from_json_bytes(bundle.to_json_bytes())
    assert restored == bundle
    assert restored.bundle_id == bundle.bundle_id


def test_content_id_is_the_hash_of_the_canonical_payload_without_the_id() -> None:
    bundle = labeling()
    payload = bundle.model_dump(mode="json")
    del payload["bundle_id"]
    expected = hashlib.sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    assert bundle.bundle_id == expected


def test_labeling_bundle_content_id_changes_with_the_content() -> None:
    assert labeling().bundle_id != labeling(page_id="other").bundle_id


def test_labeling_bundle_rejects_a_stale_bundle_id() -> None:
    payload = labeling().model_dump(mode="json")
    payload["page_id"] = "other"
    with pytest.raises(ValidationError, match="bundle_id does not match"):
        LabelingBundle.model_validate(payload)


def test_rebuild_applies_updates_and_derives_a_fresh_id() -> None:
    bundle = labeling()
    rebuilt = bundle.rebuild(page_id="other")
    assert rebuilt.page_id == "other"
    assert rebuilt.bundle_id != bundle.bundle_id
    assert rebuilt.bundle_id == labeling(page_id="other").bundle_id
    assert bundle.rebuild().bundle_id == bundle.bundle_id


def test_labeling_bundle_rejects_other_schema_versions_and_bad_fields() -> None:
    with pytest.raises(ValidationError, match="review contract version"):
        labeling(schema_version="0.1.0")
    with pytest.raises(ValidationError, match="page_id must not be empty"):
        labeling(page_id=" ")
    with pytest.raises(ValidationError, match="64-character"):
        labeling(text_sha256="1")


def test_labeling_bundle_words_must_match_the_bundle_page_and_image() -> None:
    with pytest.raises(ValidationError, match="must match the containing bundle"):
        labeling(words=(word(page=h(40)),))
    with pytest.raises(ValidationError, match="must match the containing bundle"):
        labeling(words=(word(image=h(40)),))


def test_labeling_bundle_words_are_checked_against_its_taxonomy() -> None:
    other = TypographyTaxonomy(version="t2", labels=TAXONOMY.labels)
    with pytest.raises(ValidationError, match="does not match the supplied taxonomy"):
        labeling(taxonomy=other)


def test_labeling_bundle_artifact_ids_must_be_unique() -> None:
    dup = (artifact("a", h(1)), artifact("a", h(2)))
    with pytest.raises(ValidationError, match="artifact IDs must be unique"):
        labeling(artifacts=dup, evidence=(), words=())


def test_evidence_must_name_a_declared_artifact_with_the_same_hash() -> None:
    bad = Evidence(
        evidence_id="ev",
        artifact_id="page",
        artifact_sha256=h(40),
        byte_start=0,
        byte_end=1,
    )
    with pytest.raises(ValidationError, match="identify a declared artifact"):
        labeling(evidence=(bad,))
    missing = replace(bad, artifact_id="nope", artifact_sha256=PAGE)
    with pytest.raises(ValidationError, match="identify a declared artifact"):
        labeling(evidence=(missing,))


def test_word_evidence_ids_must_be_declared_by_the_bundle() -> None:
    with pytest.raises(ValidationError, match="source evidence IDs must be declared"):
        labeling(words=(word(evidence_id="ghost"),), evidence=())


def test_span_alignment_evidence_must_be_declared_by_the_bundle() -> None:
    positive = word(state=LabelState.POSITIVE)
    payload = positive.model_dump(mode="json")
    payload["source_evidence_ids"] = ["ev"]
    payload["spans"][0]["alignment_evidence_id"] = "ghost"
    with pytest.raises(
        ValidationError, match="alignment evidence IDs must be declared"
    ):
        labeling(words=(WordTypography.model_validate(payload),))
    assert labeling(words=(positive,)).words[0].whole_word_labels == ("italic",)


def test_bundle_word_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="word IDs must be unique"):
        labeling(words=(word(), word()))


def test_model_runs_must_reference_declared_artifacts() -> None:
    run = ModelRun(run_id="r", model_name="m", model_version="1", config_sha256=h(99))
    with pytest.raises(ValidationError, match="must reference declared artifacts"):
        labeling(model_runs=(run,))
    declared = replace(run, config_sha256=CONFIG)
    assert labeling(model_runs=(declared,)).model_runs == (declared,)
    with pytest.raises(ValidationError, match="model run IDs must be unique"):
        labeling(model_runs=(declared, declared))


def test_transforms_must_reference_declared_artifacts_and_unique_ids() -> None:
    orient, crop = transforms()
    with pytest.raises(ValidationError, match="must reference declared artifacts"):
        labeling(coordinate_transforms=(replace(orient, source_artifact_sha256=h(99)),))
    with pytest.raises(ValidationError, match="transform IDs must be unique"):
        labeling(coordinate_transforms=(orient, replace(crop, transform_id="t-orient")))


def test_geometry_round_trips_when_page_and_word_geometry_are_complete() -> None:
    bundle = labeling(geometry=True)
    assert bundle.page_geometry is not None
    restored = LabelingBundle.from_json_bytes(bundle.to_json_bytes())
    assert restored == bundle


def test_page_and_word_geometry_must_be_present_together() -> None:
    full = labeling(geometry=True)
    with pytest.raises(ValidationError, match="present together"):
        full.rebuild(geometry=None)
    with pytest.raises(ValidationError, match="present together"):
        full.rebuild(page_geometry=None)


def test_geometry_without_complete_model_runs_is_rejected() -> None:
    full = labeling(geometry=True)
    ocr, _ = model_runs()
    incomplete = replace(ocr, purpose=None).model_dump(mode="json")
    with pytest.raises(ValidationError, match="require purpose, model, config"):
        full.rebuild(model_runs=[incomplete])


@pytest.mark.parametrize(
    "updates",
    [
        {"page_id": "other"},
        {"page_sha256": h(40)},
        {"image_sha256": h(40)},
        {"page_head_sha256": h(40)},
    ],
)
def test_inbound_page_geometry_must_match_bundle_provenance(
    updates: dict[str, str],
) -> None:
    full = labeling(geometry=True)
    with pytest.raises(ValidationError):
        full.rebuild(**updates)


def test_geometry_must_reference_a_declared_word_at_its_revision() -> None:
    full = labeling(geometry=True)
    other = replace(
        word_geometry(),
        word_id=make_word_id(project_id="p", page_id="pg", reading_order=1, text="x"),
    )
    with pytest.raises(ValidationError, match="reference a declared word"):
        full.rebuild(geometry=[other.model_dump(mode="json")])
    stale = replace(word_geometry(), word_revision=5)
    with pytest.raises(ValidationError, match="must match its word"):
        full.rebuild(geometry=[stale.model_dump(mode="json")])


def test_geometry_word_boxes_must_stay_inside_the_image() -> None:
    full = labeling(geometry=True)
    outside = replace(word_geometry(), x1=81.0)
    with pytest.raises(ValidationError, match="within the returned image bounds"):
        full.rebuild(geometry=[outside.model_dump(mode="json")])
    negative = replace(word_geometry(), x0=-1.0)
    with pytest.raises(ValidationError, match="within the returned image bounds"):
        full.rebuild(geometry=[negative.model_dump(mode="json")])


def test_geometry_word_ids_must_be_unique_and_use_chain_transforms() -> None:
    full = labeling(geometry=True)
    geo = word_geometry().model_dump(mode="json")
    with pytest.raises(ValidationError, match="geometry word IDs must be unique"):
        full.rebuild(geometry=[geo, geo])
    with pytest.raises(ValidationError, match="declared page chain"):
        full.rebuild(geometry=[{**geo, "transform_id": "nope"}])
    with pytest.raises(ValidationError, match="match the returned page geometry"):
        full.rebuild(geometry=[{**geo, "coordinate_space_id": "elsewhere"}])


def test_page_geometry_must_name_declared_transforms_and_stages() -> None:
    full = labeling(geometry=True)
    geo = page_geometry().model_dump(mode="json")
    with pytest.raises(ValidationError, match="declared coordinate transforms"):
        full.rebuild(page_geometry={**geo, "transform_ids": ["t-orient", "ghost"]})
    with pytest.raises(ValidationError, match="orientation and crop transform stages"):
        full.rebuild(page_geometry={**geo, "transform_ids": ["t-crop", "t-orient"]})
    with pytest.raises(ValidationError, match="must reference declared artifacts"):
        full.rebuild(page_geometry={**geo, "ocr_artifact_sha256": h(99)})


def test_page_geometry_transforms_must_chain_contiguously() -> None:
    full = labeling(geometry=True)
    orient, crop = transforms()
    broken = replace(crop, source_artifact_sha256=SRC)
    with pytest.raises(ValidationError, match="contiguous artifact chain"):
        full.rebuild(
            coordinate_transforms=[
                orient.model_dump(mode="json"),
                broken.model_dump(mode="json"),
            ]
        )
    skewed = replace(crop, source_coordinate_space_id="other")
    with pytest.raises(ValidationError, match="contiguous artifact chain"):
        full.rebuild(
            coordinate_transforms=[
                orient.model_dump(mode="json"),
                skewed.model_dump(mode="json"),
            ]
        )


def test_page_geometry_transforms_must_declare_bounds_matching_the_image_chain() -> (
    None
):
    full = labeling(geometry=True)
    orient, crop = transforms()
    unbounded = replace(orient, source_width=None)
    with pytest.raises(ValidationError, match="declared source and target bounds"):
        full.rebuild(
            coordinate_transforms=[
                unbounded.model_dump(mode="json"),
                crop.model_dump(mode="json"),
            ]
        )
    wrong = replace(crop, target_width=79)
    with pytest.raises(ValidationError, match="transform bounds must match"):
        full.rebuild(
            coordinate_transforms=[
                orient.model_dump(mode="json"),
                wrong.model_dump(mode="json"),
            ]
        )


def test_identity_crop_rules() -> None:
    full = labeling(geometry=True)
    orient, crop = transforms()
    fake_identity = replace(crop, crop_recipe="identity")
    with pytest.raises(
        ValidationError, match="identity crop must use an identity affine"
    ):
        full.rebuild(
            coordinate_transforms=[
                orient.model_dump(mode="json"),
                fake_identity.model_dump(mode="json"),
            ]
        )
    identity_affine_resized = replace(crop, affine=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
    with pytest.raises(ValidationError, match="identity crop transform bounds"):
        full.rebuild(
            coordinate_transforms=[
                orient.model_dump(mode="json"),
                identity_affine_resized.model_dump(mode="json"),
            ]
        )


def test_orientation_affine_must_match_the_declared_source_orientation() -> None:
    full = labeling(geometry=True)
    orient, crop = transforms()
    wrong = replace(orient, affine=(0.0, 1.0, 0.0, -1.0, 0.0, 0.0))
    with pytest.raises(
        ValidationError, match="affine does not match source orientation"
    ):
        full.rebuild(
            coordinate_transforms=[
                wrong.model_dump(mode="json"),
                crop.model_dump(mode="json"),
            ]
        )


def test_rotated_sources_swap_the_oriented_bounds_and_use_the_rotation_affine() -> None:
    full = labeling(geometry=True)
    orient, crop = transforms()
    rotated_orient = replace(
        orient,
        source_orientation="rotate_90_clockwise",
        affine=(0.0, -1.0, 200.0, 1.0, 0.0, 0.0),
        target_width=200,
        target_height=100,
    )
    rotated_crop = replace(crop, source_width=200, source_height=100)
    geo = {
        **page_geometry().model_dump(mode="json"),
        "source_orientation": "rotate_90_clockwise",
    }
    word_geo = {
        **word_geometry().model_dump(mode="json"),
        "source_orientation": "rotate_90_clockwise",
    }
    rebuilt = full.rebuild(
        coordinate_transforms=[
            rotated_orient.model_dump(mode="json"),
            rotated_crop.model_dump(mode="json"),
        ],
        page_geometry=geo,
        geometry=[word_geo],
    )
    assert rebuilt.page_geometry is not None
    assert (
        rebuilt.page_geometry.source_orientation
        is SourceOrientation.ROTATE_90_CLOCKWISE
    )


def test_page_geometry_must_match_its_final_transform_and_model_runs() -> None:
    full = labeling(geometry=True)
    geo = page_geometry().model_dump(mode="json")
    with pytest.raises(ValidationError, match="match its final coordinate transform"):
        full.rebuild(
            page_geometry={**geo, "coordinate_space": "other"},
            geometry=[
                {**word_geometry().model_dump(mode="json"), "coordinate_space": "other"}
            ],
        )
    ocr, region = model_runs()
    swapped = replace(ocr, purpose="page_region")
    with pytest.raises(
        ValidationError, match="declared OCR and page-region model runs"
    ):
        full.rebuild(
            model_runs=[swapped.model_dump(mode="json"), region.model_dump(mode="json")]
        )
    wrong_output = replace(ocr, output_artifact_sha256=REG)
    with pytest.raises(ValidationError, match="bind model inputs, outputs"):
        full.rebuild(
            model_runs=[
                wrong_output.model_dump(mode="json"),
                region.model_dump(mode="json"),
            ]
        )


def test_correction_bundle_gets_a_content_id_and_round_trips() -> None:
    bundle = returns(labeling(), correction())
    assert bundle.bundle_id is not None
    restored = CorrectionBundle.from_json_bytes(bundle.to_json_bytes())
    assert restored == bundle
    assert bundle.rebuild(configuration_hash=h(50)).bundle_id != bundle.bundle_id


def test_correction_bundle_rejects_a_stale_id_and_bad_header_fields() -> None:
    bundle = returns(labeling(), correction())
    payload = bundle.model_dump(mode="json")
    payload["configuration_hash"] = h(50)
    with pytest.raises(ValidationError, match="bundle_id does not match"):
        CorrectionBundle.model_validate(payload)
    with pytest.raises(ValidationError, match="review contract version"):
        bundle.rebuild(schema_version="0.0.1")
    with pytest.raises(ValidationError, match="content ID"):
        bundle.rebuild(labeling_bundle_id="abc")
    with pytest.raises(ValidationError, match="64-character"):
        bundle.rebuild(configuration_hash="abc")


def test_labeling_bundle_id_is_lowercased() -> None:
    labeling_bundle = labeling()
    assert labeling_bundle.bundle_id is not None
    bundle = returns(
        labeling_bundle,
        correction(),
        labeling_bundle_id=labeling_bundle.bundle_id.upper(),
    )
    assert bundle.labeling_bundle_id == labeling_bundle.bundle_id


def test_correction_and_replacement_artifact_ids_must_be_unique() -> None:
    base = labeling()
    with pytest.raises(ValidationError, match="correction IDs must be unique"):
        returns(base, correction(), correction())
    dup = replacement_artifacts(NEW_PAGE, NEW_IMAGE, NEW_HEAD)
    with pytest.raises(
        ValidationError, match="replacement artifact IDs must be unique"
    ):
        returns(
            base,
            correction(),
            replacement_artifacts=(
                dup[0],
                replace(dup[1], artifact_id=dup[0].artifact_id),
            ),
        )


def test_successive_corrections_chain_page_bases_and_word_revisions() -> None:
    base = labeling()
    first = correction()
    second = correction(
        correction_id="c2",
        revision=2,
        supersedes_id="c1",
        base=(NEW_PAGE, NEW_IMAGE, NEW_HEAD),
        base_revision=1,
        result=(h(20), h(21), h(22)),
    )
    bundle = returns(
        base,
        first,
        second,
        replacement_artifacts=replacement_artifacts(
            NEW_PAGE, NEW_IMAGE, NEW_HEAD, h(20), h(21), h(22)
        ),
    )
    assert [c.revision for c in bundle.corrections] == [1, 2]
    bundle.validate_against(base)


def test_second_correction_page_base_must_follow_the_previous_result() -> None:
    first = correction()
    second = correction(
        correction_id="c2",
        revision=2,
        supersedes_id="c1",
        base=(PAGE, NEW_IMAGE, NEW_HEAD),
        base_revision=1,
        result=(h(20), h(21), h(22)),
    )
    with pytest.raises(
        ValidationError, match="follow the preceding global page revision"
    ):
        returns(labeling(), first, second)


def test_word_revisions_must_start_at_one_and_supersede_their_predecessor() -> None:
    base = labeling()
    skipped = correction(revision=2, supersedes_id="c0")
    with pytest.raises(ValidationError, match="contiguous from 1"):
        returns(base, skipped)
    first = correction()
    wrong_parent = correction(
        correction_id="c2",
        revision=2,
        supersedes_id="other",
        base=(NEW_PAGE, NEW_IMAGE, NEW_HEAD),
        base_revision=1,
        result=(h(20), h(21), h(22)),
    )
    with pytest.raises(ValidationError, match="supersedes_id must reference"):
        returns(base, first, wrong_parent)


def test_successor_word_base_must_equal_the_predecessor_replacement() -> None:
    first = correction()
    wrong_base = correction(
        correction_id="c2",
        revision=2,
        supersedes_id="c1",
        base=(NEW_PAGE, NEW_IMAGE, NEW_HEAD),
        base_revision=0,
        result=(h(20), h(21), h(22)),
    )
    with pytest.raises(ValidationError, match="successor word bases"):
        returns(labeling(), first, wrong_base)


def test_validate_against_accepts_a_matching_labeling_bundle() -> None:
    base = labeling()
    returns(base, correction()).validate_against(base)
    returns(base).validate_against(base)


def test_validate_against_rejects_a_different_labeling_bundle() -> None:
    base = labeling()
    other = labeling(page_id="other")
    with pytest.raises(ValueError, match="does not reference the supplied"):
        returns(base, correction()).validate_against(other)


def test_validate_against_rejects_unknown_words() -> None:
    base = labeling(words=())
    with pytest.raises(ValueError, match="absent from labeling bundle"):
        returns(base, correction()).validate_against(base)


def test_validate_against_checks_the_first_correction_page_bases() -> None:
    base = labeling()
    off = correction(base=(h(60), IMAGE, HEAD))
    with pytest.raises(ValueError, match="first correction page bases"):
        returns(base, off).validate_against(base)
    off_head = correction(base=(PAGE, IMAGE, h(60)))
    with pytest.raises(ValueError, match="first correction page bases"):
        returns(base, off_head).validate_against(base)


def test_validate_against_checks_the_initial_word_base() -> None:
    base = labeling()
    stale = correction(base_revision=3)
    with pytest.raises(ValueError, match="initial word correction does not match"):
        returns(base, stale).validate_against(base)


def test_validate_against_requires_declared_replacement_artifacts() -> None:
    base = labeling()
    bundle = returns(
        base, correction(), replacement_artifacts=replacement_artifacts(NEW_PAGE)
    )
    with pytest.raises(ValueError, match="require declared artifacts"):
        bundle.validate_against(base)


def test_validate_against_rejects_replacements_that_break_the_taxonomy() -> None:
    base = labeling()
    reviewed_regular = correction(decision=CorrectionDecision.REVIEWED_REGULAR)
    returns(base, reviewed_regular).validate_against(base)
    positive = word(
        page=NEW_PAGE, image=NEW_IMAGE, revision=1, state=LabelState.POSITIVE
    )
    bad = replace(
        correction(decision=CorrectionDecision.REVIEWED_REGULAR),
        replacement=positive.model_dump(mode="json"),
    )
    with pytest.raises(ValueError, match="requires all required labels negative"):
        returns(base, bad).validate_against(base)


def test_validate_against_checks_correction_taxonomy_identity() -> None:
    other = TypographyTaxonomy(version="t2", labels=TAXONOMY.labels)
    moved_word = replace(
        word(), taxonomy_version="t2", taxonomy_hash=other.taxonomy_hash
    )
    base = labeling(taxonomy=other, words=(moved_word,))
    with pytest.raises(ValueError, match="initial word correction does not match"):
        returns(base, correction()).validate_against(base)


def test_validate_against_rejects_a_replacement_with_a_different_word_revision() -> (
    None
):
    base = labeling()
    skewed = replace(
        correction(),
        replacement=word(page=NEW_PAGE, image=NEW_IMAGE, revision=7).model_dump(
            mode="json"
        ),
    )
    with pytest.raises(ValueError, match="replacement does not match correction"):
        returns(base, skewed).validate_against(base)


def test_rejecting_decisions_validate_without_replacement_artifacts() -> None:
    base = labeling()
    deferred = correction(decision=CorrectionDecision.DEFER)
    bundle = returns(base, deferred, replacement_artifacts=())
    bundle.validate_against(base)
    assert bundle.corrections[0].effective_page_sha256 == PAGE


def test_geometry_return_round_trips_and_validates_against_the_labeling_bundle() -> (
    None
):
    base = labeling(geometry=True)
    bundle = geometry_return(base)
    bundle.validate_against(base)
    assert CorrectionBundle.from_json_bytes(bundle.to_json_bytes()) == bundle


def test_returned_geometry_must_be_complete_pairs() -> None:
    bundle = geometry_return(labeling(geometry=True))
    with pytest.raises(ValidationError, match="present together"):
        bundle.rebuild(geometry=None)
    with pytest.raises(ValidationError, match="present together"):
        bundle.rebuild(page_geometry=None)


def test_returned_geometry_must_cover_every_corrected_word() -> None:
    bundle = geometry_return(labeling(geometry=True))
    with pytest.raises(ValidationError, match="include every corrected word"):
        bundle.rebuild(geometry=[])


def test_returned_page_geometry_must_match_the_final_correction_page() -> None:
    bundle = geometry_return(labeling(geometry=True))
    stale = page_geometry(page=h(70), image=NEW_IMAGE, head=NEW_HEAD)
    moved_word = word_geometry(page=h(70), image=NEW_IMAGE, head=NEW_HEAD, revision=1)
    declared = [a.model_dump(mode="json") for a in bundle.replacement_artifacts]
    declared += [a.model_dump(mode="json") for a in replacement_artifacts(h(70))]
    declared[-1]["artifact_id"] = "extra"
    with pytest.raises(ValidationError, match="must match the final correction page"):
        bundle.rebuild(
            page_geometry=stale.model_dump(mode="json"),
            geometry=[moved_word.model_dump(mode="json")],
            replacement_artifacts=declared,
        )


def test_returned_word_geometry_must_match_the_latest_correction() -> None:
    bundle = geometry_return(labeling(geometry=True))
    stale = word_geometry(page=NEW_PAGE, image=NEW_IMAGE, head=NEW_HEAD, revision=0)
    with pytest.raises(ValidationError, match="latest correction provenance"):
        bundle.rebuild(geometry=[stale.model_dump(mode="json")])


def test_geometry_only_return_must_match_the_labeling_bundle_provenance() -> None:
    base = labeling(geometry=True)
    same = returns(
        base,
        replacement_artifacts=replacement_artifacts(
            PAGE, IMAGE, HEAD, SRC, ORI, OCR, REG, MODEL, CONFIG, PREP
        ),
        page_geometry=page_geometry(),
        geometry=(word_geometry(),),
        model_runs=model_runs(),
        coordinate_transforms=transforms(),
    )
    same.validate_against(base)
    moved = same.rebuild(
        page_geometry=page_geometry(page=NEW_PAGE).model_dump(mode="json"),
        geometry=[word_geometry(page=NEW_PAGE).model_dump(mode="json")],
        replacement_artifacts=[
            a.model_dump(mode="json")
            for a in replacement_artifacts(
                NEW_PAGE, IMAGE, HEAD, SRC, ORI, OCR, REG, MODEL, CONFIG, PREP
            )
        ],
    )
    with pytest.raises(ValueError, match="geometry-only return must match"):
        moved.validate_against(base)


def test_validate_against_checks_returned_geometry_word_membership_and_revision() -> (
    None
):
    base = labeling(geometry=True)
    unknown_base = labeling(words=())
    geometry_only = returns(
        base,
        replacement_artifacts=replacement_artifacts(
            PAGE, IMAGE, HEAD, SRC, ORI, OCR, REG, MODEL, CONFIG, PREP
        ),
        page_geometry=page_geometry(),
        geometry=(word_geometry(),),
        model_runs=model_runs(),
        coordinate_transforms=transforms(),
    )
    forged = geometry_only.rebuild(labeling_bundle_id=unknown_base.bundle_id)
    with pytest.raises(ValueError, match="geometry word_id is absent"):
        forged.validate_against(unknown_base)
    stale = geometry_only.rebuild(
        geometry=[word_geometry(revision=2).model_dump(mode="json")]
    )
    with pytest.raises(ValueError, match="retain the inbound word revision"):
        stale.validate_against(base)


def test_returned_page_geometry_must_name_the_labeling_bundle_page() -> None:
    other_geometry = replace(page_geometry(), page_id="other")
    base = labeling(geometry=True, page_id="other", page_geometry=other_geometry)
    bundle = returns(
        base,
        replacement_artifacts=replacement_artifacts(
            PAGE, IMAGE, HEAD, SRC, ORI, OCR, REG, MODEL, CONFIG, PREP
        ),
        page_geometry=page_geometry(),
        geometry=(word_geometry(),),
        model_runs=model_runs(),
        coordinate_transforms=transforms(),
    )
    with pytest.raises(ValueError, match="match the labeling bundle page"):
        bundle.validate_against(base)


@pytest.mark.parametrize("path", [".", "./a", "a/./b"])
def test_artifact_reference_rejects_dot_segments(path: str) -> None:
    with pytest.raises(ValidationError, match="safe relative POSIX path"):
        ArtifactReference(artifact_id="x", relative_path=path, sha256=h(1))
