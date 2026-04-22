import os
import re
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

def clean_whitespace(s):
    return ' '.join(s.split())

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
                cleaned = clean_whitespace(c)
                if cleaned: self_cites.add(cleaned)
                
        # 2. Look for Neutral INSC formatting
        for match in RE_INSC.finditer(head_text):
            self_cites.add(clean_whitespace(match.group(1)))
            
        # 3. Look for archaic 'CITATION:' block
        citation_block_match = RE_CITATION_BLOCK.search(head_text)
        if citation_block_match:
            block = citation_block_match.group(1)
            # Find year + reporter + number in block
            cites = re.findall(rf'((?:19|20)\d{{2}}\s+(?:{REPORTERS})\s+\d+)', block, re.IGNORECASE)
            for c in cites:
                self_cites.add(clean_whitespace(c))
                
        # 4. Fallback for Transitional Era with no headers
        if not self_cites:
            case_no_match = RE_CASE_NO.search(head_text)
            if case_no_match:
                self_cites.add(clean_whitespace("CASE NO: " + case_no_match.group(1)))
        
        # Extract Body Citations from entire file
        body_cites = set()
        for match in RE_BODY_CITATIONS.finditer(text):
            body_cites.add(clean_whitespace(match.group(0)))
            
        # Optional: remove self citations from body citations (to avoid a node pointing to itself unnecessarily)
        body_cites = body_cites - self_cites
        
        # Extract party vs party case names
        case_names = set()
        for match in RE_CASE_NAMES.finditer(text):
            case_names.add(clean_whitespace(match.group(1)))
        
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
    import sys
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir.parent / "archive" / "supreme_court_judgments_txt"
    output_file = script_dir.parent / "citations_network.jsonl"
    
    # --- 1. Load existing to support auto-resume ---
    existing = set()
    if output_file.exists():
        print("Reading existing JSONL to resume...")
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        existing.add(json.loads(line.strip()).get('file_id', ''))
                    except:
                        pass
        print(f"Found {len(existing)} existing records.")

    # 2. Discover all txt files and filter out existing
    print("Discovering files...")
    all_files = list(Path(base_dir).rglob("*.txt"))
    files = [f for f in all_files if f.stem not in existing]
    
    total_files = len(files)
    if total_files == 0:
        print("All files already extracted. Nothing to do!")
        return
        
    print(f"Found {total_files} new files to process (out of {len(all_files)} total).")
    
    start_time = time.time()
    results_count = 0
    errors_count = 0
    missing_self_cites = 0
    
    print(f"Starting extraction using ThreadPoolExecutor with {min(32, os.cpu_count() * 2)} workers...")
    
    # 3. Process concurrently, appending to output file
    with open(output_file, 'a', encoding='utf-8') as out_f:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 2)) as executor:
            for i, result in enumerate(executor.map(process_file, [str(f) for f in files])):
                out_f.write(json.dumps(result, ensure_ascii=False) + '\n')
                
                if 'error' in result:
                    errors_count += 1
                else:
                    results_count += 1
                    if not result.get('self_citations'):
                        missing_self_cites += 1
                        
                # ASCII Progress logging
                if (i + 1) % 100 == 0 or (i + 1) == total_files:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    eta = (total_files - (i + 1)) / rate if rate > 0 else 0
                    pct = (i + 1) * 100 // total_files
                    bar = '#' * (pct // 2) + '-' * (50 - pct // 2)
                    sys.stdout.write(f"\r  [{bar}] {pct}%  {i+1}/{total_files}  "
                                     f"({rate:.0f}/s  ETA {eta:.0f}s)    ")
                    sys.stdout.flush()
                    
    elapsed = time.time() - start_time
    print(f"\n\n--- Extraction Complete in {elapsed:.2f} seconds ---")
    print(f"Newly processed: {results_count}")
    print(f"Errors during processing: {errors_count}")
    print(f"Files requiring fallback filename-identity: {missing_self_cites}")

if __name__ == '__main__':
    main()
