"""
Citation & Statute Normalizer
==============================
The highest-value, highest-risk component (per the architecture doc).

Responsibilities:
  1. Citation normalization — collapse formatting variants to canonical form
  2. Statute normalization — map raw statute strings → (section, act_name, canonical_name)
  3. Act registry — known Act synonyms / abbreviations → full official names

All normalization is deterministic, stateless, and tested against actual data.
"""

import re
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════
# PART 1 — CITATION NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def normalize_citation(raw: str) -> str:
    """
    Normalize a citation string for deduplication and matching.

    Algorithm (from architecture doc §1.2 Stage 2):
      1. Uppercase
      2. Remove brackets: ()[]
      3. Replace SUPREME COURT → SC
      4. Collapse whitespace
      5. Strip
    """
    if not raw:
        return ""
    c = raw.upper()
    c = re.sub(r'[()\[\]]', '', c)
    c = re.sub(r'SUPREME\s*COURT', 'SC', c)
    return ' '.join(c.split())


def extract_reporter(citation_code: str) -> Optional[str]:
    """Extract the reporter abbreviation from a normalized citation code."""
    # Typical: "2006 10 SCC 261" → "SCC"
    # Or: "AIR 2006 SC 975" → "AIR"
    reporters = [
        "ALLINDCAS", "AIR", "SCC", "SCR", "SCALE", "JT", "INSC",
        "LLJ", "CRILJ", "ITR", "STC", "ELT", "SCW",
    ]
    upper = citation_code.upper()
    for r in reporters:
        if r in upper:
            return r
    return None


def extract_citation_year(citation_code: str) -> Optional[int]:
    """Extract the year from a normalized citation code."""
    m = re.search(r'\b((?:19|20)\d{2})\b', citation_code)
    if m:
        return int(m.group(1))
    return None


# ═══════════════════════════════════════════════════════════════════════════
# PART 2 — ACT REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

# Category → official Act name (from architecture doc §4.2 Layer 1)
CATEGORY_TO_ACT = {
    "ipc_sections":        "Indian Penal Code, 1860",
    "bns_sections":        "Bharatiya Nyaya Sanhita, 2023",
    "crpc_sections":       "Code of Criminal Procedure, 1973",
    "bnss_sections":       "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "cpc_sections":        "Code of Civil Procedure, 1908",
    "constitutional_refs": "Constitution of India, 1950",
    "order_rules":         "Code of Civil Procedure, 1908",
}

# Act type classification
ACT_TYPE_MAP = {
    "Indian Penal Code, 1860":                    "penal",
    "Bharatiya Nyaya Sanhita, 2023":              "penal",
    "Code of Criminal Procedure, 1973":           "procedural",
    "Bharatiya Nagarik Suraksha Sanhita, 2023":   "procedural",
    "Code of Civil Procedure, 1908":              "procedural",
    "Constitution of India, 1950":                "constitutional",
}

