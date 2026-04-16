"""
Data Cleaner for LexiFusionNet.

Handles removal of IndianKanoon page markers, repeated headers,
and whitespace normalization from raw judgment text files.
"""

import re
from typing import Optional


# Pre-compiled patterns for performance
# Matches: "Indian Kanoon - http://indiankanoon.org/doc/1857950/" followed by page number
_PAGE_MARKER_RE = re.compile(
    r'^.*Indian Kanoon\s*-\s*http://indiankanoon\.org/doc/\d+/?\s*\n\d+\s*$',
    re.MULTILINE
)

# Matches a standalone page number line (just digits, possibly with whitespace)
_STANDALONE_PAGE_NUM_RE = re.compile(r'^\s*\d{1,4}\s*$', re.MULTILINE)


def clean_text(raw_text: str, case_title: Optional[str] = None) -> str:
    """
    Clean raw IndianKanoon judgment text.

    Steps:
    1. Remove IndianKanoon page markers (URL + page number)
    2. Remove repeated case title lines at page breaks
    3. Collapse excessive whitespace (3+ newlines → 2)
    4. Strip leading/trailing whitespace

    Args:
        raw_text: Raw text from .txt file.
        case_title: If provided, removes repeated occurrences of this title
                    (which appear at every page break in IndianKanoon exports).

    Returns:
        Cleaned text string.
    """
    text = raw_text

    # Step 1: Remove IndianKanoon page markers
    # Pattern: "<case title> on <date>\nIndian Kanoon - http://indiankanoon.org/doc/XXXXX/\n<page_num>"
    text = _PAGE_MARKER_RE.sub('', text)

    # Step 2: Remove repeated case title lines at page breaks
    if case_title:
        # Escape the title for regex use and match the repeated header line
        escaped_title = re.escape(case_title)
        # Match lines that are just the case title (possibly with trailing date info)
        title_repeat_re = re.compile(
            r'^' + escaped_title + r'.*$',
            re.MULTILINE
        )
        # Keep the first occurrence (line 1), remove subsequent ones
        matches = list(title_repeat_re.finditer(text))
        if len(matches) > 1:
            # Remove all except the first match
            for match in reversed(matches[1:]):
                text = text[:match.start()] + text[match.end():]

    # Step 3: Collapse excessive whitespace
    # 3+ consecutive newlines → 2 newlines (preserve paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Collapse multiple spaces within lines (but preserve intentional indentation)
    text = re.sub(r'[^\S\n]{3,}', '  ', text)

    # Step 4: Strip leading/trailing whitespace
    text = text.strip()

    return text


def extract_title_from_first_line(raw_text: str) -> Optional[str]:
    """
    Extract the case title from the first line of the file.

    The first line follows the pattern:
    "A.K. Gopalan vs The State Of Madras.Union Of India: ... on 19 May, 1950"

    We extract everything before " on " followed by a date pattern.

    Returns:
        The case title string, or None if parsing fails.
    """
    first_line = raw_text.split('\n', 1)[0].strip()
    if not first_line:
        return None

    # Try to split on " on <day> <month>, <year>" or " on <day>/<month>/<year>"
    date_split = re.split(r'\s+on\s+\d{1,2}[\s/]', first_line)
    if date_split:
        return date_split[0].strip()

    return first_line
