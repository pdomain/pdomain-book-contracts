from __future__ import annotations

import pytest

from pdomain_book_contracts.ocr.provenance import (
    UNKNOWN_METADATA_VALUE,
    OCRModelProvenance,
    OCRProvenance,
)


def test_model_to_dict_omits_unset_and_empty_optionals() -> None:
    assert OCRModelProvenance(name="m").to_dict() == {"name": "m"}
    assert OCRModelProvenance(name="m", version="", weights_id="").to_dict() == {
        "name": "m"
    }


def test_model_round_trip_keeps_version_and_weights() -> None:
    model = OCRModelProvenance(name="det", version="2", weights_id="abc")
    assert OCRModelProvenance.from_dict(model.to_dict()) == model


def test_model_from_dict_defaults_missing_name_to_unknown() -> None:
    model = OCRModelProvenance.from_dict({"version": 3})
    assert model == OCRModelProvenance(name=UNKNOWN_METADATA_VALUE, version="3")


def test_provenance_defaults_are_unknown_and_empty() -> None:
    prov = OCRProvenance()
    assert prov.engine == UNKNOWN_METADATA_VALUE
    assert prov.models == ()


def test_provenance_round_trip_keeps_empty_string_distinct_from_none() -> None:
    prov = OCRProvenance(
        engine="doctr",
        engine_version="",
        models=(OCRModelProvenance(name="det", version="1"),),
        config_fingerprint="",
    )
    restored = OCRProvenance.from_dict(prov.to_dict())
    assert restored == prov
    assert restored.engine_version == ""
    assert restored.config_fingerprint == ""


def test_provenance_to_dict_omits_none_optionals() -> None:
    assert OCRProvenance(engine="e").to_dict() == {"engine": "e", "models": []}


def test_provenance_from_dict_empty_uses_defaults() -> None:
    prov = OCRProvenance.from_dict({})
    assert prov == OCRProvenance()
    assert prov.engine_version is None
    assert prov.config_fingerprint is None


def test_provenance_from_dict_accepts_legacy_model_shapes() -> None:
    prov = OCRProvenance.from_dict(
        {
            "engine": "e",
            "models": [
                "plain-name",
                {"model": "legacy-key", "version": 1, "weights_id": "w"},
                {"name": "full"},
                "",
                {"version": "no-name"},
                {"name": ""},
                42,
            ],
        }
    )
    assert prov.models == (
        OCRModelProvenance(name="plain-name"),
        OCRModelProvenance(name="legacy-key", version="1", weights_id="w"),
        OCRModelProvenance(name="full"),
    )


def test_provenance_from_dict_ignores_non_list_models() -> None:
    assert OCRProvenance.from_dict({"models": "oops"}).models == ()


def test_provenance_from_dict_stringifies_scalar_fields() -> None:
    prov = OCRProvenance.from_dict(
        {"engine": "e", "engine_version": 5, "config_fingerprint": 7}
    )
    assert prov.engine_version == "5"
    assert prov.config_fingerprint == "7"


def test_coerce_none_gives_none() -> None:
    assert OCRProvenance.coerce(None) is None


def test_coerce_instance_is_returned_unchanged() -> None:
    prov = OCRProvenance(engine="e")
    assert OCRProvenance.coerce(prov) is prov


def test_coerce_dict_builds_provenance() -> None:
    assert OCRProvenance.coerce({"engine": "e", "models": ["m"]}) == OCRProvenance(
        engine="e", models=(OCRModelProvenance(name="m"),)
    )


def test_coerce_rejects_other_types() -> None:
    with pytest.raises(TypeError, match="Expected OCRProvenance or dict"):
        OCRProvenance.coerce("engine")
