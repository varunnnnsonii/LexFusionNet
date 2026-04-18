import os
import re
import random
import sys

# Import the dummy extractor
sys.path.append('/home/vxrun/LexiFusionNet/src/pipeline')
from citation_extractor import CitationExtractor

def test_flaws():
    base_dir = '/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/'
    files_to_check = []
    
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.txt'):
                files_to_check.append(os.path.join(root, file))
                
    files_to_check = random.sample(files_to_check, 500)
    extractor = CitationExtractor()
    
    extracted_count = 0
    expected_heuristics_count = 0
    missed_examples = []
    
    # Generic regex to catch "vs." or "v." references to signify a case citation existence
    v_pattern = re.compile(r'\b(?:v\.|vs\.|vs)\b', re.IGNORECASE)
    
    # Regex for a general generic citation like "[number] [Word] [number]"
    # e.g., 2005 13 SCALE 33, (1998) 8 JT 1
    missed_pattern = re.compile(r'\b\d{4}\b\s*[\(\[]?\d*[\)\]]?\s*(?:SCALE|JT|ILR|SCW|ALL)\s*\d+', re.IGNORECASE)
    
    for filepath in files_to_check:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # We skip the header Equivalent citation line to avoid double counting
                body_content = content[2000:] if len(content) > 3000 else content
                
                extracts = extractor.extract_from_body(body_content)
                extracted_count += len(extracts)
                
                v_matches = len(v_pattern.findall(body_content))
                expected_heuristics_count += v_matches
                
                # Check for explicit misses of other reporters
                for m in missed_pattern.finditer(body_content):
                    missed_examples.append(m.group())
                    
        except Exception as e:
            pass
            
    print(f"Total Files Checked: {len(files_to_check)}")
    print(f"Total Citations Extracted: {extracted_count}")
    print(f"Total Case Name References ('v.' or 'vs.'): {expected_heuristics_count}")
    print(f"\nPotential Missed Extractions (Sample from other reporters): {missed_examples[:10]}")
    
if __name__ == '__main__':
    test_flaws()
