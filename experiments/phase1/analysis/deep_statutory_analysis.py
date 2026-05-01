"""
Deep Statutory Format Analysis Script
--------------------------------------
Scans the Supreme Court corpus to identify and quantify ALL different
formatting patterns used for IPC sections and legislative Act references.

Outputs a comprehensive JSON report with:
- Every unique format template found
- Frequency counts per template
- Top IPC sections cited
- Top Acts referenced
- Era-wise breakdown
"""

import os
import re
import json
import random
import collections
from pathlib import Path

# ---------------------------------------------------------------------------
# MASTER REGEX BANK — covers every observed archetype across 1950-2024
# ---------------------------------------------------------------------------

# IPC SECTION PATTERNS (all observed variations)
IPC_PATTERNS = [
    # 1. "Section 302 IPC" / "Section 302/498-A IPC" / "Section 302 read with 34 IPC"
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/,\s]+?(?:read\s+with\s+(?:Sections?\s+)?[\d\w\(\)\-/,\s]+?)?\s*(?:of\s+(?:the\s+)?)?I\.?P\.?C\.?)\b', re.IGNORECASE),
    # 2. "Section 302 of the Indian Penal Code" (full name)
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/,\s]+?of\s+(?:the\s+)?Indian\s+Penal\s+Code(?:,?\s*\d{4})?)\b', re.IGNORECASE),
    # 3. Abbreviated: "s. 302 IPC" / "S. 302 IPC" / "s. 48 of the IPC"
    re.compile(r'\b([Ss]\.\s*[\d\w\(\)\-/]+\s+(?:of\s+(?:the\s+)?)?I\.?P\.?C\.?)\b'),
    # 4. Plural abbreviated: "ss. 79, 78" (seen in older judgments)
    re.compile(r'\b(ss\.\s*[\d\w\(\)\-/,\s]+?\s+(?:of\s+(?:the\s+)?)?I\.?P\.?C\.?)\b', re.IGNORECASE),
    # 5. "Section 304 Part II of the IPC"
    re.compile(r'\b(Sections?\s+\d[\w\-]*\s+Part\s+(?:I{1,3}|IV|V)\s+(?:of\s+(?:the\s+)?)?I\.?P\.?C\.?)\b', re.IGNORECASE),
]

# CrPC PATTERNS (Code of Criminal Procedure)
CRPC_PATTERNS = [
    # "Section 482 Cr.P.C." / "Section 125 CrPC" / "Section 160 of Cr.P.C"
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/,\s]+?(?:read\s+with\s+(?:Sections?\s+)?[\d\w\(\)\-/,\s]+?)?\s*(?:of\s+(?:the\s+)?)?Cr\.?\s*P\.?\s*C\.?)\b', re.IGNORECASE),
    # "Section 482 of the Code of Criminal Procedure"
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/,\s]+?of\s+(?:the\s+)?Code\s+of\s+Criminal\s+Procedure(?:,?\s*\d{4})?)\b', re.IGNORECASE),
    # Abbreviated: "s. 48 of the Code of Civil Procedure"
    re.compile(r'\b([Ss]\.\s*[\d\w\(\)\-/]+\s+(?:of\s+(?:the\s+)?)?Cr\.?\s*P\.?\s*C\.?)\b'),
]

# CPC PATTERNS (Code of Civil Procedure)
CPC_PATTERNS = [
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/,\s]+?(?:of\s+(?:the\s+)?)?C\.?\s*P\.?\s*C\.?)\b', re.IGNORECASE),
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/,\s]+?of\s+(?:the\s+)?Code\s+of\s+Civil\s+Procedure(?:,?\s*\d{4})?)\b', re.IGNORECASE),
    re.compile(r'\b([Ss]\.\s*[\d\w\(\)\-/]+\s+(?:of\s+(?:the\s+)?)?C\.?\s*P\.?\s*C\.?)\b'),
]