# Abbreviation → full official name (synonym registry for named_act_sections)
ACT_SYNONYMS = {
    # Criminal
    "IPC":      "Indian Penal Code, 1860",
    "I.P.C.":   "Indian Penal Code, 1860",
    "Indian Penal Code": "Indian Penal Code, 1860",
    "CrPC":     "Code of Criminal Procedure, 1973",
    "Cr.P.C.":  "Code of Criminal Procedure, 1973",
    "Cr. P.C.": "Code of Criminal Procedure, 1973",
    "Code of Criminal Procedure": "Code of Criminal Procedure, 1973",
    "CPC":      "Code of Civil Procedure, 1908",
    "C.P.C.":   "Code of Civil Procedure, 1908",
    "Code of Civil Procedure": "Code of Civil Procedure, 1908",
    "BNS":      "Bharatiya Nyaya Sanhita, 2023",
    "BNSS":     "Bharatiya Nagarik Suraksha Sanhita, 2023",

    # Evidence
    "Evidence Act":        "Indian Evidence Act, 1872",
    "Indian Evidence Act": "Indian Evidence Act, 1872",

    # Constitutional
    "Constitution":         "Constitution of India, 1950",
    "Constitution of India": "Constitution of India, 1950",

    # Specific Acts
    "NDPS Act":     "Narcotic Drugs and Psychotropic Substances Act, 1985",
    "PMLA":         "Prevention of Money Laundering Act, 2002",
    "POCSO":        "Protection of Children from Sexual Offences Act, 2012",
    "POCSO Act":    "Protection of Children from Sexual Offences Act, 2012",
    "NIA Act":      "National Investigation Agency Act, 2008",
    "TADA":         "Terrorist and Disruptive Activities (Prevention) Act, 1987",
    "TADA Act":     "Terrorist and Disruptive Activities (Prevention) Act, 1987",
    "UAPA":         "Unlawful Activities (Prevention) Act, 1967",
    "SEBI Act":     "Securities and Exchange Board of India Act, 1992",
    "SARFAESI":     "Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act, 2002",
    "SARFAESI Act": "Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act, 2002",
    "FEMA":         "Foreign Exchange Management Act, 1999",
    "FERA":         "Foreign Exchange Regulation Act, 1973",
    "IT Act":       "Information Technology Act, 2000",
    "NI Act":       "Negotiable Instruments Act, 1881",
    "PC Act":       "Prevention of Corruption Act, 1988",
    "RPA":          "Representation of the People Act, 1951",
    "Motor Vehicles Act": "Motor Vehicles Act, 1988",
    "Arbitration Act":    "Arbitration and Conciliation Act, 1996",
    "Hindu Marriage Act":  "Hindu Marriage Act, 1955",
    "Transfer of Property Act": "Transfer of Property Act, 1882",
    "Limitation Act":      "Limitation Act, 1963",
    "Registration Act":    "Registration Act, 1908",
    "Companies Act":       "Companies Act, 2013",
    "Companies Act, 1956": "Companies Act, 1956",
    "Income Tax Act":      "Income Tax Act, 1961",
    "Customs Act":         "Customs Act, 1962",
    "Land Acquisition Act": "Land Acquisition Act, 1894",
    "Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act": "Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act, 2013",
    "Industrial Disputes Act": "Industrial Disputes Act, 1947",
    "Workmen Compensation Act": "Workmen's Compensation Act, 1923",
    "Consumer Protection Act":  "Consumer Protection Act, 2019",
    "Specific Relief Act":      "Specific Relief Act, 1963",
    "Arms Act":                 "Arms Act, 1959",
    "Mines Act":                "Mines Act, 1952",
    "Factories Act":            "Factories Act, 1948",
    "Contract Act":             "Indian Contract Act, 1872",
    "Indian Contract Act":      "Indian Contract Act, 1872",
    "Hindu Succession Act":     "Hindu Succession Act, 1956",
    "Dowry Prohibition Act":    "Dowry Prohibition Act, 1961",
    "DV Act":                   "Protection of Women from Domestic Violence Act, 2005",
    "POSH":                     "Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013",
    "MMDR Act":                 "Mines and Minerals (Development and Regulation) Act, 1957",
    "BR Act":                   "Banking Regulation Act, 1949",
}

# Pre-compile lower-case synonym lookup for matching
_ACT_SYNONYM_LOWER = {k.lower(): v for k, v in ACT_SYNONYMS.items()}


