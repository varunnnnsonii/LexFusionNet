#!/usr/bin/env python3
"""
ACT / STATUTE / TOPIC EXTRACTION — REALITY ANALYSIS
Analyzes real dataset to validate pipeline design assumptions.
READ-ONLY: Does not modify any project files.
"""

import os
import re
import random
import json
from pathlib import Path
from collections import Counter, defaultdict

random.seed(42)

DATA_DIR = Path("data/input/supreme_court_judgments_txt")

# ─── STEP 1: SMART SAMPLING ────────────────────────────────────────────
print("=" * 80)
print("STEP 1: SMART SAMPLING")
print("=" * 80)

all_files = sorted(DATA_DIR.rglob("*.txt"))
total_files = len(all_files)
print(f"Total files in dataset: {total_files}")

# Get file sizes for edge case selection
file_sizes = [(f, f.stat().st_size) for f in all_files]
file_sizes.sort(key=lambda x: x[1])

# 300 random files (global random)
random_sample = random.sample(all_files, min(300, total_files))

# 25 smallest files
smallest = [f for f, _ in file_sizes[:25]]

# 25 largest files
largest = [f for f, _ in file_sizes[-25:]]

# Combine and deduplicate
sample_set = set(random_sample) | set(smallest) | set(largest)
sample_files = sorted(sample_set)
print(f"Sample size: {len(sample_files)} files")
print(f"  - Random: {len(random_sample)}")
print(f"  - Smallest 25: sizes {file_sizes[0][1]}-{file_sizes[24][1]} bytes")
print(f"  - Largest 25: sizes {file_sizes[-25][1]}-{file_sizes[-1][1]} bytes")

# Size distribution of full dataset
sizes_all = [s for _, s in file_sizes]
print(f"\nDataset size stats:")
print(f"  Min: {min(sizes_all)} bytes")
print(f"  Max: {max(sizes_all)} bytes")
print(f"  Median: {sorted(sizes_all)[len(sizes_all)//2]} bytes")
print(f"  Mean: {sum(sizes_all)//len(sizes_all)} bytes")
print(f"  <500 bytes: {sum(1 for s in sizes_all if s < 500)}")
print(f"  <1KB: {sum(1 for s in sizes_all if s < 1024)}")
print(f"  <5KB: {sum(1 for s in sizes_all if s < 5120)}")
print(f"  >500KB: {sum(1 for s in sizes_all if s > 512000)}")
print(f"  >1MB: {sum(1 for s in sizes_all if s > 1048576)}")

# ─── PATTERNS ──────────────────────────────────────────────────────────

# ACT-like section patterns
ACT_PATTERNS = [
    (r'^ACT:\s*$', 'ACT: (standalone)'),
    (r'^ACT:\s*.+', 'ACT: <content>'),
    (r'^HEADNOTE:\s*$', 'HEADNOTE: (standalone)'),
    (r'^HEADNOTE:', 'HEADNOTE: (with content)'),
    (r'^PETITIONER:', 'PETITIONER:'),
    (r'^RESPONDENT:', 'RESPONDENT:'),
    (r'CITATOR INFO', 'CITATOR INFO'),
    (r'^DATE OF JUDGMENT', 'DATE OF JUDGMENT'),
    (r'^JUDGMENT:', 'JUDGMENT:'),
    (r'^JUDGMENT\s*$', 'JUDGMENT (standalone)'),
    (r'^ORDER\s*$', 'ORDER (standalone)'),
    (r'^Equivalent citations?:', 'Equivalent citations:'),
    (r'^Author:', 'Author:'),
    (r'^Bench:', 'Bench:'),
]

