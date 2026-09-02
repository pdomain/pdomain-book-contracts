import json
import pathlib
from logging import getLogger
from typing import cast

import regex

# Configure logging
logger = getLogger(__name__)


class PGDPResults:
    # NOTE: kept as a plain class (not @dataclass) because the constructor
    # runs ``process()`` to populate the ``processed_*`` and ``original_lines``
    # fields from ``page_text``. Dataclass-with-__post_init__ would express
    # the same shape, but the public constructor takes only
    # ``(png_file, page_text)`` -- the other attributes are computed, not
    # injected -- so a custom __init__ is the honest representation. The
    # bare class-level annotations (R-19) were misleading because they
    # looked like class variables; they have been removed, and instance
    # attribute types are now declared inline in __init__.
    def __init__(self, png_file: str, page_text: str) -> None:
        self.png_file: str = png_file
        self.png_full_path: pathlib.Path = pathlib.Path(png_file).resolve()
        self.original_page_text: str = page_text
        self.original_lines: list[str] = page_text.splitlines()
        # processed_* fields populated by self.process()
        self.processed_page_text: str = ""
        self.processed_lines: list[tuple[int, str]] = []
        self.processed_words: list[tuple[int, int, str]] = []
        _ = self.process()

    def process(self) -> "PGDPResults":
        text = self.original_page_text
        text = text.replace(
            "\r\n", "\n"
        )  # Convert Windows-style line breaks to Unix-style
        text = self.remove_proofer_notes(text)
        text = self.remove_blank_page(text)
        text = self.fix_pgdp_diacritics(text)
        text = self.fix_footnotes(text)
        text = self.split_hyphen_asterisk(text)
        text = self.convert_pgdp_dashes(text)
        text = self.remove_leading_trailing_asterisk(text)
        text = self.convert_straight_to_curly_quotes(text)

        self.processed_page_text = text

        self.processed_lines = [
            (line_idx, line) for line_idx, line in enumerate(text.splitlines())
        ]

        self.processed_words = [
            (line_nbr, word_nbr, word)
            for line_nbr, line in self.processed_lines
            for word_nbr, word in enumerate(line.split())
        ]
        return self

    @staticmethod
    def remove_blank_page(text: str) -> str:
        logger.debug("Removing blank page markers from text")
        s: str = regex.sub(r"\[Blank Page\]", "", text, flags=regex.DOTALL)
        if s == text:
            logger.debug("No blank page markers found")
        else:
            logger.debug("Blank page markers removed")
        return s

    @staticmethod
    def remove_proofer_notes(text: str) -> str:
        logger.debug("Removing proofer notes from text")
        s: str = regex.sub(r"\[\*.*?\]", "", text, flags=regex.DOTALL)
        if s == text:
            logger.debug("No proofer notes found")
        else:
            logger.debug("Proofer notes removed")
        return s

    @staticmethod
    def convert_pgdp_dashes(text: str) -> str:
        logger.debug("Converting PGDP dashes to Unicode dashes")
        s: str = regex.sub(r"----", "⸺", text, flags=regex.DOTALL)
        s = regex.sub(r"--", "\u2014", s, flags=regex.DOTALL)  # EM DASH
        if s == text:
            logger.debug("No PGDP dashes found")
        else:
            logger.debug("PGDP dashes converted")
        return s

    @staticmethod
    def convert_straight_to_curly_quotes(text: str) -> str:
        logger.debug("Converting straight quotes to curly quotes")
        # Heuristic approach (no heavy NLP): handle elisions, decades, contractions, then generic quotes.
        s: str = text

        elision_remainders = [
            "Tis",
            "tis",
            "Twas",
            "twas",
            "Twere",
            "twere",
            "Twill",
            "twill",
            "Twould",
            "twould",
            "Cause",
            "cause",
            "Round",
            "round",
            "Mid",
            "mid",
            "Mongst",
            "mongst",
            "Em",
            "em",
            "Ere",
            "ere",
            "En",
            "en",
            "N",
            "n",
            "Til",
            "til",
        ]

        # 1. Leading elisions
        elisions_pattern = (
            r"(?<=^|\s|[\"\u201c])'("
            + "|".join(elision_remainders)
            + r")(?=\b)"  # LEFT DOUBLE QUOTATION MARK
        )
        s = regex.sub(
            elisions_pattern, lambda m: "\u2019" + m.group(1), s
        )  # RIGHT SINGLE QUOTATION MARK

        # 2. Decade / year abbreviations
        s = regex.sub(
            r"(?<=^|\s|[\"\u201c])'(?=\d{2}s?\b)", "\u2019", s
        )  # RIGHT SINGLE QUOTATION MARK, LEFT DOUBLE QUOTATION MARK

        # 3. Contractions / possessives
        s = regex.sub(r"(?<=\w)'(?=\w)", "\u2019", s)  # RIGHT SINGLE QUOTATION MARK

        # 4. Double quotes
        s = regex.sub(
            r'(^|[\u2014⸺\s(\[{<])"', r"\1\u201c", s
        )  # LEFT DOUBLE QUOTATION MARK, EM DASH
        s = regex.sub(r'"', "\u201d", s)  # RIGHT DOUBLE QUOTATION MARK

        # 5. Opening single quotes excluding elisions & decades
        negative_lookahead = r"(?!\d{2}s?\b|" + "|".join(elision_remainders) + r"\b)"
        s = regex.sub(
            r"(^|[\s(\[{<])'" + negative_lookahead, r"\1\u2018", s
        )  # LEFT SINGLE QUOTATION MARK

        # 6. Opening single after em/long dash
        s = regex.sub(
            r"(?<=[\u2014⸺])'(?=\w)", "\u2018", s
        )  # LEFT SINGLE QUOTATION MARK, EM DASH
        s = regex.sub(
            r"(?<=[\u2014⸺]\s)'(?=\w)", "\u2018", s
        )  # LEFT SINGLE QUOTATION MARK, EM DASH

        # 7. Closing single quotes
        s = regex.sub(
            r"(?<=[\w.,!?;:])'(?=\s|$|[\"\u201d.,!?;:)\]}>])", "\u2019", s
        )  # RIGHT SINGLE QUOTATION MARK, RIGHT DOUBLE QUOTATION MARK
        s = regex.sub(
            r"(?<=[\u2014⸺])'(?=\s|$)", "\u2019", s
        )  # RIGHT SINGLE QUOTATION MARK, EM DASH
        s = regex.sub(r"(?<=\w)'(?=\b)", "\u2019", s)  # fallback

        # 8. Correct mis-assigned openings before elision remainders
        s = regex.sub(
            r"\u2018(" + "|".join(elision_remainders) + r")\b",
            lambda m: "\u2019" + m.group(1),
            s,  # LEFT SINGLE QUOTATION MARK, RIGHT SINGLE QUOTATION MARK
        )

        # 9. Remaining leading straight single quotes before lowercase word => opening curly
        return regex.sub(
            r"(?<=^|\s)'(?=[a-z])", "\u2018", s
        )  # LEFT SINGLE QUOTATION MARK

    @staticmethod
    def split_hyphen_asterisk(text: str) -> str:
        return regex.sub(r"-\*(\S+)\n(\S+)", r"-\n\1 \2", text)

    @staticmethod
    def remove_leading_trailing_asterisk(text: str) -> str:
        text = text.strip()
        if text[0:1] == "*":
            text = text[1:]
        # Trailing asterisk: drop the '*'. If preceded by a hyphen or em/long
        # dash, the dash is preserved (indicating a word continued onto the
        # next page); if there is no preceding dash, no dash is added.
        if text.endswith("*"):
            text = text[:-1]
        return text

    @staticmethod
    def fix_footnotes(text: str) -> str:
        return regex.sub(r"\[(\d+)\]", r"\1", text)

    @staticmethod
    def fix_pgdp_diacritics(text: str) -> str:
        text = regex.sub(r"\[=A\]", "Ā", text)
        text = regex.sub(r"\[=E\]", "Ē", text)
        text = regex.sub(r"\[=I\]", "Ī", text)
        text = regex.sub(r"\[=O\]", "Ō", text)
        text = regex.sub(r"\[=U\]", "Ū", text)
        text = regex.sub(r"\[=a\]", "ā", text)
        text = regex.sub(r"\[=e\]", "ē", text)
        text = regex.sub(r"\[=i\]", "ī", text)
        text = regex.sub(r"\[=o\]", "ō", text)
        text = regex.sub(r"\[=u\]", "ū", text)

        text = regex.sub(r"\[:A\]", "Ä", text)
        text = regex.sub(r"\[:E\]", "Ë", text)
        text = regex.sub(r"\[:I\]", "Ï", text)
        text = regex.sub(r"\[:O\]", "Ö", text)
        text = regex.sub(r"\[:U\]", "Ü", text)
        text = regex.sub(r"\[:a\]", "ä", text)
        text = regex.sub(r"\[:e\]", "ë", text)
        text = regex.sub(r"\[:i\]", "ï", text)
        text = regex.sub(r"\[:o\]", "ö", text)
        text = regex.sub(r"\[:u\]", "ü", text)

        text = regex.sub(r"\[\.A\]", "Ȧ", text)
        text = regex.sub(r"\[\.E\]", "Ė", text)
        text = regex.sub(r"\[\.I\]", "İ", text)
        text = regex.sub(r"\[\.O\]", "Ȯ", text)
        text = regex.sub(r"\[\.C\]", "Ċ", text)
        text = regex.sub(r"\[\.G\]", "Ġ", text)
        text = regex.sub(r"\[\.Z\]", "Ż", text)
        text = regex.sub(r"\[\.a\]", "ȧ", text)
        text = regex.sub(r"\[\.e\]", "ė", text)
        text = regex.sub(r"\[\.o\]", "ȯ", text)
        text = regex.sub(r"\[\.c\]", "ċ", text)
        text = regex.sub(r"\[\.g\]", "ġ", text)
        text = regex.sub(r"\[\.z\]", "ż", text)

        text = regex.sub(r"\[`A\]", "À", text)
        text = regex.sub(r"\[`E\]", "È", text)
        text = regex.sub(r"\[`I\]", "Ì", text)
        text = regex.sub(r"\[`O\]", "Ò", text)
        text = regex.sub(r"\[`U\]", "Ù", text)
        text = regex.sub(r"\['N\]", "Ǹ", text)
        text = regex.sub(r"\[`a\]", "à", text)
        text = regex.sub(r"\[`e\]", "è", text)
        text = regex.sub(r"\[`i\]", "ì", text)
        text = regex.sub(r"\[`o\]", "ò", text)
        text = regex.sub(r"\[`u\]", "ù", text)
        text = regex.sub(r"\['n\]", "ǹ", text)

        text = regex.sub(r"\['A\]", "Á", text)
        text = regex.sub(r"\['E\]", "É", text)
        text = regex.sub(r"\['I\]", "Í", text)
        text = regex.sub(r"\['O\]", "Ó", text)
        text = regex.sub(r"\['U\]", "Ú", text)
        text = regex.sub(r"\['Y\]", "Ý", text)
        text = regex.sub(r"\['a\]", "á", text)
        text = regex.sub(r"\['e\]", "é", text)
        text = regex.sub(r"\['i\]", "í", text)
        text = regex.sub(r"\['o\]", "ó", text)
        text = regex.sub(r"\['u\]", "ú", text)
        text = regex.sub(r"\['y\]", "ý", text)

        text = regex.sub(r"\[\)A\]", "Ă", text)
        text = regex.sub(r"\[\)E\]", "Ĕ", text)
        text = regex.sub(r"\[\)I\]", "Ĭ", text)
        text = regex.sub(r"\[\)O\]", "Ŏ", text)
        text = regex.sub(r"\[\)U\]", "Ŭ", text)
        text = regex.sub(r"\[\)a\]", "ă", text)
        text = regex.sub(r"\[\)e\]", "ĕ", text)
        text = regex.sub(r"\[\)i\]", "ĭ", text)
        text = regex.sub(r"\[\)o\]", "ŏ", text)
        text = regex.sub(r"\[\)u\]", "ŭ", text)

        return regex.sub(r"\[c,\]", "ç", text)