def resolve_act_name(raw_act: str) -> str:
    """
    Resolve a raw Act name/abbreviation to its canonical full name.
    Returns the raw string if no match found (creates a new Act).
    """
    if not raw_act:
        return raw_act
    # Exact match
    if raw_act in ACT_SYNONYMS:
        return ACT_SYNONYMS[raw_act]
    # Case-insensitive match
    lower = raw_act.lower().strip()
    if lower in _ACT_SYNONYM_LOWER:
        return _ACT_SYNONYM_LOWER[lower]
    # Strip trailing year and try again
    without_year = re.sub(r',?\s*\d{4}$', '', raw_act).strip()
    if without_year.lower() in _ACT_SYNONYM_LOWER:
        # Re-append the year from the raw string
        year_match = re.search(r'\d{4}$', raw_act)
        resolved = _ACT_SYNONYM_LOWER[without_year.lower()]
        if year_match:
            # Check if resolved already has a year
            if not re.search(r'\d{4}$', resolved):
                resolved = f"{resolved}, {year_match.group()}"
        return resolved
    return raw_act


def classify_act_type(act_name: str) -> str:
    """Classify an Act into a broad category."""
    if act_name in ACT_TYPE_MAP:
        return ACT_TYPE_MAP[act_name]
    lower = act_name.lower()
    if "penal" in lower or "nyaya" in lower or "crime" in lower:
        return "penal"
    if "procedure" in lower or "suraksha" in lower:
        return "procedural"
    if "constitution" in lower:
        return "constitutional"
    return "regulatory"


def extract_act_abbreviation(act_name: str) -> Optional[str]:
    """Get short abbreviation for known Acts."""
    # Reverse lookup
    for abbrev, full_name in ACT_SYNONYMS.items():
        if full_name == act_name and len(abbrev) <= 10:
            return abbrev
    return None


def extract_act_year(act_name: str) -> Optional[int]:
    """Extract year from an Act name."""
    m = re.search(r'(\d{4})$', act_name.strip())
    if m:
        return int(m.group(1))
    return None


# ═══════════════════════════════════════════════════════════════════════════
# PART 3 — STATUTE NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════

# Regex to extract section/article number
_RE_SECTION_NUM = re.compile(
    r'(?:Sections?|Ss?\.)\s+(\d[\w()\-/]*)', re.IGNORECASE
)
_RE_ARTICLE_NUM = re.compile(
    r'(?:Articles?|Arts?\.)\s+(\d[\w()\-/]*)', re.IGNORECASE
)
_RE_ORDER_RULE = re.compile(
    r'Order\s+([IVXLC]+|\d+)\s+Rule\s+(\d+[\w()]*)', re.IGNORECASE
)

# Extract Act name from "Section X of the Some Act, YYYY" patterns
_RE_OF_ACT = re.compile(
    r'of\s+(?:the\s+)?(.+?Act(?:,?\s*\d{4})?)\s*$', re.IGNORECASE
)
_RE_OF_CODE = re.compile(
    r'of\s+(?:the\s+)?(.+?Code(?:\s+of\s+\w+\s+Procedure)?(?:,?\s*\d{4})?)\s*$',
    re.IGNORECASE,
)
_RE_OF_SANHITA = re.compile(
    r'of\s+(?:the\s+)?(.+?Sanhita(?:,?\s*\d{4})?)\s*$', re.IGNORECASE
)
_RE_OF_CONSTITUTION = re.compile(
    r'of\s+(?:the\s+)?Constitution(?:\s+of\s+India)?\s*$', re.IGNORECASE
)

# Trailing abbreviation: "Section 302 IPC", "Section 497 CrPC"
_RE_TRAILING_ABBR = re.compile(
    r'(?:I\.?P\.?C\.?|Cr\.?\s*P\.?\s*C\.?|C\.?\s*P\.?\s*C\.?|BNS|BNSS|'
    r'PMLA|NDPS|POCSO|NIA|TADA|UAPA|SEBI|SARFAESI|FEMA|FERA)\s*$',
    re.IGNORECASE,
)


def extract_section_number(statute_str: str) -> Optional[str]:
    """Extract the section or article number from a statute string."""
    m = _RE_SECTION_NUM.search(statute_str)
    if m:
        return m.group(1).strip()
    m = _RE_ARTICLE_NUM.search(statute_str)
    if m:
        return m.group(1).strip()
    m = _RE_ORDER_RULE.search(statute_str)
    if m:
        return f"Order {m.group(1)} Rule {m.group(2)}"
    return None


