"""
Pure-Python contracts shared across the pdomain-* OCR suite.

This package holds the value types, contracts, and pure algorithms that any
consumer can depend on without an imaging stack: geometry, text, typography,
matching, OCR value types, layout contracts, licensing, and the PGDP round
readers.

``pdomain-book-tools`` depends on this package and re-exports its names from
their old paths, so existing imports keep working. It keeps everything that
needs cv2, numpy, torch, or doctr: the OCR engine, image processing, geometry
correction, and the Hugging Face helpers.

The dependency set is deliberately small: pydantic, pydantic-core, shapely,
regex, and typing-extensions. Nothing here may import torch, doctr,
torchvision, cv2, pandas, matplotlib, or transformers, and
``tests/test_torch_free_import.py`` enforces that. Numpy is the one exception:
shapely imports it eagerly, so it loads through a permitted dependency rather
than through anything this package asks for directly.
"""

from __future__ import annotations

# Version is generated at build time by hatch-vcs into _version.py. In an
# editable or source-tree checkout where _version.py has not been generated
# yet, fall back to importlib.metadata, which works once installed.
try:
    from pdomain_book_contracts._version import __version__, version
except ImportError:  # pragma: no cover - fallback for unbuilt source trees
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version

        try:
            __version__ = _pkg_version("pdomain-book-contracts")
        except PackageNotFoundError:
            __version__ = "0.0.0+unknown"
    except ImportError:
        __version__ = "0.0.0+unknown"
    version = __version__

__all__ = ["__version__", "version"]