# Statute patterns — comprehensive
STATUTE_PATTERNS = [
    (r'[Ss]ection\s+\d+[A-Za-z]?(?:\s*\(\d+\))?', 'section X'),
    (r'[Ss]ec\.\s*\d+', 'Sec. X'),
    (r'[Ss]\.\s*\d+', 'S. X'),
    (r'[Ss]s?\.\s*\d+', 'Ss. X'),
    (r'u/s\.?\s*\d+', 'u/s X'),
    (r'[Aa]rticle\s+\d+[A-Za-z]?(?:\s*\(\d+\))?', 'Article X'),
    (r'[Aa]rt\.\s*\d+', 'Art. X'),
    (r'[Rr]ule\s+\d+', 'Rule X'),
    (r'[Oo]rder\s+[IVXLCDM]+', 'Order (Roman)'),
    (r'[Oo]rder\s+\d+', 'Order X'),
    (r'[Cc]lause\s+\(\w+\)', 'Clause (x)'),
    (r'[Cc]lause\s+\d+', 'Clause X'),
    # OCR corruption patterns
    (r'[Ss]ect[il1]on\s+\d+', 'sectlon (OCR)'),
    (r'5ec\w*\s+\d+', '5ec (OCR)'),
    (r'[Ss]ectio[nm]\s+\d+', 'sectio(n/m) (OCR)'),
]

# Named Acts pattern
NAMED_ACT_RE = re.compile(
    r'(?:the\s+)?(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act,?\s+\d{4}',
    re.MULTILINE
)

NAMED_CODE_RE = re.compile(
    r'(?:the\s+)?(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Code,?\s+\d{4}',
    re.MULTILINE
)

# Common Acts (known short forms)
COMMON_ACT_ABBREVS = [
    (r'\bI\.?P\.?C\.?\b', 'IPC'),
    (r'\bCr\.?\s*P\.?\s*C\.?\b', 'CrPC'),
    (r'\bC\.?\s*P\.?\s*C\.?\b', 'CPC'),
    (r'\bI\.?T\.?\s*Act\b', 'IT Act'),
    (r'\bCPC\b', 'CPC'),
    (r'\bIPC\b', 'IPC'),
    (r'\bCrPC\b', 'CrPC'),
]

# Doctrine / legal principle patterns
DOCTRINE_PATTERNS = [
    r'doctrine\s+of\s+\w+',
    r'res\s+judicata',
    r'stare\s+decisis',
    r'ratio\s+decidendi',
    r'obiter\s+dict[ua]m?',
    r'ejusdem\s+generis',
    r'noscitur\s+a\s+sociis',
    r'ultra\s+vires',
    r'mens\s+rea',
    r'actus\s+reus',
    r'audi\s+alteram\s+partem',
    r'natural\s+justice',
    r'due\s+process',
    r'fundamental\s+rights?',
    r'basic\s+structure',
    r'harmonious\s+construction',
    r'reasonable\s+classification',
    r'principle\s+of\s+\w+',
    r'test\s+of\s+\w+',
    r'right\s+to\s+\w+',
    r'burden\s+of\s+proof',
    r'preponderance\s+of\s+\w+',
    r'beyond\s+reasonable\s+doubt',
    r'locus\s+standi',
    r'prima\s+facie',
    r'mala\s+fide',
    r'bona\s+fide',
    r'suo\s+motu',
    r'per\s+incuriam',
    r'pro\s+rata',
    r'mutatis\s+mutandis',
    r'pari\s+passu',
    r'colourable\s+exercise',
    r'wednesbury\s+unreasonableness',
    r'proportionality',
    r'severability',
    r'prospective\s+overruling',
]

# Pipeline's statute regex (from parser.py line 73-78)
PIPELINE_STATUTE_RE = re.compile(
    r'(?:Section|Article|Rule|Order)\s+\d+[A-Za-z]?(?:\(\d+\))?'
    r'|(?:the\s+)?[\w\s]+Act,?\s+\d{4}'
    r'|(?:the\s+)?[\w\s]+Code,?\s+\d{4}',
    re.IGNORECASE
)


# ─── STEP 2-4: ANALYZE EACH FILE ──────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 2-4: STRUCTURE DETECTION, CLASSIFICATION, PATTERN DISCOVERY")
print("=" * 80)

results = []
act_header_variations = Counter()
statute_pattern_hits = Counter()
statute_examples = defaultdict(list)  # pattern_name -> [example strings]
doctrine_hits = Counter()
doctrine_examples = defaultdict(list)
named_acts_found = Counter()
named_codes_found = Counter()
act_abbreviation_hits = Counter()
classification_counts = Counter()

# For pipeline regex comparison
pipeline_hits = 0
pipeline_missed = 0
pipeline_false_positives_examples = []

