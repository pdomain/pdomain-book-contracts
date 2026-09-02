from __future__ import annotations

from typing import Protocol


class BlobStoreProtocol(Protocol):
    """Minimum interface Page needs from a blob store.

    Defined here (in pdomain-book-tools) so Page can type-hint get_image() and
    get_thumbnail() without importing pdomain-ops — which would create a circular
    dependency (pdomain-ops depends on pdomain-book-tools).

    The concrete BlobStore in pdomain-ops implements this protocol.
    """

    def read(self, hash: str) -> bytes:
        """Return raw bytes for a blob identified by its SHA256 hash."""
        ...
