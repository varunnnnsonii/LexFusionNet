import os
import re
import sys
import json
import logging
import concurrent.futures
from pathlib import Path
import time

logging.basicConfig(level=logging.INFO, format='%(message)s')

# Compiled regexes for self-citations (from headers)
RE_EQUIV_CITATIONS = re.compile(r'Equivalent citations:\s*([^\n]+)', re.IGNORECASE)
RE_CASE_NO = re.compile(r'CASE NO\.:\s*\n([^\n]+)', re.IGNORECASE)
RE_INSC = re.compile(r'\b((?:19|20)\d{2}\s+INSC\s+\d+)\b', re.IGNORECASE)
RE_CITATION_BLOCK = re.compile(r'CITATION:\s*\n(.*?)(?:\n\s*CITATOR INFO|\n\s*ACT|\n\s*JUDGMENT|\n\s*\n)', re.DOTALL | re.IGNORECASE)

REPORTERS = r"AIR|SCC|SCR|SCALE|JT|INSC|LLJ|Cr\.?L\.?J\.?|CriLJ|ITR|STC|ELT|SCW|AC|Comp\.?\s*Cas(?:es)?|L\.?Ed\.?|U\.?S\.?|W\.?L\.?R\.?|S\.?C\.?R\.?|S\.?C\.?C\.?|A\.?I\.?R\.?"

# Highly comprehensive and robust compiled regex for all body citations
RE_BODY_CITATIONS = re.compile(
    # 1. Year first (unbracketed): 1950 AIR 27, 2010 (10) SCC 141, 1999 3 SCR 255
    rf'\b(?:19|20)\d{{2}}\s+(?:\(\d+\)\s+|\d+\s+)?(?:{REPORTERS})\s+(?:\w+\s+)?\d+\b|'
    # 2. Year first (bracketed): (2010) 10 SCC 141, [1950] 1 SCR 88
    rf'[\(\[](?:19|20)\d{{2}}[\)\]]\s+(?:\d+\s+)?(?:{REPORTERS})\s+(?:\w+\s+)?\d+\b|'
    # 3. Reporter first: AIR 1950 SC 27, SCC 2010 SC 141, JT 2010 (2) SC 123
    rf'\b(?:{REPORTERS})\s+(?:19|20)\d{{2}}\s+(?:\(\d+\)\s+)?(?:SC|SUPREME COURT)?\s*\d+\b',
    re.IGNORECASE
)

# Regex for Party vs. Party Case Names (e.g. Maneka Gandhi v. Union of India)
RE_CASE_NAMES = re.compile(
    r'\b([A-Z][\w\.\&\'\-]*?(?:\s+(?:[A-Z][\w\.\&\'\-]*?|of|the|and|in|on|&)){0,7}\s+v(?:s)?\.?\s+[A-Z][\w\.\&\'\-]*?(?:\s+(?:[A-Z][\w\.\&\'\-]*?|of|the|and|in|on|&)){0,7})\b'
)

def normalize_citation(c):
    c = c.upper()
    c = re.sub(r'[()\[\]]', '', c)
    c = re.sub(r'SUPREME\s*COURT', 'SC', c)
    return ' '.join(c.split())

def clean_case_name(name):
    name = re.sub(r'^In\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+on$', '', name, flags=re.IGNORECASE)
    return ' '.join(name.split())