# Classification logic for each file
for i, fpath in enumerate(sample_files):
    if i % 50 == 0:
        print(f"  Processing {i}/{len(sample_files)}...")

    try:
        text = fpath.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        results.append({
            'file': str(fpath),
            'size': 0,
            'classification': 'ERROR',
            'error': str(e),
        })
        continue

    fsize = len(text)
    year = int(fpath.parent.name)

    # --- Detect ACT-like structures ---
    has_act_section = False
    has_headnote = False
    has_petitioner = False
    has_citator = False
    has_judgment_marker = False
    has_equiv_citations = False
    has_author = False
    has_bench = False
    has_date_of_judgment = False
    has_order = False

    for pattern, label in ACT_PATTERNS:
        matches = re.findall(pattern, text[:5000], re.MULTILINE)
        if matches:
            act_header_variations[label] += 1
            if 'ACT' in label:
                has_act_section = True
            if 'HEADNOTE' in label:
                has_headnote = True
            if 'PETITIONER' in label:
                has_petitioner = True
            if 'CITATOR' in label:
                has_citator = True
            if 'JUDGMENT' in label:
                has_judgment_marker = True
            if 'Equivalent' in label:
                has_equiv_citations = True
            if 'Author' in label:
                has_author = True
            if 'Bench' in label:
                has_bench = True
            if 'DATE OF' in label:
                has_date_of_judgment = True
            if 'ORDER' in label:
                has_order = True

    # --- Detect ACT block content ---
    act_block_content = None
    act_block_type = None  # single-line, multi-line, noisy

    # Look for ACT: block
    act_match = re.search(r'^ACT:\s*(.*)$', text, re.MULTILINE)
    if act_match:
        act_content = act_match.group(1).strip()
        if act_content:
            # Single-line ACT: with content on same line
            act_block_content = act_content
            act_block_type = 'single-line'
        else:
            # Multi-line: content follows on next lines
            # Find content until next section header
            act_start = act_match.end()
            next_section = re.search(
                r'^(?:HEADNOTE|JUDGMENT|CITATOR|PETITIONER|RESPONDENT|DATE):',
                text[act_start:act_start + 3000],
                re.MULTILINE
            )
            if next_section:
                act_content = text[act_start:act_start + next_section.start()].strip()
            else:
                act_content = text[act_start:act_start + 1000].strip()
            act_block_content = act_content
            if len(act_content) > 200:
                act_block_type = 'multi-line'
            elif len(act_content) < 10:
                act_block_type = 'noisy/empty'
            else:
                act_block_type = 'single-line'

    # --- Detect statute mentions ---
    statute_count = 0
    for pattern, label in STATUTE_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            statute_pattern_hits[label] += 1
            statute_count += len(matches)
            # Store up to 3 examples
            if len(statute_examples[label]) < 5:
                for m in matches[:3]:
                    if m not in statute_examples[label]:
                        statute_examples[label].append(m)

    # Named acts
    named_acts = NAMED_ACT_RE.findall(text)
    for act in named_acts:
        named_acts_found[act.strip()] += 1

    named_codes = NAMED_CODE_RE.findall(text)
    for code in named_codes:
        named_codes_found[code.strip()] += 1

    # Act abbreviations
    for pattern, label in COMMON_ACT_ABBREVS:
        if re.search(pattern, text):
            act_abbreviation_hits[label] += 1

    # --- Pipeline regex comparison ---
    pipeline_matches = PIPELINE_STATUTE_RE.findall(text)
    all_real_matches = []
    for pattern, label in STATUTE_PATTERNS:
        all_real_matches.extend(re.findall(pattern, text))

    if pipeline_matches:
        pipeline_hits += 1
    if all_real_matches and not pipeline_matches:
        pipeline_missed += 1

    # --- Detect doctrine patterns ---
    doctrine_count = 0
    for pattern in DOCTRINE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            for m in matches:
                doctrine_hits[m.lower().strip()] += 1
                doctrine_count += len(matches)
                if len(doctrine_examples[m.lower().strip()]) < 2:
                    # Get surrounding context
                    idx = text.lower().find(m.lower())
                    if idx >= 0:
                        context = text[max(0, idx-50):idx+len(m)+50].replace('\n', ' ')
                        doctrine_examples[m.lower().strip()].append(context)

    # --- Classify file ---
    is_pre2000_format = has_petitioner or has_date_of_judgment or has_citator
    has_statute = statute_count > 0
    has_doctrine = doctrine_count > 0

    if has_act_section and has_statute and has_doctrine:
        classification = 'Mixed'
    elif has_act_section and has_statute:
        classification = 'Mixed'
    elif has_act_section:
        classification = 'ACT-based'
    elif has_statute and not has_doctrine:
        classification = 'Statute-based'
    elif has_doctrine and not has_statute:
        classification = 'Doctrine-only'
    elif has_statute and has_doctrine:
        classification = 'Mixed'
    elif is_pre2000_format or has_equiv_citations or has_judgment_marker:
        classification = 'Unstructured'  # Has some structure but no act/statute/doctrine
    else:
        classification = 'Unstructured'

    classification_counts[classification] += 1

    results.append({
        'file': str(fpath),
        'year': year,
        'size': fsize,
        'classification': classification,
        'has_act_section': has_act_section,
        'act_block_type': act_block_type,
        'act_block_content_preview': (act_block_content[:200] if act_block_content else None),
        'has_headnote': has_headnote,
        'has_petitioner': has_petitioner,
        'has_citator': has_citator,
        'has_judgment_marker': has_judgment_marker,
        'has_equiv_citations': has_equiv_citations,
        'has_author': has_author,
        'has_bench': has_bench,
        'has_date_of_judgment': has_date_of_judgment,
        'is_pre2000_format': is_pre2000_format,
        'statute_count': statute_count,
        'doctrine_count': doctrine_count,
        'pipeline_regex_matches': len(pipeline_matches) if pipeline_matches else 0,
    })

