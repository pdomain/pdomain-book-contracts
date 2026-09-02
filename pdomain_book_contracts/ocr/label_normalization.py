from __future__ import annotations

from typing import Final

ALLOWED_TEXT_STYLE_LABELS: Final[frozenset[str]] = frozenset(
    {
        "regular",
        "all caps",
        "small caps",
        "italics",
        "bold",
        "blackletter",
        "underline",
        "strikethrough",
        "monospace",
        "handwritten",
    }
)

ALLOWED_COMPONENTS: Final[frozenset[str]] = frozenset(
    {
        "superscript",
        "subscript",
        "footnote marker",
        # Drop-cap recognition tags. ``drop cap`` = this Word *is* the
        # decorative initial glyph, regardless of whether its text came
        # from the OCR engine or from the cursive-cap inference fallback
        # (see ``pdomain_book_tools.ocr.dropcap``). ``Block.text`` keys on
        # this tag to fuse the cap to the next body Word with the empty
        # string separator (so cap "S" + body "tudies" renders as
        # "Studies", not "S tudies").
        # ``drop cap unrecovered`` = the geometric trigger fired but the
        # letter couldn't be resolved; surfaced on the closest body word
        # so downstream tooling / labelers can flag the case for human
        # review. This tag does NOT trigger the empty-string join.
        "drop cap",
        "drop cap unrecovered",
    }
)

ALLOWED_TEXT_STYLE_LABEL_SCOPES: Final[frozenset[str]] = frozenset({"whole", "part"})


def _normalize_token(label: str) -> str:
    return " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())


def normalize_text_style_label(label: str) -> str:
    """Normalise a single text style label to a canonical allowed value."""
    normalized = _normalize_token(label)

    if normalized not in ALLOWED_TEXT_STYLE_LABELS:
        compact = normalized.replace(" ", "")

        for allowed_label in ALLOWED_TEXT_STYLE_LABELS:
            if compact == allowed_label.replace(" ", ""):
                normalized = allowed_label
                break

    if normalized not in ALLOWED_TEXT_STYLE_LABELS:
        allowed = ", ".join(sorted(ALLOWED_TEXT_STYLE_LABELS))
        raise ValueError(
            f"Invalid text style label '{label}'. Allowed labels: {allowed}"
        )
    return normalized


def normalize_text_style_labels(labels: list[str] | None) -> list[str]:
    """Normalise a list of style labels, deduplicating and stripping redundant 'regular'."""
    if not labels:
        return ["regular"]
    normalized = list(
        dict.fromkeys(normalize_text_style_label(label) for label in labels)
    )
    # Strip the redundant 'regular' sentinel when any concrete style label is
    # also present. This mirrors Word.update_style_attributes (word.py ~252-257)
    # so that all entry points (Word(__init__), to_dict/from_dict round-trips,
    # update_style_attributes) agree on the canonical representation.
    if "regular" in normalized and len(normalized) > 1:
        normalized = [label for label in normalized if label != "regular"]
    return normalized


def normalize_text_style_label_scope(scope: str | None) -> str:
    """Normalise a single text style scope value (``'whole'`` or ``'part'``)."""
    if scope is None:
        return "whole"

    normalized = _normalize_token(scope)

    if normalized not in ALLOWED_TEXT_STYLE_LABEL_SCOPES:
        allowed = ", ".join(sorted(ALLOWED_TEXT_STYLE_LABEL_SCOPES))
        raise ValueError(
            f"Invalid text style label scope '{scope}'. Allowed scopes: {allowed}"
        )
    return normalized


def normalize_text_style_label_scopes(
    labels: list[str], scopes: dict[str, str] | None
) -> dict[str, str]:
    """Build a normalised label→scope mapping, validating each scope against its label."""
    normalized_labels = [normalize_text_style_label(label) for label in labels]
    if not normalized_labels:
        normalized_labels = ["regular"]
    normalized_labels = list(dict.fromkeys(normalized_labels))
    # Mirror normalize_text_style_labels: strip the 'regular' sentinel when any
    # concrete style is present, so scopes stays in lockstep with labels.
    if "regular" in normalized_labels and len(normalized_labels) > 1:
        normalized_labels = [label for label in normalized_labels if label != "regular"]
    normalized_scopes = dict.fromkeys(normalized_labels, "whole")

    if not scopes:
        return normalized_scopes

    for label, scope in scopes.items():
        normalized_label = normalize_text_style_label(label)
        if normalized_label not in normalized_scopes:
            # Silently drop a 'regular' scope entry that was made redundant by
            # the M-29 strip (legacy payloads can carry both 'regular' and a
            # concrete style; the concrete one wins).
            if normalized_label == "regular":
                continue
            allowed_labels = ", ".join(sorted(normalized_scopes.keys()))
            raise ValueError(
                f"Unknown style label '{label}' in text_style_label_scopes. "
                + f"Must match text_style_labels: {allowed_labels}"
            )
        normalized_scopes[normalized_label] = normalize_text_style_label_scope(scope)

    return normalized_scopes


def normalize_word_component(component: str) -> str:
    """Normalise a single word component label to a canonical allowed value."""
    return _normalize_component(
        component,
        allowed_components=ALLOWED_COMPONENTS,
        label_type="word component",
    )


def normalize_word_components(components: list[str] | None) -> list[str]:
    """Normalise a list of word component labels, deduplicating order-preservingly."""
    if not components:
        return []
    normalized = [normalize_word_component(component) for component in components]
    return list(dict.fromkeys(normalized))


def normalize_character_component(component: str) -> str:
    """Normalise a single character component label to a canonical allowed value."""
    return _normalize_component(
        component,
        allowed_components=ALLOWED_COMPONENTS,
        label_type="character component",
    )


def _normalize_component(
    component: str,
    *,
    allowed_components: frozenset[str],
    label_type: str,
) -> str:
    normalized = _normalize_token(component)

    if normalized not in allowed_components:
        compact = normalized.replace(" ", "")

        for allowed_component in allowed_components:
            if compact == allowed_component.replace(" ", ""):
                normalized = allowed_component
                break

    if normalized not in allowed_components:
        allowed = ", ".join(sorted(allowed_components))
        raise ValueError(
            f"Invalid {label_type} '{component}'. Allowed components: {allowed}"
        )
    return normalized


def normalize_character_components(components: list[str] | None) -> list[str]:
    """Normalise a list of character component labels, deduplicating order-preservingly."""
    if not components:
        return []
    normalized = [normalize_character_component(component) for component in components]
    return list(dict.fromkeys(normalized))