# GENERIC ACT PATTERNS (captures ANY "Section X of the Y Act, YYYY")
GENERIC_ACT_PATTERNS = [
    # "Section 30 of the Securities Exchange Board of India Act, 1992"
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/]+(?:\s*(?:read\s+with|r/w)\s+(?:Sections?\s+)?[\d\w\(\)\-/]+)?\s+of\s+(?:the\s+)?[A-Z][\w\.\'\s]*?Act(?:,?\s*\d{4})?)\b'),
    # Abbreviated: "s. 38 of the Act" / "ss. 4(2)(a) and 5"
    re.compile(r'\b([Ss]s?\.\s*[\d\w\(\)\-/,\s]+?of\s+(?:the\s+)?[A-Z][\w\.\'\s]*?Act(?:,?\s*\d{4})?)\b'),
    # "under Section 50 of PMLA" (acronym Acts)
    re.compile(r'\b(Sections?\s+[\d\w\(\)\-/]+\s+(?:of\s+(?:the\s+)?)?(?:PMLA|NDPS|POCSO|NIA|IT|FERA|FEMA|TADA|UAPA|SEBI|SARFAESI|DV|POSH))\b', re.IGNORECASE),
    # "sub-Section (1) of Section 127C of the Act"
    re.compile(r'\b(sub-?[Ss]ections?\s*\([\d]+\)\s+of\s+Sections?\s+[\d\w]+\s+of\s+(?:the\s+)?(?:[A-Z][\w\.\'\s]*?)?Act(?:,?\s*\d{4})?)\b', re.IGNORECASE),
]

# CONSTITUTIONAL ARTICLE PATTERNS
CONSTITUTION_PATTERNS = [
    re.compile(r'\b(Articles?\s+[\d\w\(\)\-/,\s]+?of\s+(?:the\s+)?Constitution(?:\s+of\s+India)?)\b', re.IGNORECASE),
    re.compile(r'\b(Art(?:s)?\.\s*[\d\w\(\)\-/,\s]+?of\s+(?:the\s+)?Constitution)\b', re.IGNORECASE),
]


def clean(s):
    return ' '.join(s.split())


def classify_format(text):
    """Returns a simplified format template from the raw text."""
    t = text.strip()
    # Normalize section numbers to placeholder
    t = re.sub(r'\d[\d\w\(\)\-/,]*', 'NUM', t)
    # Collapse whitespace
    t = ' '.join(t.split())
    return t