print(f"  Completed processing {len(sample_files)} files.")

# ─── STEP 2 OUTPUT ────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("STRUCTURE DETECTION RESULTS")
print("=" * 80)

print("\nHeader/Section markers found (across sample):")
for label, count in act_header_variations.most_common():
    pct = count / len(sample_files) * 100
    print(f"  {label:35s}: {count:4d} files ({pct:5.1f}%)")

# ─── STEP 3 OUTPUT ────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("CLASSIFICATION DISTRIBUTION")
print("=" * 80)

for cls, count in classification_counts.most_common():
    pct = count / len(sample_files) * 100
    print(f"  {cls:20s}: {count:4d} files ({pct:5.1f}%)")

# Pre-2000 vs Post-2000
pre2000 = sum(1 for r in results if r.get('year', 2000) < 2000)
post2000 = sum(1 for r in results if r.get('year', 2000) >= 2000)
print(f"\n  Pre-2000 files in sample: {pre2000}")
print(f"  Post-2000 files in sample: {post2000}")

pre2000_with_act = sum(1 for r in results if r.get('year', 2000) < 2000 and r.get('has_act_section'))
post2000_with_act = sum(1 for r in results if r.get('year', 2000) >= 2000 and r.get('has_act_section'))
print(f"  Pre-2000 with ACT section: {pre2000_with_act} ({pre2000_with_act/max(pre2000,1)*100:.1f}%)")
print(f"  Post-2000 with ACT section: {post2000_with_act} ({post2000_with_act/max(post2000,1)*100:.1f}%)")

# ─── STEP 4 OUTPUT: ACT PATTERNS ──────────────────────────────────────
print("\n" + "=" * 80)
print("ACT PATTERN REALITY")
print("=" * 80)

act_files = [r for r in results if r.get('has_act_section')]
print(f"\nFiles with ACT: section: {len(act_files)} / {len(sample_files)} ({len(act_files)/len(sample_files)*100:.1f}%)")

act_types = Counter()
for r in act_files:
    act_types[r.get('act_block_type', 'unknown')] += 1

print("\nACT block types:")
for t, c in act_types.most_common():
    print(f"  {t}: {c}")

print("\nSample ACT block contents:")
shown = 0
for r in results:
    if r.get('act_block_content_preview') and shown < 10:
        print(f"\n  --- {Path(r['file']).name} (year={r['year']}, type={r['act_block_type']}) ---")
        print(f"  {r['act_block_content_preview'][:300]}")
        shown += 1

# ─── STEP 4 OUTPUT: STATUTE PATTERNS ──────────────────────────────────
print("\n" + "=" * 80)
print("STATUTE PATTERN REALITY")
print("=" * 80)

