"""
Quality Checker for LexiFusionNet — Phase 0.

Performs multi-dimensional quality analysis on parsed judgment text:
  A. Semantic Corruption — abnormal word lengths, empty/near-empty content
  B. Missing Legal Sections — absence of JUDGMENT/ORDER/PETITIONER/RESPONDENT
  C. Broken Sentences — fragmented text, too many very short sentences
  D. Encoding Artifacts — replacement chars, null bytes, invalid Unicode
  E. OCR Noise — excessive special chars, spaced-out words, symbol bursts

Each check produces a sub-score (0.0–1.0). The final score is a weighted
average. Files are classified as OK (≥0.8), REVIEW (0.6–0.8), or REJECT (<0.6).
"""

import re
from dataclasses import dataclass, field
from typing import List


# ─── Weights ────────────────────────────────────────────────────────────────────
CHECK_WEIGHTS = {
    "semantic": 0.20,
    "missing_sections": 0.15,
    "broken_sentences": 0.20,
    "encoding": 0.20,
    "ocr_noise": 0.25,
}


@dataclass
class QualityResult:
    """Result of quality analysis for a single file."""

    score: float  # 0.0 – 1.0 weighted aggregate
    flag: str  # "OK" | "REVIEW" | "REJECT"
    issues: List[str] = field(default_factory=list)
    check_scores: dict = field(default_factory=dict)


# ─── Individual Checks ─────────────────────────────────────────────────────────

def _check_semantic(text: str) -> tuple[float, list[str]]:
    """
    Detect semantically corrupt text.

    Checks:
    - Empty or near-empty content (< 100 chars)
    - Abnormal average word length (< 2 or > 15 characters)
    """
    issues = []

    if len(text.strip()) < 100:
        issues.append(f"Near-empty content ({len(text.strip())} chars)")
        return 0.0, issues

    words = text.split()
    if not words:
        issues.append("No words detected in text")
        return 0.0, issues

    avg_word_len = sum(len(w) for w in words) / len(words)

    if avg_word_len < 2:
        issues.append(f"Avg word length abnormally short ({avg_word_len:.1f} chars)")
        return 0.2, issues
    elif avg_word_len > 15:
        issues.append(f"Avg word length abnormally long ({avg_word_len:.1f} chars)")
        return 0.2, issues
    elif avg_word_len < 3 or avg_word_len > 12:
        issues.append(f"Avg word length suspicious ({avg_word_len:.1f} chars)")
        return 0.6, issues

    return 1.0, issues


def _check_missing_sections(text: str) -> tuple[float, list[str]]:
    """
    Check for absence of expected legal structure keywords.

    Looks for at least one of:
    - JUDGMENT / ORDER
    - PETITIONER / RESPONDENT
    """
    issues = []
    upper_text = text.upper()

    has_judgment = "JUDGMENT" in upper_text or "ORDER" in upper_text
    has_parties = "PETITIONER" in upper_text or "RESPONDENT" in upper_text

    # Also check for common judgment body markers
    has_court_marker = (
        "SUPREME COURT" in upper_text
        or "HIGH COURT" in upper_text
        or "COURT" in upper_text
    )

    found_count = sum([has_judgment, has_parties, has_court_marker])

    if found_count == 0:
        issues.append("No legal structure keywords found (JUDGMENT/ORDER/PETITIONER/RESPONDENT/COURT)")
        return 0.3, issues
    elif found_count == 1:
        missing = []
        if not has_judgment:
            missing.append("JUDGMENT/ORDER")
        if not has_parties:
            missing.append("PETITIONER/RESPONDENT")
        if not has_court_marker:
            missing.append("COURT reference")
        issues.append(f"Missing legal sections: {', '.join(missing)}")
        return 0.6, issues
    elif found_count == 2:
        return 0.9, issues

    return 1.0, issues


def _check_broken_sentences(text: str) -> tuple[float, list[str]]:
    """
    Detect fragmented or broken sentence structure.

    Flags:
    - > 50% of sentences under 4 words → fragmented
    - > 70% under 4 words → severely fragmented
    """
    issues = []

    # Split on sentence-ending punctuation
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        issues.append("No sentences detected")
        return 0.0, issues

    if len(sentences) < 3:
        # Too few sentences to judge meaningfully
        return 0.8, issues

    short_count = sum(1 for s in sentences if len(s.split()) < 4)
    short_ratio = short_count / len(sentences)

    if short_ratio > 0.70:
        issues.append(f"Severely fragmented text ({short_ratio:.0%} sentences under 4 words)")
        return 0.1, issues
    elif short_ratio > 0.50:
        issues.append(f"Fragmented text ({short_ratio:.0%} sentences under 4 words)")
        return 0.4, issues
    elif short_ratio > 0.35:
        issues.append(f"Somewhat fragmented text ({short_ratio:.0%} sentences under 4 words)")
        return 0.7, issues

    return 1.0, issues


