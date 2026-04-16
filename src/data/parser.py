"""
Judgment Parser for LexiFusionNet.

Parses raw IndianKanoon judgment text files into structured JSON.
Handles two distinct document formats:
  - Pre-2000: Contains PETITIONER/RESPONDENT, CITATION, CITATOR INFO, HEADNOTE, ACT blocks
  - Post-2000: Simpler header (title, citations, author, bench) followed by judgment body
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import List, Optional

from src.data.cleaner import clean_text, extract_title_from_first_line


@dataclass
class ParsedJudgment:
    """Structured representation of a parsed judgment."""
    case_id: str
    title: str
    date_str: str  # Original date string from text
    year: int
    citations: List[str] = field(default_factory=list)
    author: Optional[str] = None
    bench: List[str] = field(default_factory=list)
    headnote: Optional[str] = None
    acts: List[str] = field(default_factory=list)
    citator_info: List[dict] = field(default_factory=list)
    body: str = ""
    file_path: str = ""
    file_size: int = 0
    is_valid: bool = True
    parse_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Citation Extraction Patterns ────────────────────────────────────────────

_EQUIV_CITATIONS_RE = re.compile(
    r'^Equivalent citations?:\s*(.+)$', re.MULTILINE | re.IGNORECASE
)

_AUTHOR_RE = re.compile(
    r'^Author:\s*(.+)$', re.MULTILINE
)

_BENCH_RE = re.compile(
    r'^Bench:\s*(.+)$', re.MULTILINE
)

_DATE_RE = re.compile(
    r'on\s+(\d{1,2})\s+(\w+),?\s+(\d{4})'
)

_DATE_SLASH_RE = re.compile(
    r'DATE OF JUDGMENT[:\s]*(\d{1,2})/(\d{1,2})/(\d{4})', re.IGNORECASE
)

# Statute/Act references in body text
_STATUTE_RE = re.compile(
    r'(?:Section|Article|Rule|Order)\s+\d+[A-Za-z]?(?:\(\d+\))?'
    r'|(?:the\s+)?[\w\s]+Act,?\s+\d{4}'
    r'|(?:the\s+)?[\w\s]+Code,?\s+\d{4}',
    re.IGNORECASE
)

# CITATOR INFO line pattern: "F  1951 SC 157  (21)"
_CITATOR_LINE_RE = re.compile(
    r'^\s*(F|R|D|O|E|RF|APL|E&F|E&R)\s+(\d{4})\s+SC\s*(\d+)\s*(?:\((.+?)\))?\s*$',
    re.MULTILINE
)

MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}


def _generate_case_id(file_path: str) -> str:
    """Generate a deterministic case ID from the file path."""
    return hashlib.sha256(file_path.encode()).hexdigest()[:16]


def _parse_date(text: str, year_from_dir: int) -> tuple[str, int]:
    """
    Extract date from the text.

    Returns:
        Tuple of (date_string, year).
    """
    # Try "on DD Month, YYYY" pattern first (most common)
    match = _DATE_RE.search(text[:500])
    if match:
        day, month_str, year_str = match.groups()
        year = int(year_str)
        month_num = MONTH_MAP.get(month_str.lower(), 0)
        if month_num:
            return f"{year}-{month_num:02d}-{int(day):02d}", year
        return f"{year}-00-{int(day):02d}", year

    # Try "DATE OF JUDGMENT: DD/MM/YYYY" pattern (pre-2000 files)
    match = _DATE_SLASH_RE.search(text[:2000])
    if match:
        day, month, year_str = match.groups()
        year = int(year_str)
        return f"{year}-{int(month):02d}-{int(day):02d}", year

    # Fallback to directory year
    return f"{year_from_dir}-01-01", year_from_dir


def _parse_citations(text: str) -> List[str]:
    """Extract equivalent citation codes from the header."""
    match = _EQUIV_CITATIONS_RE.search(text[:1000])
    if not match:
        return []

    raw = match.group(1).strip()
    # Citations are comma-separated but may contain internal commas in long names
    # Split on comma followed by a space and a year-like pattern or uppercase word
    citations = [c.strip() for c in raw.split(',')]
    # Clean up and filter empty
    return [c for c in citations if c and len(c) > 3]


def _parse_author(text: str) -> Optional[str]:
    """Extract the author (writing judge) from the header."""
    match = _AUTHOR_RE.search(text[:500])
    if match:
        return match.group(1).strip()
    return None


def _parse_bench(text: str) -> List[str]:
    """Extract the bench (list of judges) from the header."""
    match = _BENCH_RE.search(text[:800])
    if not match:
        return []

    raw = match.group(1).strip()
    # Judges are comma-separated
    judges = [j.strip() for j in raw.split(',')]
    return [j for j in judges if j and len(j) > 2]


def _extract_headnote(text: str) -> Optional[str]:
    """
    Extract HEADNOTE section (pre-2000 files only).

    The HEADNOTE appears between 'HEADNOTE:' and either 'JUDGMENT:' or 'JUDGMENT'
    on its own line.
    """
    # Find HEADNOTE start
    hn_match = re.search(r'^HEADNOTE:\s*$', text, re.MULTILINE)
    if not hn_match:
        return None

    start = hn_match.end()

    # Find JUDGMENT start (end of headnote)
    jg_match = re.search(r'^JUDGMENT:?\s*$', text[start:], re.MULTILINE)
    if jg_match:
        end = start + jg_match.start()
    else:
        # If no JUDGMENT marker, take next 2000 chars as headnote
        end = min(start + 2000, len(text))

    headnote = text[start:end].strip()
    return headnote if len(headnote) > 50 else None


def _extract_body(text: str) -> str:
    """
    Extract the judgment body text.

    Strategy:
    - If JUDGMENT: marker exists, take everything after it
    - Otherwise, skip the header (first ~10% of structured blocks) and take the rest
    """
    # Try to find explicit JUDGMENT marker
    jg_match = re.search(r'^JUDGMENT:?\s*$', text, re.MULTILINE)
    if jg_match:
        return text[jg_match.end():].strip()

    # For post-2000 files without explicit marker, skip the header block
    # Headers typically end within the first 500-1000 characters
    # Look for the first substantive paragraph after bench/author info
    lines = text.split('\n')
    body_start = 0

    for i, line in enumerate(lines):
        # Skip past header lines (title, citations, author, bench, court header)
        if i < 4:
            continue
        # Look for first line that looks like judgment text
        stripped = line.strip()
        if (len(stripped) > 80 and
                not stripped.startswith(('PETITIONER', 'RESPONDENT', 'BENCH:',
                                        'CITATION', 'CITATOR', 'ACT:', 'DATE OF'))):
            body_start = i
            break

    if body_start == 0:
        body_start = min(5, len(lines))

    return '\n'.join(lines[body_start:]).strip()


def _extract_acts(body: str) -> List[str]:
    """
    Extract statute/act references from the body text.

    Returns deduplicated list of referenced statutes.
    """
    matches = _STATUTE_RE.findall(body)
    # Normalize: strip whitespace, deduplicate
    seen = set()
    result = []
    for m in matches:
        normalized = re.sub(r'\s+', ' ', m.strip())
        if normalized.lower() not in seen and len(normalized) > 5:
            seen.add(normalized.lower())
            result.append(normalized)
    return result[:50]  # Cap at 50 to avoid noise from verbose judgments


def _extract_citator_info(text: str) -> List[dict]:
    """
    Extract CITATOR INFO block (pre-1990 files only).

    Returns list of dicts: {type, year, sc_number, paragraphs}
    """
    # Find CITATOR INFO section
    ci_match = re.search(r'CITATOR INFO\s*:', text)
    if not ci_match:
        return []

    # Search within the next 5000 chars
    search_region = text[ci_match.end():ci_match.end() + 5000]

    results = []
    for match in _CITATOR_LINE_RE.finditer(search_region):
        cite_type, year, sc_num, paras = match.groups()
        results.append({
            'type': cite_type,
            'citation': f"{year} SC {sc_num}",
            'paragraphs': paras
        })

    return results


def parse_file(file_path: Path, year_from_dir: int) -> ParsedJudgment:
    """
    Parse a single judgment text file into a structured ParsedJudgment.

    Args:
        file_path: Path to the .txt file.
        year_from_dir: Year extracted from the directory name (fallback for date).

    Returns:
        ParsedJudgment with all extracted fields.
    """
    errors = []
    file_size = file_path.stat().st_size

    try:
        raw_text = file_path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return ParsedJudgment(
            case_id=_generate_case_id(str(file_path)),
            title=file_path.stem,
            date_str=f"{year_from_dir}-01-01",
            year=year_from_dir,
            file_path=str(file_path),
            file_size=file_size,
            is_valid=False,
            parse_errors=[f"Failed to read file: {e}"]
        )

    # Check minimum size
    if file_size < 500:
        return ParsedJudgment(
            case_id=_generate_case_id(str(file_path)),
            title=file_path.stem,
            date_str=f"{year_from_dir}-01-01",
            year=year_from_dir,
            file_path=str(file_path),
            file_size=file_size,
            is_valid=False,
            parse_errors=["File too small (< 500 bytes), likely corrupt or stub"]
        )

    case_id = _generate_case_id(str(file_path))

    # Extract title from first line
    title = extract_title_from_first_line(raw_text)
    if not title:
        title = file_path.stem.replace('_', ' ')
        errors.append("Could not parse title from first line")

    # Clean text (strip page markers, repeated headers)
    cleaned = clean_text(raw_text, case_title=title)

    # Parse metadata fields
    date_str, year = _parse_date(raw_text, year_from_dir)
    citations = _parse_citations(raw_text)
    author = _parse_author(raw_text)
    bench = _parse_bench(raw_text)

    # Extract structured sections
    headnote = _extract_headnote(raw_text)
    citator_info = _extract_citator_info(raw_text)

    # Extract body text from cleaned version
    body = _extract_body(cleaned)

    # Extract acts/statutes from body
    acts = _extract_acts(body)

    # Validate body
    if len(body) < 200:
        errors.append(f"Body text suspiciously short ({len(body)} chars)")
        is_valid = len(body) > 50  # Still usable if > 50 chars
    else:
        is_valid = True

    if not citations:
        errors.append("No equivalent citations found")

    return ParsedJudgment(
        case_id=case_id,
        title=title,
        date_str=date_str,
        year=year,
        citations=citations,
        author=author,
        bench=bench,
        headnote=headnote,
        acts=acts,
        citator_info=citator_info,
        body=body,
        file_path=str(file_path),
        file_size=file_size,
        is_valid=is_valid,
        parse_errors=errors,
    )


def parse_corpus(
    raw_data_dir: Path,
    output_dir: Path,
    verbose: bool = True
) -> dict:
    """
    Parse all judgment files in the corpus.

    Args:
        raw_data_dir: Root directory containing year subdirectories.
        output_dir: Directory to write parsed JSON files.

    Returns:
        Summary dict with counts and error info.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    valid = 0
    invalid = 0
    errors_list = []

    # Iterate year directories
    year_dirs = sorted(raw_data_dir.iterdir())
    for year_dir in year_dirs:
        if not year_dir.is_dir():
            continue

        try:
            year = int(year_dir.name)
        except ValueError:
            continue

        year_output = output_dir / year_dir.name
        year_output.mkdir(exist_ok=True)

        txt_files = sorted(year_dir.glob('*.txt'))
        for txt_file in txt_files:
            total += 1

            parsed = parse_file(txt_file, year)

            if parsed.is_valid:
                valid += 1
            else:
                invalid += 1
                errors_list.append({
                    'file': str(txt_file),
                    'errors': parsed.parse_errors
                })

            # Write JSON output
            out_file = year_output / f"{txt_file.stem}.json"
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(parsed.to_dict(), f, indent=2, ensure_ascii=False)

        if verbose:
            year_count = len(txt_files)
            print(f"  {year}: {year_count} files parsed")

    summary = {
        'total': total,
        'valid': valid,
        'invalid': invalid,
        'error_files': errors_list[:50],  # Cap output
    }

    if verbose:
        print(f"\nParsing complete: {valid}/{total} valid, {invalid} invalid")

    return summary