print("\nStatute pattern frequency (across sample files):")
for label, count in statute_pattern_hits.most_common():
    pct = count / len(sample_files) * 100
    print(f"  {label:25s}: {count:4d} files ({pct:5.1f}%)")

print("\nStatute pattern examples:")
for label, examples in sorted(statute_examples.items()):
    print(f"\n  {label}:")
    for ex in examples[:3]:
        print(f"    \"{ex}\"")

print("\nTop 30 Named Acts mentioned:")
for act, count in named_acts_found.most_common(30):
    print(f"  {count:3d}x  {act}")

print("\nTop 15 Named Codes mentioned:")
for code, count in named_codes_found.most_common(15):
    print(f"  {count:3d}x  {code}")

print("\nAct abbreviation usage:")
for abbr, count in act_abbreviation_hits.most_common():
    pct = count / len(sample_files) * 100
    print(f"  {abbr:10s}: {count:4d} files ({pct:5.1f}%)")

# ─── STEP 4 OUTPUT: DOCTRINE PATTERNS ─────────────────────────────────
print("\n" + "=" * 80)
print("DOCTRINE PATTERN REALITY")
print("=" * 80)

files_with_doctrine = sum(1 for r in results if r.get('doctrine_count', 0) > 0)
print(f"\nFiles with doctrine-like language: {files_with_doctrine} / {len(sample_files)} ({files_with_doctrine/len(sample_files)*100:.1f}%)")

print("\nTop 40 doctrine/legal phrases:")
for phrase, count in doctrine_hits.most_common(40):
    print(f"  {count:3d}x  {phrase}")

# ─── STEP 5: VALIDATE PIPELINE CLAIMS ─────────────────────────────────
print("\n" + "=" * 80)
print("STEP 5: PIPELINE CLAIM VALIDATION")
print("=" * 80)

# CLAIM A: ACT exists and is reliable
print("\n--- CLAIM A: ACT exists and is reliable ---")
act_pct = len(act_files) / len(sample_files) * 100
clean_acts = sum(1 for r in act_files if r.get('act_block_type') in ('single-line', 'multi-line'))
clean_pct = clean_acts / max(len(act_files), 1) * 100
print(f"  Files with ACT section: {len(act_files)}/{len(sample_files)} ({act_pct:.1f}%)")
print(f"  Clean/usable ACT blocks: {clean_acts}/{len(act_files)} ({clean_pct:.1f}%)")
if act_pct < 30:
    print(f"  ⚠️  VERDICT: ACT section is NOT a reliable primary source. Only {act_pct:.1f}% of files have it.")
elif act_pct < 60:
    print(f"  ⚠️  VERDICT: ACT section exists in a minority. Usable but needs fallback.")
else:
    print(f"  ✅ VERDICT: ACT section is present in majority. Viable extraction source.")

# CLAIM B: Statute regex is sufficient
print("\n--- CLAIM B: Pipeline statute regex is sufficient ---")
files_with_statutes = sum(1 for r in results if r.get('statute_count', 0) > 0)
files_pipeline_caught = sum(1 for r in results if r.get('pipeline_regex_matches', 0) > 0)
pct_with_statutes = files_with_statutes / len(sample_files) * 100
pct_pipeline = files_pipeline_caught / len(sample_files) * 100
# Files where our broader regex found things but pipeline didn't
missed_by_pipeline = sum(1 for r in results
                         if r.get('statute_count', 0) > 0 and r.get('pipeline_regex_matches', 0) == 0)
print(f"  Files with ANY statute reference: {files_with_statutes}/{len(sample_files)} ({pct_with_statutes:.1f}%)")
print(f"  Files caught by pipeline regex: {files_pipeline_caught}/{len(sample_files)} ({pct_pipeline:.1f}%)")
print(f"  Files MISSED by pipeline regex: {missed_by_pipeline}")
print(f"  Pipeline misses patterns: u/s, s., Sec., abbreviated forms, OCR corruptions")

# Check what pipeline misses
if missed_by_pipeline > 0:
    print(f"\n  Examples of files missed by pipeline regex:")
    shown = 0
    for r in results:
        if r.get('statute_count', 0) > 0 and r.get('pipeline_regex_matches', 0) == 0 and shown < 5:
            print(f"    {Path(r['file']).name}: {r['statute_count']} statutes found by broader regex, 0 by pipeline")
            shown += 1

