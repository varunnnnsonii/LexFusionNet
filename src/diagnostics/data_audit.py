"""
Data Audit Script for LexiFusionNet — Phase 0.

Performs comprehensive diagnostics on the raw judgment dataset:
- File count and size distribution per year
- Corrupt/empty file detection
- Duplicate detection (body text hash)
- Header parsing accuracy sampling
- Structural pattern analysis across eras
- Quality scoring and auto-flagging (semantic, encoding, OCR noise)

Output: artifacts/data_audit_report.json
"""

import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import get_config
from src.data.parser import parse_file
from src.diagnostics.quality_checker import check_quality


def compute_body_hash(text: str) -> str:
    """Hash the first 500 chars of body text for dedup."""
    normalized = text[:500].strip().lower()
    return hashlib.md5(normalized.encode()).hexdigest()


def run_audit():
    """Run the full data audit and write report."""
    cfg = get_config()
    raw_dir = cfg.paths.raw_data
    report_path = cfg.paths.audit_report

    print(f"Starting data audit on: {raw_dir}")
    print(f"Report will be written to: {report_path}")
    print()

    # ── 1. File Inventory ────────────────────────────────────────────────────
    print("═" * 60)
    print("1. FILE INVENTORY")
    print("═" * 60)

    year_stats = {}
    all_files = []
    total_size = 0
    sizes = []

    year_dirs = sorted(raw_dir.iterdir())
    for year_dir in year_dirs:
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
        except ValueError:
            continue

        files = sorted(year_dir.glob('*.txt'))
        year_sizes = [f.stat().st_size for f in files]

        year_stats[str(year)] = {
            'count': len(files),
            'total_bytes': sum(year_sizes),
            'avg_bytes': int(sum(year_sizes) / len(year_sizes)) if year_sizes else 0,
            'min_bytes': min(year_sizes) if year_sizes else 0,
            'max_bytes': max(year_sizes) if year_sizes else 0,
        }

        for f, s in zip(files, year_sizes):
            all_files.append((f, year, s))
            total_size += s
            sizes.append(s)

    print(f"  Total files: {len(all_files)}")
    print(f"  Total size:  {total_size / 1024 / 1024:.1f} MB")
    print(f"  Years:       {min(year_stats.keys())} – {max(year_stats.keys())}")
    if sizes:
        print(f"  Avg size:    {sum(sizes) / len(sizes) / 1024:.1f} KB")
        print(f"  Min size:    {min(sizes)} bytes")
        print(f"  Max size:    {max(sizes) / 1024 / 1024:.1f} MB")

    # Size distribution buckets
    size_buckets = Counter()
    for s in sizes:
        if s < 500:
            size_buckets['< 500 B (corrupt)'] += 1
        elif s < 1024:
            size_buckets['500 B – 1 KB'] += 1
        elif s < 10 * 1024:
            size_buckets['1 – 10 KB'] += 1
        elif s < 50 * 1024:
            size_buckets['10 – 50 KB'] += 1
        elif s < 100 * 1024:
            size_buckets['50 – 100 KB'] += 1
        elif s < 500 * 1024:
            size_buckets['100 – 500 KB'] += 1
        else:
            size_buckets['> 500 KB'] += 1

    print("\n  Size distribution:")
    for bucket, count in sorted(size_buckets.items()):
        print(f"    {bucket}: {count}")

    # ── 2. Corrupt/Empty File Detection ──────────────────────────────────────
    print(f"\n{'═' * 60}")
    print("2. CORRUPT / EMPTY FILES")
    print("═" * 60)

    corrupt_files = [(f, y, s) for f, y, s in all_files if s < 500]
    print(f"  Files < 500 bytes: {len(corrupt_files)}")
    for f, y, s in corrupt_files:
        print(f"    [{y}] {f.name} ({s} bytes)")

    # ── 3. Duplicate Detection ───────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print("3. DUPLICATE DETECTION")
    print("═" * 60)

    body_hashes = defaultdict(list)
    print("  Scanning for duplicates (first 500 chars of body)...")

    for file_path, year, fsize in all_files:
        if fsize < 500:
            continue
        try:
            text = file_path.read_text(encoding='utf-8', errors='replace')
            # Use a simple approach: hash the text after header (skip first 5 lines)
            lines = text.split('\n')
            body_start = '\n'.join(lines[5:50])  # Lines 5-50
            h = compute_body_hash(body_start)
            body_hashes[h].append(str(file_path))
        except Exception:
            pass

    duplicates = {h: paths for h, paths in body_hashes.items() if len(paths) > 1}
    print(f"  Duplicate groups found: {len(duplicates)}")
    for h, paths in list(duplicates.items())[:5]:
        print(f"    Hash {h[:8]}...: {len(paths)} files")
        for p in paths[:3]:
            print(f"      - {Path(p).name}")

    # ── 4. Header Parsing Accuracy ───────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print("4. HEADER PARSING ACCURACY (sample)")
    print("═" * 60)

    sample_size = min(cfg.audit.sample_size, len(all_files))
    sample = random.sample(all_files, sample_size)

    parse_results = {
        'title_extracted': 0,
        'date_extracted': 0,
        'citations_extracted': 0,
        'author_extracted': 0,
        'bench_extracted': 0,
        'headnote_extracted': 0,
        'acts_extracted': 0,
        'body_valid': 0,
        'total_sampled': sample_size,
    }

    all_parse_errors = []
    for file_path, year, fsize in sample:
        parsed = parse_file(file_path, year)

        if parsed.title and parsed.title != file_path.stem.replace('_', ' '):
            parse_results['title_extracted'] += 1
        if not parsed.date_str.endswith('01-01'):
            parse_results['date_extracted'] += 1
        if parsed.citations:
            parse_results['citations_extracted'] += 1
        if parsed.author:
            parse_results['author_extracted'] += 1
        if parsed.bench:
            parse_results['bench_extracted'] += 1
        if parsed.headnote:
            parse_results['headnote_extracted'] += 1
        if parsed.acts:
            parse_results['acts_extracted'] += 1
        if parsed.is_valid and len(parsed.body) > 200:
            parse_results['body_valid'] += 1

        if parsed.parse_errors:
            all_parse_errors.append({
                'file': str(file_path),
                'errors': parsed.parse_errors
            })

    print(f"  Sample size: {sample_size}")
    for field, count in parse_results.items():
        if field == 'total_sampled':
            continue
        pct = count / sample_size * 100
        status = "✓" if pct >= 90 else ("⚠" if pct >= 70 else "✗")
        print(f"  {status} {field}: {count}/{sample_size} ({pct:.1f}%)")

    print(f"\n  Files with parse errors: {len(all_parse_errors)}")
    for err in all_parse_errors[:5]:
        print(f"    {Path(err['file']).name}: {err['errors']}")

    # ── 5. Structural Patterns by Era ────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print("5. STRUCTURAL PATTERNS BY ERA")
    print("═" * 60)

    era_patterns = {}
    for decade_start in range(1950, 2030, 10):
        decade_files = [
            (f, y, s) for f, y, s in all_files
            if decade_start <= y < decade_start + 10 and s >= 500
        ]
        if not decade_files:
            continue

        # Sample up to 10 from this decade
        decade_sample = random.sample(decade_files, min(10, len(decade_files)))
        patterns = Counter()

        for file_path, year, fsize in decade_sample:
            try:
                text = file_path.read_text(encoding='utf-8', errors='replace')
                if 'HEADNOTE' in text:
                    patterns['HEADNOTE'] += 1
                if 'CITATOR INFO' in text:
                    patterns['CITATOR_INFO'] += 1
                if 'ACT:' in text[:5000]:
                    patterns['ACT_BLOCK'] += 1
                if 'PETITIONER:' in text:
                    patterns['PETITIONER_BLOCK'] += 1
                if 'indiankanoon.org' in text:
                    patterns['INDIANKANOON_MARKERS'] += 1
                if 'Equivalent citations' in text[:1000]:
                    patterns['EQUIV_CITATIONS'] += 1
            except Exception:
                pass

        decade_label = f"{decade_start}s"
        era_patterns[decade_label] = {
            'sample_size': len(decade_sample),
            'total_files': len(decade_files),
            'patterns': dict(patterns)
        }
        print(f"  {decade_label} ({len(decade_files)} files, sampled {len(decade_sample)}):")
        for p, c in sorted(patterns.items()):
            print(f"    {p}: {c}/{len(decade_sample)}")

    # ── 6. Quality Scoring & Auto-Flagging ───────────────────────────────────
    print(f"\n{'═' * 60}")
    print("6. QUALITY SCORING & AUTO-FLAGGING (sample)")
    print("═" * 60)

    quality_sample_size = min(200, len(all_files))
    quality_sample = random.sample(all_files, quality_sample_size)

    quality_counts = {"OK": 0, "REVIEW": 0, "REJECT": 0}
    rejected_files = []
    review_files = []
    quality_details = []

    for file_path, year, fsize in quality_sample:
        try:
            text = file_path.read_text(encoding='utf-8', errors='replace')
            qr = check_quality(text)

            quality_counts[qr.flag] += 1

            if qr.flag == "REJECT":
                rejected_files.append({
                    'file': str(file_path),
                    'year': year,
                    'score': qr.score,
                    'issues': qr.issues,
                    'check_scores': qr.check_scores,
                })
            elif qr.flag == "REVIEW":
                review_files.append({
                    'file': str(file_path),
                    'year': year,
                    'score': qr.score,
                    'issues': qr.issues,
                    'check_scores': qr.check_scores,
                })

            quality_details.append({
                'file': str(file_path),
                'score': qr.score,
                'flag': qr.flag,
            })

        except Exception as e:
            rejected_files.append({
                'file': str(file_path),
                'year': year,
                'score': 0.0,
                'issues': [f"Failed to read: {e}"],
                'check_scores': {},
            })
            quality_counts["REJECT"] += 1

    print(f"  Quality sample size: {quality_sample_size}")
    print(f"  OK:     {quality_counts['OK']} ({quality_counts['OK']/quality_sample_size*100:.1f}%)")
    print(f"  REVIEW: {quality_counts['REVIEW']} ({quality_counts['REVIEW']/quality_sample_size*100:.1f}%)")
    print(f"  REJECT: {quality_counts['REJECT']} ({quality_counts['REJECT']/quality_sample_size*100:.1f}%)")

    if rejected_files:
        print(f"\n  Rejected files ({len(rejected_files)}):")
        for rf in rejected_files[:10]:
            print(f"    {Path(rf['file']).name}: score={rf['score']:.3f} — {rf['issues'][:2]}")

    if review_files:
        print(f"\n  Review-needed files ({len(review_files)}):")
        for rv in review_files[:10]:
            print(f"    {Path(rv['file']).name}: score={rv['score']:.3f} — {rv['issues'][:2]}")

    # ── Build Final Report ───────────────────────────────────────────────────
    report = {
        'summary': {
            'total_files': len(all_files),
            'total_size_mb': round(total_size / 1024 / 1024, 1),
            'year_range': f"{min(year_stats.keys())}–{max(year_stats.keys())}",
            'corrupt_files': len(corrupt_files),
            'duplicate_groups': len(duplicates),
        },
        'year_stats': year_stats,
        'size_distribution': dict(size_buckets),
        'corrupt_files': [
            {'file': str(f), 'year': y, 'size': s}
            for f, y, s in corrupt_files
        ],
        'duplicates': {
            h[:16]: paths for h, paths in list(duplicates.items())[:20]
        },
        'parse_accuracy': parse_results,
        'parse_errors_sample': all_parse_errors[:20],
        'era_patterns': era_patterns,
        'quality_summary': {
            'sample_size': quality_sample_size,
            'counts': quality_counts,
            'ok_percent': round(quality_counts['OK'] / quality_sample_size * 100, 1),
            'review_percent': round(quality_counts['REVIEW'] / quality_sample_size * 100, 1),
            'reject_percent': round(quality_counts['REJECT'] / quality_sample_size * 100, 1),
        },
        'rejected_files': rejected_files[:50],
        'review_files': review_files[:50],
    }

    # Write report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'═' * 60}")
    print(f"AUDIT COMPLETE — Report written to: {report_path}")
    print("═" * 60)

    return report


if __name__ == '__main__':
    random.seed(42)
    run_audit()
