"""
Pure-Python contracts shared across the pdomain-* OCR suite.

This package holds the value types, contracts, and pure algorithms that any
consumer can depend on without an imaging stack: geometry, typography,
matching, OCR value types, layout contracts, and the PGDP round readers.

``pdomain-book-tools`` depends on this package and re-exports its names, so
it keeps everything that needs cv2, numpy, torch, or doctr: the OCR engine,
image processing, geometry correction, and the Hugging Face helpers.

The dependency set is deliberately small: pydantic, pydantic-core, shapely,
and regex. Nothing here may import torch, doctr, torchvision, cv2, numpy,
pandas, matplotlib, or transformers; ``tests/test_torch_free_import.py``
enforces that boundary.

This package is currently an empty skeleton. Its subpackages carry
placeholder docstrings naming what they will own; the code that fills them
moves from ``pdomain-book-tools`` in a later task.
"""

from __future__ import annotations

__version__ = "0.1.0"