# CLAIM C: Doctrine cases exist
print("\n--- CLAIM C: Doctrine cases exist ---")
doctrine_only = sum(1 for r in results if r.get('classification') == 'Doctrine-only')
mixed_with_doctrine = sum(1 for r in results if r.get('doctrine_count', 0) > 0)
print(f"  Files with doctrine language: {mixed_with_doctrine}/{len(sample_files)} ({mixed_with_doctrine/len(sample_files)*100:.1f}%)")
print(f"  Doctrine-ONLY files (no statutes): {doctrine_only}/{len(sample_files)}")
print(f"  Are they standalone? {'Yes' if doctrine_only > 5 else 'Not really — mostly mixed with statutes'}")

# CLAIM D: Fallback NLP needed
print("\n--- CLAIM D: Fallback NLP needed ---")
unstructured = sum(1 for r in results if r.get('classification') == 'Unstructured')
unstructured_pct = unstructured / len(sample_files) * 100
print(f"  Fully unstructured files: {unstructured}/{len(sample_files)} ({unstructured_pct:.1f}%)")
print(f"  These files have no ACT section, no detectable statutes, no doctrine keywords")

# Check if unstructured files have ANY useful content
unstructured_with_content = 0
for r in results:
    if r.get('classification') == 'Unstructured' and r.get('size', 0) > 2000:
        unstructured_with_content += 1
print(f"  Unstructured files >2KB (likely real judgments): {unstructured_with_content}")
if unstructured_pct > 10:
    print(f"  ⚠️  VERDICT: {unstructured_pct:.1f}% require fallback NLP. This is significant.")
else:
    print(f"  ✅ VERDICT: Only {unstructured_pct:.1f}% need fallback. Manageable.")

# ─── STEP 6: FAILURE ANALYSIS ─────────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 6: FAILURE ANALYSIS")
print("=" * 80)

# Case 1: ACT missing but topics exist in body
no_act_but_statutes = sum(1 for r in results
                          if not r.get('has_act_section') and r.get('statute_count', 0) > 5)
print(f"\n  ACT missing but statutes in body: {no_act_but_statutes} files")

# Case 2: Sections present but broken format
ocr_corrupted = statute_pattern_hits.get('sectlon (OCR)', 0) + \
                statute_pattern_hits.get('5ec (OCR)', 0) + \
                statute_pattern_hits.get('sectio(n/m) (OCR)', 0)
print(f"  Files with OCR-corrupted statute refs: {ocr_corrupted}")

# Case 3: Very small files
tiny_files = sum(1 for r in results if r.get('size', 0) < 500)
small_files = sum(1 for r in results if r.get('size', 0) < 1024)
print(f"  Files <500 bytes (likely stubs): {tiny_files}")
print(f"  Files <1KB: {small_files}")

# Case 4: Giant files (might overwhelm regex)
giant_files = sum(1 for r in results if r.get('size', 0) > 500000)
print(f"  Files >500KB (may overwhelm regex): {giant_files}")

# Case 5: Files with no header markers at all
no_markers = sum(1 for r in results
                 if not any([
                     r.get('has_act_section'),
                     r.get('has_headnote'),
                     r.get('has_petitioner'),
                     r.get('has_citator'),
                     r.get('has_judgment_marker'),
                     r.get('has_equiv_citations'),
                     r.get('has_author'),
                     r.get('has_bench'),
                     r.get('has_date_of_judgment'),
                 ]))
print(f"  Files with NO standard header markers: {no_markers}")

# Show some examples of problematic files
print("\n  Example failure cases:")
shown = 0
for r in results:
    if r.get('classification') == 'Unstructured' and r.get('size', 0) > 5000 and shown < 5:
        print(f"\n  --- {Path(r['file']).name} ---")
        print(f"    Size: {r['size']} bytes, Year: {r.get('year')}")
        print(f"    Has: act={r.get('has_act_section')}, headnote={r.get('has_headnote')}, "
              f"petitioner={r.get('has_petitioner')}, equiv_citations={r.get('has_equiv_citations')}")
        # Read first 500 chars to show structure
        try:
            text = Path(r['file']).read_text(encoding='utf-8', errors='replace')
            print(f"    First 300 chars:")
            print(f"    {text[:300].replace(chr(10), ' | ')}")
        except:
            pass
        shown += 1

