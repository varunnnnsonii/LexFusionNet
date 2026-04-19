"""
Deep citation header analysis across the entire dataset.
Categorizes every file by its citation header structure.
"""
import os
import re
from collections import Counter, defaultdict

base_dir = '/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/'

# Counters
total_files = 0
has_equiv_citations = 0
has_citation_block = 0
has_both = 0
has_neither = 0
has_citator_info = 0

# Per-year breakdown of files with NO citation header
no_citation_by_year = Counter()
total_by_year = Counter()

# Collect samples of files with no citation
no_citation_samples = []

# What do the "no citation" files look like? Collect first 5 lines
no_citation_header_samples = []

for root, _, files in os.walk(base_dir):
    for file in files:
        if not file.endswith('.txt'):
            continue
        filepath = os.path.join(root, file)
        # Extract year from path
        parts = root.split('/')
        year = parts[-1] if parts[-1].isdigit() else 'unknown'
        
        total_files += 1
        total_by_year[year] += 1
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Only need to read the header (first ~1500 chars)
                header = f.read(1500)
            
            has_equiv = bool(re.search(r'Equivalent citations:', header, re.IGNORECASE))
            has_cit = bool(re.search(r'^CITATION:', header, re.MULTILINE))
            has_citator = bool(re.search(r'CITATOR INFO', header, re.IGNORECASE))
            
            if has_equiv:
                has_equiv_citations += 1
            if has_cit:
                has_citation_block += 1
            if has_equiv and has_cit:
                has_both += 1
            if has_citator:
                has_citator_info += 1
            if not has_equiv and not has_cit:
                has_neither += 1
                no_citation_by_year[year] += 1
                if len(no_citation_samples) < 20:
                    no_citation_samples.append(filepath)
                if len(no_citation_header_samples) < 5:
                    # Grab first 10 lines
                    lines = header.split('\n')[:12]
                    no_citation_header_samples.append((filepath, lines))
                    
        except Exception as e:
            pass

print("=" * 70)
print("CITATION HEADER ANALYSIS — FULL DATASET")
print("=" * 70)
print(f"Total files scanned:          {total_files}")
print(f"Has 'Equivalent citations:':  {has_equiv_citations}  ({has_equiv_citations/total_files*100:.1f}%)")
print(f"Has 'CITATION:' block:        {has_citation_block}  ({has_citation_block/total_files*100:.1f}%)")
print(f"Has BOTH:                     {has_both}  ({has_both/total_files*100:.1f}%)")
print(f"Has 'CITATOR INFO':           {has_citator_info}  ({has_citator_info/total_files*100:.1f}%)")
print(f"Has NEITHER (no citation):    {has_neither}  ({has_neither/total_files*100:.1f}%)")
print()

print("=" * 70)
print("NO-CITATION FILES BY YEAR (top 20)")
print("=" * 70)
for year, count in sorted(no_citation_by_year.items(), key=lambda x: -x[1])[:20]:
    total = total_by_year[year]
    pct = count / total * 100
    print(f"  {year}: {count}/{total} files have no citation header ({pct:.0f}%)")

print()
print("=" * 70)
print("SAMPLE HEADERS OF FILES WITH NO CITATION")
print("=" * 70)
for filepath, lines in no_citation_header_samples:
    print(f"\n--- {filepath.split('/')[-1]} ---")
    for line in lines:
        print(f"  {line}")
