from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

UNKNOWN_METADATA_VALUE = "unknown"

# JSON-compatible dict type alias used throughout this module.
# Values are `object` (not `Any`) so callers must explicitly cast/narrow them;
# `Any` is reserved for genuinely opaque third-party API surfaces.
_JsonDict = dict[str, object]


@dataclass(frozen=True)
class OCRModelProvenance:
    """Provenance metadata for a single OCR model (name, version, weights)."""

    name: str
    version: str | None = None
    weights_id: str | None = None

    def to_dict(self) -> _JsonDict:
        """Serialise to a plain dict for JSON persistence."""
        result: _JsonDict = {"name": self.name}
        if self.version:
            result["version"] = self.version
        if self.weights_id:
            result["weights_id"] = self.weights_id
        return result

    @classmethod
    def from_dict(cls, data: _JsonDict) -> OCRModelProvenance:
        """Deserialise from the dict produced by :meth:`to_dict`."""
        return cls(
            name=str(data.get("name", UNKNOWN_METADATA_VALUE)),
            version=(str(data["version"]) if data.get("version") is not None else None),
            weights_id=(
                str(data["weights_id"]) if data.get("weights_id") is not None else None
            ),
        )


@dataclass(frozen=True)
class OCRProvenance:
    """Full provenance record for an OCR pass: engine, version, and model list."""

    engine: str = UNKNOWN_METADATA_VALUE
    engine_version: str | None = None
    # Stored as a tuple so the frozen=True immutability promise is real:
    # ``provenance.models.append(...)`` would have succeeded silently on a
    # list, defeating the dataclass's frozen contract. ``__post_init__``
    # coerces any incoming list/iterable to a tuple. (L-15)
    models: tuple[OCRModelProvenance, ...] = field(default_factory=tuple)
    config_fingerprint: str | None = None

    def __post_init__(self) -> None:
        # Tolerate callers (and legacy code) constructing with a list.
        # ``object.__setattr__`` is required because the dataclass is frozen.
        # The isinstance guard is intentional: the field type is ``tuple`` but
        # callers may pass a list and bypass static checks at runtime (e.g.
        # via deserialized JSON or legacy code). pyright: ignore is used below
        # because the guard is always-False from the type checker's perspective
        # yet genuinely needed at runtime.
        if not isinstance(self.models, tuple):  # pyright: ignore[reportUnnecessaryIsInstance]
            object.__setattr__(self, "models", tuple(self.models))

    def to_dict(self) -> _JsonDict:
        """Serialise to a plain dict for JSON persistence."""
        result: _JsonDict = {
            "engine": self.engine,
            "models": [model.to_dict() for model in self.models],
        }
        # L-17: serialize ``None`` and explicit ``""`` distinctly. The
        # truthy guard ``if self.engine_version`` previously omitted ``""``
        # from the dict, and ``from_dict``'s ``is not None`` check then
        # defaulted the missing key back to ``None`` — silently flipping
        # an explicit empty value to "unknown" on every round-trip.
        if self.engine_version is not None:
            result["engine_version"] = self.engine_version
        if self.config_fingerprint is not None:
            result["config_fingerprint"] = self.config_fingerprint
        return result

    @classmethod
    def from_dict(cls, data: _JsonDict) -> OCRProvenance:
        """Deserialise from the dict produced by :meth:`to_dict`."""
        raw_models = data.get("models", [])
        models: list[OCRModelProvenance] = []
        if isinstance(raw_models, list):
            for model in cast("list[object]", raw_models):
                if isinstance(model, str) and model:
                    models.append(OCRModelProvenance(name=model))
                elif isinstance(model, dict):
                    model_d = cast("_JsonDict", model)
                    name = model_d.get("name") or model_d.get("model")
                    if not isinstance(name, str) or not name:
                        continue
                    models.append(
                        OCRModelProvenance(
                            name=name,
                            version=(
                                str(model_d["version"])
                                if model_d.get("version") is not None
                                else None
                            ),
                            weights_id=(
                                str(model_d["weights_id"])
                                if model_d.get("weights_id") is not None
                                else None
                            ),
                        )
                    )

        return cls(
            engine=str(data.get("engine", UNKNOWN_METADATA_VALUE)),
            engine_version=(
                str(data["engine_version"])
                if data.get("engine_version") is not None
                else None
            ),
            models=tuple(models),
            config_fingerprint=(
                str(data["config_fingerprint"])
                if data.get("config_fingerprint") is not None
                else None
            ),
        )

    @classmethod
    def coerce(cls, value: object | None) -> OCRProvenance | None:
        """Coerce a raw value to :class:`OCRProvenance` or ``None``."""
        if value is None:
            return None
        if isinstance(value, OCRProvenance):
            # L-16: the class is frozen (L-15 made ``models`` a tuple), so
            # returning the input directly is safe and avoids a wasteful
            # ``from_dict(value.to_dict())`` round-trip.
            return value
        if not isinstance(value, dict):
            raise TypeError("Expected OCRProvenance or dict")
        return OCRProvenance.from_dict(cast("_JsonDict", value))
