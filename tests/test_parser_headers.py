"""
Defensive tests for the LexiFusionNet judgment parser.

Ensures the parser handles a range of inputs without crashing:
  Case 1 — Clean, well-formed input
  Case 2 — Missing fields (no date, no citations)
  Case 3 — OCR noise (corrupted characters, broken formatting)
  Case 4 — Irregular formatting (extra whitespace, misaligned headers)
  Case 5 — Edge legal formats (pre-1960 vs modern minimal)
"""

import tempfile
from pathlib import Path

import pytest

from src.data.parser import parse_file, ParsedJudgment


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _write_temp_file(content: str, suffix: str = ".txt") -> Path:
    """Write content to a temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8')
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


# ─── Case 1: Clean Input ────────────────────────────────────────────────────

CLEAN_INPUT = """\
State Of Madras vs Champakam Dorairajan on 9 April, 1951
Equivalent citations: 1951 AIR 226, 1951 SCR 525
Author: S.R. Das
Bench: S.R. Das, B.K. Mukherjea, M.C. Mahajan

PETITIONER:
STATE OF MADRAS

RESPONDENT:
SMT. CHAMPAKAM DORAIRAJAN

DATE OF JUDGMENT:
09/04/1951

HEADNOTE:
This case concerns the validity of the Communal Government Order issued by
the State of Madras which reserved seats in educational institutions on the
basis of religion, race, and caste. The Supreme Court held that the order
violated the fundamental rights guaranteed under Article 29(2) of the Constitution.

JUDGMENT:
The appeal is dismissed. The Communal Government Order of the State of Madras is
unconstitutional as it violates Article 29(2) of the Constitution of India.
The right of a citizen not to be discriminated against in matters of admission
to educational institutions maintained by the State or receiving aid out of
State funds is a fundamental right. This order clearly classifies students
on grounds of religion, race, caste and community, which is prohibited under
Article 29(2). The High Court was correct in striking down the order.

The petitioner has failed to demonstrate any compelling state interest that
would justify the classification. The classification has no rational nexus
to the purpose sought to be achieved. Therefore, the petition under
Article 32 of the Constitution is allowed with costs.
"""


class TestCleanInput:
    """Case 1: Parser handles clean, well-formed input correctly."""

    def setup_method(self):
        self.path = _write_temp_file(CLEAN_INPUT)
        self.result = parse_file(self.path, 1951)

    def test_is_valid(self):
        assert self.result.is_valid is True

    def test_title_extracted(self):
        assert "State Of Madras" in self.result.title
        assert "Champakam Dorairajan" in self.result.title

    def test_date_extracted(self):
        assert self.result.date_str == "1951-04-09"
        assert self.result.year == 1951

    def test_citations_extracted(self):
        assert len(self.result.citations) >= 1
        assert any("1951 AIR 226" in c for c in self.result.citations)

    def test_author_extracted(self):
        assert self.result.author == "S.R. Das"

    def test_bench_extracted(self):
        assert len(self.result.bench) >= 2

    def test_body_valid(self):
        assert len(self.result.body) > 200
        assert "unconstitutional" in self.result.body.lower()

    def test_headnote_extracted(self):
        assert self.result.headnote is not None
        assert "Communal Government Order" in self.result.headnote

    def test_quality_score(self):
        assert self.result.quality_score > 0
        assert self.result.quality_flag in ("OK", "REVIEW", "REJECT")

    def test_no_critical_errors(self):
        # "No equivalent citations found" should NOT be in errors for clean input
        critical = [e for e in self.result.parse_errors if "Failed" in e or "crash" in e.lower()]
        assert len(critical) == 0


# ─── Case 2: Missing Fields ─────────────────────────────────────────────────

MISSING_FIELDS_INPUT = """\
Some Party Name vs Another Party

This is a judgment without proper date formatting or citation blocks.
The court hereby orders that the appeal is dismissed. The respondent
is entitled to costs. The lower court's decision is upheld in its entirety.
Additional reasoning is provided below to substantiate the findings
of the lower court which we find to be correct and well-reasoned.
The arguments presented by the appellant do not hold merit and are
accordingly rejected. The ruling of the High Court stands affirmed.
"""


class TestMissingFields:
    """Case 2: Parser handles missing date and citations gracefully."""

    def setup_method(self):
        self.path = _write_temp_file(MISSING_FIELDS_INPUT)
        self.result = parse_file(self.path, 2000)

    def test_does_not_crash(self):
        assert isinstance(self.result, ParsedJudgment)

    def test_fallback_date(self):
        # Should fall back to directory year
        assert "2000" in self.result.date_str

    def test_no_citations(self):
        assert self.result.citations == []

    def test_errors_logged(self):
        assert any("citations" in e.lower() for e in self.result.parse_errors)

    def test_body_extracted(self):
        assert len(self.result.body) > 50

    def test_title_extracted(self):
        assert self.result.title is not None


# ─── Case 3: OCR Noise ──────────────────────────────────────────────────────

OCR_NOISE_INPUT = """\
St�te of Kar�ataka vs Ram�sh Kumar on 15 March, 2005
Equ�valent c�tations: 2005 A�R 445

