"""
Tests for the quality scoring engine.

Validates that quality checks correctly classify text as OK, REVIEW, or REJECT
across diverse input qualities.
"""

import pytest

from src.diagnostics.quality_checker import check_quality, QualityResult


# ─── Clean Legal Text ────────────────────────────────────────────────────────

CLEAN_TEXT = """
JUDGMENT

The Supreme Court of India hereby delivers this judgment in the matter of
State of Maharashtra versus Rajesh Kumar. The petitioner has challenged the
order of the High Court dated 15th March, 2023.

After hearing learned counsel for both parties and examining the evidence
on record, this Court is of the opinion that the High Court was correct
in its interpretation of Section 302 of the Indian Penal Code, 1860.

The appeal is dismissed with costs. The respondent is entitled to recovery
of all amounts due under the decree. The interim order, if any, stands
vacated. The parties shall bear their own costs. This Court expresses
its appreciation for the detailed submissions made by learned counsel on
both sides.

ORDER:
The appeal stands dismissed. The judgment of the High Court is affirmed.
All pending applications are disposed of.
"""


class TestCleanText:
    """Clean legal text should score OK (≥ 0.8)."""

    def test_flag_is_ok(self):
        result = check_quality(CLEAN_TEXT)
        assert result.flag == "OK"

    def test_score_above_threshold(self):
        result = check_quality(CLEAN_TEXT)
        assert result.score >= 0.8

    def test_check_scores_present(self):
        result = check_quality(CLEAN_TEXT)
        assert "semantic" in result.check_scores
        assert "encoding" in result.check_scores
        assert "ocr_noise" in result.check_scores

    def test_minimal_issues(self):
        result = check_quality(CLEAN_TEXT)
        # Clean text may still have minor issues, but no critical ones
        critical = [i for i in result.issues if "corruption" in i.lower() or "reject" in i.lower()]
        assert len(critical) == 0


# ─── Encoding Garbage ────────────────────────────────────────────────────────

ENCODING_GARBAGE = "\ufffd" * 200 + "\x00" * 50 + "random text " * 20


class TestEncodingGarbage:
    """Text with heavy encoding corruption should be REJECT."""

    def test_flag_is_reject(self):
        result = check_quality(ENCODING_GARBAGE)
        assert result.flag == "REJECT"

    def test_score_below_threshold(self):
        result = check_quality(ENCODING_GARBAGE)
        assert result.score < 0.6

    def test_encoding_check_low(self):
        result = check_quality(ENCODING_GARBAGE)
        assert result.check_scores["encoding"] < 0.5

    def test_issues_reported(self):
        result = check_quality(ENCODING_GARBAGE)
        assert any("replacement" in i.lower() or "null" in i.lower() for i in result.issues)


# ─── Partial Noise (REVIEW range) ────────────────────────────────────────────

PARTIAL_NOISE = """
The Supreme Court of India delivers its judgment in this case. The appeal
is dismissed. The High Court order is affirmed.

Some \ufffd characters appear here \ufffd but the overall text is mostly readable
and contains legal content about the Constitution and various orders passed
by the court in this matter. The respondent is entitled to costs throughout.
The petition under Article 32 is allowed.

We have examined the evidence on record and find that the trial court and
the High Court were correct in their assessment of the facts. The appellant's
contentions are without merit and are accordingly rejected. The interim
stay granted earlier stands vacated.
"""


class TestPartialNoise:
    """Text with some noise should score in REVIEW range."""

    def test_flag_is_review_or_ok(self):
        result = check_quality(PARTIAL_NOISE)
        assert result.flag in ("REVIEW", "OK")

    def test_score_in_mid_range(self):
        result = check_quality(PARTIAL_NOISE)
        assert result.score >= 0.5


# ─── Empty Text ──────────────────────────────────────────────────────────────

class TestEmptyText:
    """Empty or whitespace-only text should be REJECT with score 0."""

    def test_empty_string(self):
        result = check_quality("")
        assert result.flag == "REJECT"
        assert result.score == 0.0

    def test_whitespace_only(self):
        result = check_quality("   \n\n\t  ")
        assert result.flag == "REJECT"
        assert result.score == 0.0

    def test_none_input(self):
        result = check_quality(None)
        assert result.flag == "REJECT"
        assert result.score == 0.0

    def test_issues_reported(self):
        result = check_quality("")
        assert "Empty text" in result.issues


# ─── Near-Empty Content ─────────────────────────────────────────────────────

class TestNearEmpty:
    """Very short text (< 100 chars) should score low and not be OK."""

    def test_short_text_not_ok(self):
        result = check_quality("Short text only.")
        assert result.flag in ("REVIEW", "REJECT")
        assert result.score < 0.8


# ─── Fragmented Text ────────────────────────────────────────────────────────

FRAGMENTED_TEXT = """
Yes. No. Ok. Done. The. Court. Orders. That. The. Appeal.
Is. Dismissed. With. Costs. To. The. Respondent. Here.
Next. Point. Goes. Here. And. Another. One. Too. Plus.
More. Items. Listed. Below. For. Reference. Only. Now.
Again. Short. Words. Come. Here. Final. Sentence. Made.
Short. Words. Everywhere. In. This. Document. Being. Read.
"""


class TestFragmentedText:
    """Highly fragmented text should score low on broken_sentences check."""

    def test_broken_sentences_flagged(self):
        result = check_quality(FRAGMENTED_TEXT)
        assert result.check_scores["broken_sentences"] < 0.5

    def test_issues_mention_fragmented(self):
        result = check_quality(FRAGMENTED_TEXT)
        assert any("fragmented" in i.lower() for i in result.issues)


# ─── OCR Spaced Out Words ───────────────────────────────────────────────────

OCR_SPACED_TEXT = """
J U D G M E N T delivered by the court on this day. The appeal is
dismissed. S U P R E M E  C O U R T  of India hereby orders that the
respondent is entitled to costs. O R D E R passed accordingly.
The parties shall comply with this J U D G M E N T forthwith.
The R E S P O N D E N T is directed to file compliance report.
This is the final O R D E R of this court in the matter.
The petitioner's arguments have been fully considered by this bench
and found to be without any substance or legal merit whatsoever.
"""


class TestOCRSpacedWords:
    """Spaced-out characters should reduce OCR noise score."""

    def test_ocr_noise_detected(self):
        result = check_quality(OCR_SPACED_TEXT)
        assert result.check_scores["ocr_noise"] < 1.0


# ─── Return Type Validation ─────────────────────────────────────────────────

class TestReturnType:
    """All returns should be proper QualityResult instances."""

    def test_returns_quality_result(self):
        result = check_quality("Some text. " * 50)
        assert isinstance(result, QualityResult)

    def test_score_in_range(self):
        result = check_quality("Some text. " * 50)
        assert 0.0 <= result.score <= 1.0

    def test_flag_valid(self):
        result = check_quality("Some text. " * 50)
        assert result.flag in ("OK", "REVIEW", "REJECT")

    def test_check_scores_complete(self):
        result = check_quality("Some text. " * 50)
        expected_keys = {"semantic", "missing_sections", "broken_sentences", "encoding", "ocr_noise"}
        assert set(result.check_scores.keys()) == expected_keys