def process_file(filepath, year):
    """Extract all statutory mentions from a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    except Exception:
        return None

    results = {
        'ipc': [], 'crpc': [], 'cpc': [],
        'generic_acts': [], 'constitution': []
    }

    for pat in IPC_PATTERNS:
        for m in pat.finditer(text):
            results['ipc'].append(clean(m.group(1)))

    for pat in CRPC_PATTERNS:
        for m in pat.finditer(text):
            results['crpc'].append(clean(m.group(1)))

    for pat in CPC_PATTERNS:
        for m in pat.finditer(text):
            results['cpc'].append(clean(m.group(1)))

    for pat in GENERIC_ACT_PATTERNS:
        for m in pat.finditer(text):
            results['generic_acts'].append(clean(m.group(1)))

    for pat in CONSTITUTION_PATTERNS:
        for m in pat.finditer(text):
            results['constitution'].append(clean(m.group(1)))

    return results


def main():
    base_dir = Path(__file__).resolve().parent.parent / "archive" / "supreme_court_judgments_txt"

    # Collect ALL files grouped by decade
    all_files = []
    for year_dir in sorted(base_dir.iterdir()):
        if year_dir.is_dir() and year_dir.name.isdigit():
            for f in year_dir.glob("*.txt"):
                all_files.append((str(f), year_dir.name))

    print(f"Total files in corpus: {len(all_files)}")

    # Sample ~3000 files uniformly across the corpus for speed
    sample_size = min(3000, len(all_files))
    sampled = random.sample(all_files, sample_size)
    print(f"Sampling {sample_size} files for deep analysis...")

    # Counters
    ipc_formats = collections.Counter()
    crpc_formats = collections.Counter()
    cpc_formats = collections.Counter()
    act_formats = collections.Counter()
    constitution_formats = collections.Counter()

    ipc_sections = collections.Counter()
    crpc_sections = collections.Counter()
    act_names = collections.Counter()
    constitution_articles = collections.Counter()

    era_distribution = collections.Counter()
    files_with_ipc = 0
    files_with_acts = 0
    files_with_constitution = 0

    for i, (filepath, year) in enumerate(sampled):
        results = process_file(filepath, year)
        if results is None:
            continue

        decade = f"{year[:3]}0s"

        if results['ipc']:
            files_with_ipc += 1
            for mention in results['ipc']:
                ipc_formats[classify_format(mention)] += 1
                ipc_sections[mention] += 1
                era_distribution[f"IPC_{decade}"] += 1

        if results['crpc']:
            for mention in results['crpc']:
                crpc_formats[classify_format(mention)] += 1
                crpc_sections[mention] += 1

        if results['cpc']:
            for mention in results['cpc']:
                cpc_formats[classify_format(mention)] += 1

        if results['generic_acts']:
            files_with_acts += 1
            for mention in results['generic_acts']:
                act_formats[classify_format(mention)] += 1
                # Extract Act name
                act_match = re.search(r'of\s+(?:the\s+)?(.+)', mention, re.IGNORECASE)
                if act_match:
                    act_names[clean(act_match.group(1))] += 1

        if results['constitution']:
            files_with_constitution += 1
            for mention in results['constitution']:
                constitution_formats[classify_format(mention)] += 1
                constitution_articles[mention] += 1

        if (i + 1) % 500 == 0:
            print(f"Processed {i + 1} / {sample_size} files...")

    # Build report
    report = {
        "sample_size": sample_size,
        "total_corpus_size": len(all_files),
        "coverage": {
            "files_with_ipc_mentions": files_with_ipc,
            "files_with_act_mentions": files_with_acts,
            "files_with_constitution_mentions": files_with_constitution,
            "pct_with_ipc": round(files_with_ipc / sample_size * 100, 1),
            "pct_with_acts": round(files_with_acts / sample_size * 100, 1),
            "pct_with_constitution": round(files_with_constitution / sample_size * 100, 1),
        },
        "ipc_format_templates": dict(ipc_formats.most_common(30)),
        "crpc_format_templates": dict(crpc_formats.most_common(20)),
        "cpc_format_templates": dict(cpc_formats.most_common(20)),
        "generic_act_format_templates": dict(act_formats.most_common(30)),
        "constitution_format_templates": dict(constitution_formats.most_common(20)),
        "top_25_ipc_sections": ipc_sections.most_common(25),
        "top_25_crpc_sections": crpc_sections.most_common(25),
        "top_25_acts_referenced": act_names.most_common(25),
        "top_25_constitution_articles": constitution_articles.most_common(25),
        "era_wise_ipc_distribution": dict(era_distribution.most_common()),
    }

    output_path = Path(__file__).resolve().parent.parent / "statutory_analysis_report.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n--- Deep Statutory Analysis Complete ---")
    print(f"Files with IPC mentions: {files_with_ipc}/{sample_size} ({report['coverage']['pct_with_ipc']}%)")
    print(f"Files with Act mentions: {files_with_acts}/{sample_size} ({report['coverage']['pct_with_acts']}%)")
    print(f"Files with Constitution mentions: {files_with_constitution}/{sample_size} ({report['coverage']['pct_with_constitution']}%)")
    print(f"Unique IPC format templates found: {len(ipc_formats)}")
    print(f"Unique Act format templates found: {len(act_formats)}")
    print(f"Report saved to: {output_path}")


if __name__ == '__main__':
    main()
