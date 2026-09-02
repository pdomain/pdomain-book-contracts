from enum import Enum


class CharacterGroups(Enum):
    """Groups of visually/semantically interchangeable characters for fuzzy matching."""

    HYPHEN = ["-"]
    ENDASH = ["\u2013"]  # EN DASH
    EMDASH = ["—"]
    FIGUREDASH = ["\u2012"]  # FIGURE DASH
    TWOEMDASH = ["⸺"]
    THREEEMDASH = ["⸻"]
    HORIZONTAL_BAR = ["―"]
    NOBREAK_HYPHEN = ["\u2011"]  # NON-BREAKING HYPHEN
    MINUS = ["\u2212"]  # MINUS SIGN
    # NOTE: dict.fromkeys (not set) so iteration order is stable across
    # Python interpreter runs. Tied-variant matching in
    # ground_truth_matching is sensitive to ordering, and set() has
    # PYTHONHASHSEED-dependent iteration. See review M-26.
    DASHES = list(
        dict.fromkeys(
            HYPHEN
            + ENDASH
            + EMDASH
            + FIGUREDASH
            + TWOEMDASH
            + THREEEMDASH
            + HORIZONTAL_BAR
            + NOBREAK_HYPHEN
            + MINUS
        )
    )
    SINGLE_QUOTE = ["'", "\u2018", "\u2019"]  # LEFT/RIGHT SINGLE QUOTATION MARK
    DOUBLE_QUOTE = ['"', "“", "”"]
    QUOTES = list(dict.fromkeys(SINGLE_QUOTE + DOUBLE_QUOTE))
    SINGLE_PRIME = ["'", "\u2032"]  # PRIME
    DOUBLE_PRIME = ['"', "″"]
    PRIMES = list(dict.fromkeys(SINGLE_PRIME + DOUBLE_PRIME))
    QUOTES_AND_PRIMES = list(dict.fromkeys(QUOTES + PRIMES))

    def __contains__(self, char: object) -> bool:
        return char in self.value