The c\x00ourt h\x00ereby dismisses the appeal filed by the petitioner.
Th\ufffd\ufffd judgment of the High Court is confirmed. The respondent
is ent\x00itled to costs throughout. The arguments of learned counsel
for the app\ufffdllant have been considered and found to be without
substance. The ev\x00idence on record clearly supports the findings
of the trial c\x00ourt and the High Court. We find no reason to
interfere with the concurrent findings of fact recorded by the
courts bel\ufffdw. The special leave petition is accordingly dismissed.
"""


class TestOCRNoise:
    """Case 3: Parser does not crash on OCR-corrupted text."""

    def setup_method(self):
        self.path = _write_temp_file(OCR_NOISE_INPUT)
        self.result = parse_file(self.path, 2005)

    def test_does_not_crash(self):
        assert isinstance(self.result, ParsedJudgment)

    def test_title_still_extracted(self):
        # Should extract something even with corruption
        assert self.result.title is not None
        assert len(self.result.title) > 0

    def test_date_still_extracted(self):
        assert "2005" in self.result.date_str

    def test_body_exists(self):
        assert len(self.result.body) > 0

    def test_quality_reflects_issues(self):
        # Quality should flag encoding issues
        assert self.result.quality_score < 1.0


# ─── Case 4: Irregular Formatting ───────────────────────────────────────────

IRREGULAR_FORMAT_INPUT = """\
   Union   Of   India   vs    Ram   Lakhan    on   22    November,    1998
  Equivalent citations:    1998 AIR   112   ,  1998 SCC   (3)   445

  Author:    Justice    K.    Ramaswamy
  Bench:    K.    Ramaswamy   ,     S.P.    Bharucha



JUDGMENT:


     The    appeal    is    hereby     dismissed.     The    respondent
shall   be   entitled   to   costs.    The   High   Court   was   correct
in   its   interpretation   of   Section   14   of   the   Limitation   Act,
1963.   The   lower   court's   findings   on   this   point   are   well-
reasoned   and   we   see   no   grounds   for   interference.

The  constitutional  validity  of  the  impugned  provision  has  been
upheld  by  this  Court  in  several  earlier  decisions.  We  do  not  see
any  reason  to  take  a  different  view  in  the  present  case.  The
writ  petition  is  accordingly  dismissed  with  no  order  as  to  costs.
"""


class TestIrregularFormatting:
    """Case 4: Parser handles extra whitespace and misaligned headers."""

    def setup_method(self):
        self.path = _write_temp_file(IRREGULAR_FORMAT_INPUT)
        self.result = parse_file(self.path, 1998)

    def test_does_not_crash(self):
        assert isinstance(self.result, ParsedJudgment)

    def test_date_extracted(self):
        assert "1998" in self.result.date_str

    def test_body_extracted(self):
        assert len(self.result.body) > 100

    def test_is_valid(self):
        # Despite formatting, body should still be usable
        assert self.result.is_valid is True


# ─── Case 5: Edge Legal Formats ─────────────────────────────────────────────

PRE_1960_INPUT = """\
Romesh Thappar vs State Of Madras on 26 May, 1950
Equivalent citations: 1950 AIR 124, 1950 SCR 594

PETITIONER:
ROMESH THAPPAR

RESPONDENT:
THE STATE OF MADRAS

DATE OF JUDGMENT:
26/05/1950

BENCH:
Patanjali Sastri, C.J., Mehr Chand Mahajan, B.K. Mukherjea,
S.R. Das and Vivian Bose, JJ.

CITATION:
1950 AIR 124
1950 SCR 594

ACT:
Constitution of India, Article 19(1)(a)

HEADNOTE:
Freedom of speech and expression includes freedom of the press. The
impugned order banning the entry and circulation of the journal "Cross
Roads" in the State of Madras was held to be an infringement of the
petitioner's fundamental right under Article 19(1)(a). The restriction
could not be justified under Article 19(2) as it existed at the time.

JUDGMENT:
We have heard learned counsel. The petition under Article 32 is allowed.
The impugned order is struck down as unconstitutional. The State of Madras
had no authority to impose such a blanket ban on the circulation of the
journal. The freedom of speech and expression under Article 19(1)(a)
includes the freedom of propagation of ideas, which is ensured by the
freedom of circulation. Liberty of circulation is as essential to that
freedom as the liberty of publication. Indeed, without circulation the
publication would be of little value.
"""

MODERN_MINIMAL_INPUT = """\
Kumar vs State of UP on 10 January, 2023
Author: Justice Chandrachud
Bench: D.Y. Chandrachud, Hima Kohli

This Court has examined the matter and finds no merit in the appeal.
The special leave petition is dismissed. The judgment and order of the
High Court dated 15 November 2022 is affirmed. The interim order, if any,
stands vacated. The parties shall bear their own costs. All pending
applications are disposed of. The Registry will communicate this order
to the concerned High Court forthwith for compliance.
"""


class TestEdgeLegalFormats:
    """Case 5: Both pre-1960 and modern minimal formats are handled."""

    def test_pre_1960_does_not_crash(self):
        path = _write_temp_file(PRE_1960_INPUT)
        result = parse_file(path, 1950)
        assert isinstance(result, ParsedJudgment)
        assert result.is_valid is True

    def test_pre_1960_petitioner_block(self):
        path = _write_temp_file(PRE_1960_INPUT)
        result = parse_file(path, 1950)
        assert "1950" in result.date_str
        assert len(result.body) > 200

    def test_pre_1960_headnote(self):
        path = _write_temp_file(PRE_1960_INPUT)
        result = parse_file(path, 1950)
        assert result.headnote is not None

    def test_modern_minimal_does_not_crash(self):
        path = _write_temp_file(MODERN_MINIMAL_INPUT)
        result = parse_file(path, 2023)
        assert isinstance(result, ParsedJudgment)

    def test_modern_minimal_extracts_metadata(self):
        path = _write_temp_file(MODERN_MINIMAL_INPUT)
        result = parse_file(path, 2023)
        assert "2023" in result.date_str
        assert result.author is not None
        assert len(result.bench) >= 1

    def test_modern_minimal_body(self):
        path = _write_temp_file(MODERN_MINIMAL_INPUT)
        result = parse_file(path, 2023)
        assert len(result.body) > 50
