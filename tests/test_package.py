from __future__ import annotations

import pdomain_book_contracts
import pdomain_book_contracts._schemas
import pdomain_book_contracts.geometry
import pdomain_book_contracts.layout
import pdomain_book_contracts.licensing
import pdomain_book_contracts.matching
import pdomain_book_contracts.ocr
import pdomain_book_contracts.sources.pgdp
import pdomain_book_contracts.sources.pgdp.f2
import pdomain_book_contracts.text
import pdomain_book_contracts.typography


def test_version_is_exposed() -> None:
    assert pdomain_book_contracts.__version__
    assert isinstance(pdomain_book_contracts.__version__, str)


def test_every_subpackage_has_a_docstring() -> None:
    modules = (
        pdomain_book_contracts.geometry,
        pdomain_book_contracts.text,
        pdomain_book_contracts.typography,
        pdomain_book_contracts.matching,
        pdomain_book_contracts.ocr,
        pdomain_book_contracts.layout,
        pdomain_book_contracts.sources.pgdp,
        pdomain_book_contracts.sources.pgdp.f2,
        pdomain_book_contracts.licensing,
        pdomain_book_contracts._schemas,
    )
    for module in modules:
        assert module.__doc__, f"{module.__name__} is missing a docstring"
