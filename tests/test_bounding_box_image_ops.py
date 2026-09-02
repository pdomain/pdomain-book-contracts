"""Tests for the ``BoundingBox`` image-ops provider registry.

``pdomain_book_contracts`` never imports an imaging backend itself (see
``ImageOpsProvider`` in ``bounding_box.py``). These tests cover both ends of
that boundary: that a registered provider is dispatched to correctly, and
that the absence of one raises a clear, named error rather than an
``ImportError`` or ``AttributeError`` — proven from a real subprocess with
``pdomain_book_tools`` hidden from imports, not merely asserted.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import pytest

from pdomain_book_contracts.geometry.bounding_box import (
    BoundingBox,
    ImageOpsUnavailableError,
    register_image_ops,
)
from pdomain_book_contracts.geometry.point import Point

if TYPE_CHECKING:
    from collections.abc import Iterator

    from numpy import ndarray


@pytest.fixture(autouse=True)
def reset_image_ops_provider() -> Iterator[None]:
    """Isolate each test's provider registration from the others."""
    yield
    register_image_ops(None)


def _make_box() -> BoundingBox:
    return BoundingBox(Point(0.0, 0.0), Point(1.0, 1.0))


def _dummy_image() -> ndarray:
    """An opaque placeholder typed as ``ndarray`` for the provider boundary.

    This package has no runtime numpy dependency, so tests stand in an
    identity-trackable sentinel rather than a real array; nothing in the
    code paths under test actually reads pixel data.
    """
    return cast("ndarray", object())


@dataclass
class _FakeImageOps:
    """Minimal ``ImageOpsProvider`` that records how it was called."""

    refine_calls: list[tuple[BoundingBox, object, int, bool]] = field(
        default_factory=list
    )
    crop_top_calls: list[tuple[BoundingBox, object]] = field(default_factory=list)
    crop_bottom_calls: list[tuple[BoundingBox, object]] = field(default_factory=list)

    def refine(
        self,
        bbox: BoundingBox,
        image: object,
        padding_px: int = 0,
        expand_beyond_original: bool = False,
    ) -> BoundingBox:
        self.refine_calls.append((bbox, image, padding_px, expand_beyond_original))
        return bbox

    def crop_top(self, bbox: BoundingBox, image: object) -> BoundingBox:
        self.crop_top_calls.append((bbox, image))
        return bbox

    def crop_bottom(self, bbox: BoundingBox, image: object) -> BoundingBox:
        self.crop_bottom_calls.append((bbox, image))
        return bbox


def test_refine_dispatches_to_the_registered_provider() -> None:
    provider = _FakeImageOps()
    register_image_ops(provider)
    box = _make_box()
    sentinel_image = _dummy_image()

    result = box.refine(sentinel_image, padding_px=3, expand_beyond_original=True)

    assert result is box
    assert provider.refine_calls == [(box, sentinel_image, 3, True)]


def test_crop_top_and_crop_bottom_dispatch_to_the_registered_provider() -> None:
    provider = _FakeImageOps()
    register_image_ops(provider)
    box = _make_box()
    sentinel_image = _dummy_image()

    box.crop_top(sentinel_image)
    box.crop_bottom(sentinel_image)

    assert provider.crop_top_calls == [(box, sentinel_image)]
    assert provider.crop_bottom_calls == [(box, sentinel_image)]


@pytest.mark.parametrize("operation", ["refine", "crop_top", "crop_bottom"])
def test_each_operation_raises_the_named_error_when_nothing_is_registered(
    operation: str,
) -> None:
    register_image_ops(None)
    box = _make_box()

    with pytest.raises(ImageOpsUnavailableError) as excinfo:
        getattr(box, operation)(image=_dummy_image())

    message = str(excinfo.value)
    assert operation in message
    assert "pdomain_book_tools.geometry.image_ops" in message


def test_refine_raises_the_named_error_with_book_tools_hidden_from_imports() -> None:
    """Prove the boundary in a real subprocess, not merely assert it.

    With ``pdomain_book_tools`` hidden from imports entirely (a stand-in for
    "installed pdomain-book-contracts alone"), constructing a ``BoundingBox``
    and calling ``refine`` must raise ``ImageOpsUnavailableError`` — not
    ``ImportError`` and not ``AttributeError``.
    """
    code = textwrap.dedent(
        """
        import sys
        import importlib.abc


        class _Blocker(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path, target=None):
                if name.split(".")[0] == "pdomain_book_tools":
                    raise ModuleNotFoundError(f"No module named {name!r} (blocked)")
                return None


        sys.meta_path.insert(0, _Blocker())

        from pdomain_book_contracts.geometry.bounding_box import BoundingBox
        from pdomain_book_contracts.geometry.point import Point

        box = BoundingBox(Point(0.0, 0.0), Point(1.0, 1.0))
        try:
            box.refine(image=None)
        except Exception as err:
            print(f"{type(err).__name__}: {err}")
        else:
            print("NO-EXCEPTION-RAISED")
        """
    )
    result = subprocess.run(  # noqa: S603 - fixed argv, test-controlled code
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = result.stdout.strip()
    assert stdout.startswith("ImageOpsUnavailableError:"), stdout
    assert "pdomain_book_tools.geometry.image_ops" in stdout
