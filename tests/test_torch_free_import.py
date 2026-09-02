"""Verify ``pdomain_book_contracts`` never pulls in an imaging or ML stack.

The package's declared dependencies are pydantic, pydantic-core, shapely, and
regex. This test runs in a subprocess, with a meta-path finder hiding the
forbidden heavy modules, so the import graph is measured from a clean
interpreter rather than from whatever happens to already be in ``sys.modules``
in the test-runner process.

Numpy is a declared exception, not an oversight. ``shapely`` imports numpy
eagerly at its own import time (verified empirically: ``import shapely`` alone
puts ``numpy`` in ``sys.modules``), and shapely is a permitted dependency of
this package. A meta-path finder cannot distinguish "numpy imported because
this package asked for it" from "numpy imported because shapely, which this
package is allowed to use, asked for it" — ``find_spec`` sees only the module
name being imported, not which caller triggered it. Hard-blocking numpy would
therefore also break the legitimate ``import shapely`` this package depends
on, so numpy is deliberately left out of the meta-path block list below.

What this test actually enforces: torch, doctr, torchvision, cv2, pandas,
matplotlib, and transformers can never load, under any import path, because
nothing in this package's declared dependency set could legitimately need
them. Numpy is checked separately, and only as a today-true assertion: this
package currently imports no shapely-backed code, so ``numpy`` should not
appear in ``sys.modules`` either. That assertion is expected to need revision
once a subpackage (most likely ``geometry``) starts using shapely, at which
point numpy will legitimately load as shapely's own transitive dependency —
this test does not, and cannot, guarantee numpy will never load; it only
guarantees the seven modules above never will.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

# A blocker that makes importing any of these fail outright, simulating an
# environment where none of them is installed. Numpy is deliberately absent
# from this list; see the module docstring.
_BLOCK_HEAVY = """
import sys
import importlib.abc
import importlib.machinery


class _Blocker(importlib.abc.MetaPathFinder):
    _blocked = ("torch", "doctr", "torchvision", "cv2", "pandas", "matplotlib", "transformers")

    def find_spec(self, name, path, target=None):
        root = name.split(".")[0]
        if root in self._blocked:
            raise ModuleNotFoundError(f"No module named {root!r} (blocked)")
        return None


sys.meta_path.insert(0, _Blocker())
"""


def _run(body: str) -> subprocess.CompletedProcess[str]:
    """Run ``_BLOCK_HEAVY`` + ``body`` (dedented) in a clean subprocess."""
    code = _BLOCK_HEAVY + textwrap.dedent(body)
    return subprocess.run(  # noqa: S603 - fixed argv, test-controlled code
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )


def test_package_imports_without_heavy_stack() -> None:
    """Importing the root package pulls in none of the seven blocked modules."""
    result = _run(
        """
        import pdomain_book_contracts

        blocked = ("torch", "doctr", "torchvision", "cv2", "pandas", "matplotlib", "transformers")
        loaded = [name for name in blocked if name in sys.modules]
        assert not loaded, f"blocked modules loaded: {loaded}"
        print("OK")
        """
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_every_subpackage_imports_without_heavy_stack() -> None:
    """Every subpackage listed in the module layout imports cleanly."""
    result = _run(
        """
        import pdomain_book_contracts
        import pdomain_book_contracts.geometry
        import pdomain_book_contracts.text
        import pdomain_book_contracts.typography
        import pdomain_book_contracts.matching
        import pdomain_book_contracts.ocr
        import pdomain_book_contracts.layout
        import pdomain_book_contracts.sources.pgdp
        import pdomain_book_contracts.licensing
        import pdomain_book_contracts._schemas

        blocked = ("torch", "doctr", "torchvision", "cv2", "pandas", "matplotlib", "transformers")
        loaded = [name for name in blocked if name in sys.modules]
        assert not loaded, f"blocked modules loaded: {loaded}"
        print("OK")
        """
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_numpy_not_loaded_today() -> None:
    """Today, with no shapely-backed contract yet moved in, numpy stays out.

    See the module docstring: this is a today-true assertion about the
    package's current transitive weight, not a structural guarantee. It will
    need revising once a subpackage imports shapely, which legitimately pulls
    in numpy on its own.
    """
    result = _run(
        """
        import pdomain_book_contracts
        import pdomain_book_contracts.geometry
        import pdomain_book_contracts.text
        import pdomain_book_contracts.typography
        import pdomain_book_contracts.matching
        import pdomain_book_contracts.ocr
        import pdomain_book_contracts.layout
        import pdomain_book_contracts.sources.pgdp
        import pdomain_book_contracts.licensing
        import pdomain_book_contracts._schemas

        assert "numpy" not in sys.modules, "numpy was imported by the current empty skeleton"
        print("OK")
        """
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_shapely_itself_is_unaffected_by_the_blocker() -> None:
    """The blocker never touches shapely or its transitive numpy import.

    This documents, rather than just asserts by omission, that shapely stays
    importable (and pulls numpy in) under the same blocker used above — proof
    that the boundary above is deliberate, not an accident of shapely being
    untested.
    """
    result = _run(
        """
        import shapely

        assert "numpy" in sys.modules, "shapely no longer pulls in numpy; re-check this test's premise"
        print("OK")
        """
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