def _check_encoding(text: str) -> tuple[float, list[str]]:
    """
    Detect encoding artifacts.

    Checks:
    - Replacement character (U+FFFD, displayed as '�')
    - Null bytes
    - High ratio of non-ASCII, non-printable characters
    """
    issues = []

    replacement_count = text.count('\ufffd')
    null_count = text.count('\x00')
    text_len = max(len(text), 1)  # avoid division by zero

    # Count characters that are not printable and not standard whitespace
    non_printable = sum(
        1 for ch in text
        if not ch.isprintable() and ch not in '\n\r\t'
    )

    total_bad = replacement_count + null_count + non_printable
    bad_ratio = total_bad / text_len

    if null_count > 0:
        issues.append(f"Contains {null_count} null bytes")

    if replacement_count > 0:
        issues.append(f"Contains {replacement_count} replacement characters (�)")

    if bad_ratio > 0.05:
        issues.append(f"High encoding corruption ({bad_ratio:.1%} non-printable chars)")
        return 0.1, issues
    elif bad_ratio > 0.01:
        issues.append(f"Moderate encoding corruption ({bad_ratio:.1%} non-printable chars)")
        return 0.4, issues
    elif bad_ratio > 0.005:
        return 0.7, issues
    elif total_bad > 0:
        return 0.85, issues

    return 1.0, issues


# Pre-compiled patterns for OCR noise detection
_SPACED_WORD_RE = re.compile(
    r'(?<!\S)([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z])(?:\s+[A-Z])*(?!\S)'
)
_SYMBOL_BURST_RE = re.compile(r'[^a-zA-Z0-9\s.,;:\'\"()\-]{4,}')
_SPECIAL_CHAR_RE = re.compile(r'[^a-zA-Z0-9\s.,;:\'\"()\-/§&@#]')


def _check_ocr_noise(text: str) -> tuple[float, list[str]]:
    """
    Detect OCR noise patterns.

    Checks:
    - Excessive special characters (> 15% of text)
    - Spaced-out characters (e.g., "J U D G M E N T")
    - Random symbol bursts (4+ consecutive non-standard chars)
    """
    issues = []
    text_len = max(len(text), 1)

    # 1. Special character ratio
    special_count = len(_SPECIAL_CHAR_RE.findall(text))
    special_ratio = special_count / text_len

    # 2. Spaced-out word detection
    spaced_matches = _SPACED_WORD_RE.findall(text)
    spaced_count = len(spaced_matches)

    # 3. Symbol burst detection
    burst_matches = _SYMBOL_BURST_RE.findall(text)
    burst_count = len(burst_matches)

    score = 1.0

    if special_ratio > 0.15:
        issues.append(f"Excessive special characters ({special_ratio:.1%} of text)")
        score = min(score, 0.2)
    elif special_ratio > 0.08:
        issues.append(f"High special character ratio ({special_ratio:.1%})")
        score = min(score, 0.5)
    elif special_ratio > 0.04:
        score = min(score, 0.8)

    if spaced_count > 5:
        issues.append(f"Many spaced-out words detected ({spaced_count} occurrences)")
        score = min(score, 0.3)
    elif spaced_count > 2:
        issues.append(f"Some spaced-out words detected ({spaced_count} occurrences)")
        score = min(score, 0.6)

    if burst_count > 10:
        issues.append(f"Frequent symbol bursts ({burst_count} occurrences)")
        score = min(score, 0.3)
    elif burst_count > 3:
        issues.append(f"Some symbol bursts ({burst_count} occurrences)")
        score = min(score, 0.6)

    return score, issues


# ─── Main Entry Point ──────────────────────────────────────────────────────────

def check_quality(text: str) -> QualityResult:
    """
    Run all quality checks on a text and return a QualityResult.

    Args:
        text: The raw or cleaned judgment text.

    Returns:
        QualityResult with score, flag, issues, and per-check breakdown.
    """
    if not text or not text.strip():
        return QualityResult(
            score=0.0,
            flag="REJECT",
            issues=["Empty text"],
            check_scores={k: 0.0 for k in CHECK_WEIGHTS},
        )

    checks = {
        "semantic": _check_semantic,
        "missing_sections": _check_missing_sections,
        "broken_sentences": _check_broken_sentences,
        "encoding": _check_encoding,
        "ocr_noise": _check_ocr_noise,
    }

    all_issues = []
    check_scores = {}
    weighted_sum = 0.0

    for name, func in checks.items():
        sub_score, sub_issues = func(text)
        check_scores[name] = round(sub_score, 3)
        all_issues.extend(sub_issues)
        weighted_sum += sub_score * CHECK_WEIGHTS[name]

    final_score = round(weighted_sum, 3)

    if final_score >= 0.8:
        flag = "OK"
    elif final_score >= 0.6:
        flag = "REVIEW"
    else:
        flag = "REJECT"

    return QualityResult(
        score=final_score,
        flag=flag,
        issues=all_issues,
        check_scores=check_scores,
    )
