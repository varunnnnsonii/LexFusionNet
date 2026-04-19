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
                
        # 5. Fallback if absolutely no identity metrics were found -> Use Filename rules (to be done dynamically by graph engine if needed)
        
        # Extract Body Citations from entire file
        body_cites = set()
        for match in RE_BODY_CITATIONS.finditer(text):
            body_cites.add(clean_whitespace(match.group(0)))
            
        # Optional: remove self citations from body citations (to avoid a node pointing to itself unnecessarily)
        body_cites = body_cites - self_cites
        
        return {
            'file_id': Path(filepath).stem,
            'year': Path(filepath).parent.name,
            'self_citations': list(self_cites),
            'cited_cases': list(body_cites)
        }
    except Exception as e:
        return {'file_id': Path(filepath).stem, 'error': str(e)}

def main():
    base_dir = r"c:\Users\vedan\.gemini\lexfusion\archive\supreme_court_judgments_txt"
    output_file = r"c:\Users\vedan\.gemini\lexfusion\citations_network.jsonl"
    
    # 1. Discover all txt files (using pathlib for optimal traversal)
    print("Discovering files...")
    files = list(Path(base_dir).rglob("*.txt"))
    total_files = len(files)
    print(f"Found {total_files} files to process.")
    
    start_time = time.time()
    results_count = 0
    errors_count = 0
    missing_self_cites = 0
    
    print(f"Starting extraction using ThreadPoolExecutor with {os.cpu_count() * 2} workers...")
    # 2. Process concurrently for massive performance
    with open(output_file, 'w', encoding='utf-8') as out_f:
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
            for result in executor.map(process_file, [str(f) for f in files]):
                json.dump(result, out_f)
                out_f.write('\n')
                
                if 'error' in result:
                    errors_count += 1
                else:
                    results_count += 1
                    if not result.get('self_citations'):
                        missing_self_cites += 1
                        
                # Progress logging
                if (results_count + errors_count) % 2500 == 0:
                    print(f"Processed {results_count + errors_count} / {total_files} files ({(results_count + errors_count)/total_files*100:.1f}%)")
                    
    elapsed = time.time() - start_time
    print(f"\n--- Extraction Complete in {elapsed:.2f} seconds ---")
    print(f"Total processed: {results_count}")
    print(f"Errors during processing: {errors_count}")
    print(f"Files requiring fallback filename-identity (no self-citations found): {missing_self_cites} ({missing_self_cites/total_files*100:.1f}%)")
    print(f"Data saved to: {output_file}")

if __name__ == '__main__':
    main()