def extract_act_from_statute(statute_str: str, category: str) -> str:
    """
    Extract the parent Act name from a statute string.

    Priority:
      1. Category-based routing (ipc_sections → IPC)
      2. "of the <Act>" pattern
      3. Trailing abbreviation (Section 302 IPC)
      4. Unknown → category name as fallback
    """
    # 1. For well-known categories, use the mapping
    if category in CATEGORY_TO_ACT:
        return CATEGORY_TO_ACT[category]

    # 2. "of the <Act/Code/Sanhita/Constitution>" patterns
    for pat in [_RE_OF_ACT, _RE_OF_CODE, _RE_OF_SANHITA]:
        m = pat.search(statute_str)
        if m:
            return resolve_act_name(m.group(1).strip())

    m = _RE_OF_CONSTITUTION.search(statute_str)
    if m:
        return "Constitution of India, 1950"

    # 3. Trailing abbreviation
    m = _RE_TRAILING_ABBR.search(statute_str)
    if m:
        return resolve_act_name(m.group(0).strip())

    # 4. Fallback
    return f"Unknown ({category})"


def canonicalize_statute(
    statute_str: str, category: str
) -> dict:
    """
    Normalize a raw statute string into a canonical form.

    Returns:
        {
            "canonical_name": "Section 302, Indian Penal Code, 1860",
            "category": "ipc_sections",
            "act_name": "Indian Penal Code, 1860",
            "section": "302",
            "raw_text": original string,
        }
    """
    section = extract_section_number(statute_str)
    act_name = extract_act_from_statute(statute_str, category)

    if section and act_name:
        # Determine prefix (Section vs Article vs Order)
        if "constitutional" in category or "article" in statute_str.lower():
            prefix = "Article"
        elif section.startswith("Order"):
            prefix = ""  # Already includes "Order X Rule Y"
        else:
            prefix = "Section"

        if prefix:
            canonical = f"{prefix} {section}, {act_name}"
        else:
            canonical = f"{section}, {act_name}"
    else:
        # Cannot parse — use cleaned original as canonical
        canonical = ' '.join(statute_str.split())

    return {
        "canonical_name": canonical,
        "category": category,
        "act_name": act_name,
        "section": section or "",
        "raw_text": statute_str,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PART 4 — BATCH NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════

# The list-type statute fields to process
STATUTE_LIST_FIELDS = [
    "ipc_sections", "bns_sections", "crpc_sections", "bnss_sections",
    "cpc_sections", "constitutional_refs", "order_rules",
    "named_act_sections", "rw_combinations", "bare_section_lists",
]


def normalize_record_citations(record: dict) -> tuple[list[str], list[str]]:
    """
    Normalize all citation strings in a record.

    Returns:
        (normalized_self_citations, normalized_body_citations)
    """
    self_cites = [
        normalize_citation(c) for c in record.get("self_citations", [])
        if normalize_citation(c)
    ]
    body_cites = [
        normalize_citation(c) for c in record.get("cited_cases", [])
        if normalize_citation(c)
    ]
    return self_cites, body_cites


def normalize_record_statutes(record: dict) -> list[dict]:
    """
    Normalize all statute references in a record into canonical forms.

    Returns list of dicts with canonical_name, category, act_name, section, raw_text.
    Skips raw_act_block and additional_acts (per architecture doc §5.1 Q3).
    """
    statutes_data = record.get("statutes", {})
    results = []
    seen = set()

    for field in STATUTE_LIST_FIELDS:
        entries = statutes_data.get(field, [])
        for raw_str in entries:
            if not raw_str or not raw_str.strip():
                continue
            canon = canonicalize_statute(raw_str, field)
            key = canon["canonical_name"].lower()
            if key not in seen:
                seen.add(key)
                results.append(canon)

    return results
