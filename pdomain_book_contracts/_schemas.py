"""
Shared pydantic-core schema constants.

Will own the ``NUMBER_SCHEMA`` constant, moved from
``pdomain_book_tools.schemas._helpers``, and used by ``geometry`` for its
pydantic-core ``__get_pydantic_core_schema__`` implementations. A single
shared constant does not need a package of its own, hence the underscore
prefix and module-root placement rather than a ``schemas/`` subpackage.

Empty pending the code move in a later task.
"""

from __future__ import annotations