class PGDPExport:
    pages: list[PGDPResults]
    project_id: str

    def __init__(self, pages: list[PGDPResults], project_id: str) -> None:
        self.pages = pages
        self.project_id = project_id

    @classmethod
    def from_json_file(cls, input_file_path: pathlib.Path | str) -> "PGDPExport":
        if isinstance(input_file_path, str):
            input_file_path = pathlib.Path(input_file_path)
        if not input_file_path.exists():
            raise FileNotFoundError(f"File not found: {input_file_path}")
        if not input_file_path.is_file():
            raise FileNotFoundError(f"Not a file: {input_file_path}")
        with open(input_file_path.resolve(), encoding="utf-8") as json_file:
            return cls.from_json(json_file.read(), input_file_path.parent)

    @classmethod
    def from_json(cls, json_str: str, path_prefix: pathlib.Path | str) -> "PGDPExport":
        # Hoisted above the loop (L-26): when ``pages`` is empty the loop
        # body never runs, so the in-loop str->Path conversion left
        # ``path_prefix`` as a ``str`` and ``path_prefix.stem`` raised
        # ``AttributeError`` on the return line. Convert once up front.
        if isinstance(path_prefix, str):
            path_prefix = pathlib.Path(path_prefix)
        pages = cast("dict[str, str]", json.loads(json_str))
        new_pages: list[PGDPResults] = []
        for png_file, page_text in pages.items():
            png_full_file_path = pathlib.Path(path_prefix, png_file)
            new_pages.append(PGDPResults(str(png_full_file_path), page_text))
        return cls(pages=new_pages, project_id=path_prefix.stem)