def process_file(filepath):
    """
    Process a single file to extract self-citations and body-citations.
    Designed to fail gracefully and return a dict mapping for JSONL output.
    """
    try:
        # Fast read, ignoring malformed chars
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
            
        # Target only the first 2000 chars for headers to save regex time
        head_text = text[:2000]
        
        self_cites = set()
        
        # 1. Look for 'Equivalent citations: ...'
        equiv_match = RE_EQUIV_CITATIONS.search(head_text)
        if equiv_match:
            # May be comma separated: "1950 AIR 27, 1950 SCR 88"
            for c in equiv_match.group(1).split(','):
                cleaned = normalize_citation(c)
                if cleaned and len(cleaned) > 6: self_cites.add(cleaned)
                
        # 2. Look for Neutral INSC formatting
        for match in RE_INSC.finditer(head_text):
            cleaned = normalize_citation(match.group(1))
            if cleaned and len(cleaned) > 6: self_cites.add(cleaned)
            
        # 3. Look for archaic 'CITATION:' block
        citation_block_match = RE_CITATION_BLOCK.search(head_text)
        if citation_block_match:
            block = citation_block_match.group(1)
            # Find year + reporter + number in block
            cites = re.findall(rf'((?:19|20)\d{{2}}\s+(?:{REPORTERS})\s+\d+)', block, re.IGNORECASE)
            for c in cites:
                cleaned = normalize_citation(c)
                if cleaned and len(cleaned) > 6: self_cites.add(cleaned)
                
        # 4. Fallback for Transitional Era with no headers
        if not self_cites:
            case_no_match = RE_CASE_NO.search(head_text)
            if case_no_match:
                cleaned = normalize_citation("CASE NO: " + case_no_match.group(1))
                if cleaned and len(cleaned) > 6: self_cites.add(cleaned)
        
        # Extract Body Citations from entire file
        body_cites = set()
        for match in RE_BODY_CITATIONS.finditer(text):
            body_cites.add(normalize_citation(match.group(0)))
            
        # Optional: remove self citations from body citations (to avoid a node pointing to itself unnecessarily)
        body_cites = body_cites - self_cites
        
        # Extract party vs party case names
        case_names = set()
        for match in RE_CASE_NAMES.finditer(text):
            cn = clean_case_name(match.group(1))
            has_reporter = bool(re.search(r'\b(?:' + REPORTERS + r'|ALLINDCAS|MANU|ILR)\b', cn, re.IGNORECASE))
            if not has_reporter and cn:
                case_names.add(cn)
        
        return {
            'file_id': Path(filepath).stem,
            'year': Path(filepath).parent.name,
            'self_citations': list(self_cites),
            'cited_cases': list(body_cites),
            'case_names': list(case_names)
        }
    except Exception as e:
        return {'file_id': Path(filepath).stem, 'error': str(e)}

def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[2]
    base_dir = project_root / "data" / "input" / "supreme_court_judgments_txt"
    output_file = project_root / "data" / "processed" / "phase1" / "citations_network.jsonl"
    # 1. Discover all txt files (using pathlib for optimal traversal)
    print("Discovering files...")
    files = list(Path(base_dir).rglob("*.txt"))
    total_files = len(files)
    print(f"Found {total_files} files to process.")
    
    start_time = time.time()
    results_count = 0
    errors_count = 0
    missing_self_cites = 0
    
    print(f"Starting extraction using ThreadPoolExecutor with {min(32, os.cpu_count() * 2)} workers...")
    # 2. Process concurrently for massive performance
    with open(output_file, 'w', encoding='utf-8') as out_f:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 2)) as executor:


            for i, result in enumerate(executor.map(process_file, [str(f) for f in files])):
                json.dump(result, out_f)
                out_f.write('\n')
                
                if 'error' in result:
                    errors_count += 1
                else:
                    results_count += 1
                    if not result.get('self_citations'):
                        missing_self_cites += 1

                # ✅ Advanced Progress Bar (from your first script)
                if (i + 1) % 100 == 0 or (i + 1) == total_files:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    eta = (total_files - (i + 1)) / rate if rate > 0 else 0
                    pct = (i + 1) * 100 // total_files
                    bar = '#' * (pct // 2) + '-' * (50 - pct // 2)

                    sys.stdout.write(
                        f"\r  [{bar}] {pct}%  {i+1}/{total_files}  "
                        f"({rate:.0f}/s  ETA {eta:.0f}s)    "
                    )
                    sys.stdout.flush()
                                
    elapsed = time.time() - start_time
    print(f"\n\n--- Extraction Complete in {elapsed:.2f} seconds ---")
    print(f"Total processed: {results_count}")
    print(f"Errors during processing: {errors_count}")
    print(f"Files requiring fallback filename-identity (no self-citations found): {missing_self_cites} ({(missing_self_cites / total_files * 100) if total_files else 0:.1f}%)")
    print(f"Data saved to: {output_file}")

if __name__ == '__main__':
    main()