# ─── ADDITIONAL: Year-based analysis ──────────────────────────────────
print("\n" + "=" * 80)
print("YEAR-BASED PATTERN ANALYSIS")
print("=" * 80)

decade_stats = defaultdict(lambda: {'total': 0, 'act': 0, 'statute': 0, 'doctrine': 0,
                                     'pre2000_format': 0, 'equiv_citations': 0})
for r in results:
    y = r.get('year', 0)
    decade = (y // 10) * 10
    decade_stats[decade]['total'] += 1
    if r.get('has_act_section'):
        decade_stats[decade]['act'] += 1
    if r.get('statute_count', 0) > 0:
        decade_stats[decade]['statute'] += 1
    if r.get('doctrine_count', 0) > 0:
        decade_stats[decade]['doctrine'] += 1
    if r.get('is_pre2000_format'):
        decade_stats[decade]['pre2000_format'] += 1
    if r.get('has_equiv_citations'):
        decade_stats[decade]['equiv_citations'] += 1

print(f"\n{'Decade':>8s} | {'Total':>5s} | {'ACT':>5s} | {'Statute':>7s} | {'Doctrine':>8s} | {'Pre2K fmt':>9s} | {'Equiv Cit':>9s}")
print("-" * 72)
for decade in sorted(decade_stats.keys()):
    s = decade_stats[decade]
    print(f"{decade:>8d} | {s['total']:>5d} | {s['act']:>5d} | {s['statute']:>7d} | {s['doctrine']:>8d} | {s['pre2000_format']:>9d} | {s['equiv_citations']:>9d}")

# ─── STEP 7: REALITY SCORE ────────────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 7: REALITY SCORES")
print("=" * 80)

# Compute scores
act_reliability = min(10, int(act_pct / 10))
if clean_pct < 50:
    act_reliability = max(1, act_reliability - 2)

statute_reliability = min(10, int(pct_with_statutes / 10))
if missed_by_pipeline > len(sample_files) * 0.05:
    statute_reliability = max(1, statute_reliability - 2)

doctrine_reliability = min(10, int(mixed_with_doctrine / len(sample_files) * 10))

# Overall = weighted average
overall = int((act_reliability * 0.3 + statute_reliability * 0.4 + doctrine_reliability * 0.3))

print(f"\n  ACT extraction reliability:      {act_reliability} / 10")
print(f"  Statute extraction reliability:  {statute_reliability} / 10")
print(f"  Doctrine detection reliability:  {doctrine_reliability} / 10")
print(f"  Overall pipeline readiness:      {overall} / 10")

# ─── SAVE STRUCTURED RESULTS ──────────────────────────────────────────
print("\n" + "=" * 80)
print("Saving detailed results...")
print("=" * 80)

# Save raw JSON for further analysis
output = {
    'sample_size': len(sample_files),
    'classification_counts': dict(classification_counts),
    'act_header_variations': dict(act_header_variations),
    'statute_pattern_hits': dict(statute_pattern_hits),
    'top_named_acts': dict(named_acts_found.most_common(50)),
    'top_named_codes': dict(named_codes_found.most_common(20)),
    'act_abbreviation_hits': dict(act_abbreviation_hits),
    'top_doctrine_phrases': dict(doctrine_hits.most_common(50)),
    'decade_stats': {str(k): v for k, v in decade_stats.items()},
    'scores': {
        'act_reliability': act_reliability,
        'statute_reliability': statute_reliability,
        'doctrine_reliability': doctrine_reliability,
        'overall': overall,
    },
    'pipeline_validation': {
        'files_with_any_statute': files_with_statutes,
        'files_caught_by_pipeline': files_pipeline_caught,
        'files_missed_by_pipeline': missed_by_pipeline,
    },
}

json_path = Path("artifacts/phase1/act_extraction/analysis_raw_data2.json")
json_path.parent.mkdir(parents=True, exist_ok=True)
with open(json_path, 'w') as f:
    json.dump(output, f, indent=2)
print(f"  Saved raw data to {json_path}")

print("\n✅ ANALYSIS COMPLETE")
