import os
import re
from collections import Counter
import random

def get_citation_types():
    base_dir = '/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/'
    citation_reporters = Counter()
    
    # We will look for anything that looks like a reporter in the equivalent citations line
    # Format usually is: 1951 AIR, 9 1950 SCR 792, AIR 1951 SUPREME COURT 9
    # or CITATION: 1951 AIR 9
    
    files_to_check = []
    
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.txt'):
                files_to_check.append(os.path.join(root, file))
                
    # Check a sample to save time
    if len(files_to_check) > 5000:
        files_to_check = random.sample(files_to_check, 5000)
        
    reporter_pattern = re.compile(r'[A-Za-z\s]+')
    
    for filepath in files_to_check:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(2048) # read header
                
                # Find Equivalent citations block
                equiv_match = re.search(r'Equivalent citations:\s*(.*?)\n', content, re.IGNORECASE)
                citation_text = ""
                if equiv_match:
                    citation_text = equiv_match.group(1)
                else:
                    cit_match = re.search(r'CITATION:\s*(.*?)\n', content, re.IGNORECASE)
                    if cit_match:
                        citation_text = cit_match.group(1)
                        
                if citation_text:
                    # Break by comma
                    cits = [c.strip() for c in citation_text.split(',')]
                    for c in cits:
                        # Extract the letters (the reporter)
                        # Example: 1950 SCR 792 -> SCR, 2011 (3) SCC 23 -> SCC, AIR 1951 SC 9 -> AIR SC
                        words = c.split()
                        reporters_in_cit = [w.strip('()[]:.,') for w in words if w.strip('()[]:.,').isalpha() and len(w.strip('()[]:.,')) >= 2]
                        if reporters_in_cit:
                            # Join them back, e.g. "AIR SC" or "SCC Cri"
                            # but mostly we care about the main reporter (like SCC, AIR, SCR, SCALE, JT)
                            # let's just add all alphabetic words that are usually uppercase
                            for rep in reporters_in_cit:
                                rep_upper = rep.upper()
                                if rep_upper not in ['THE', 'IN', 'OF', 'ON', 'NO', 'VOL', 'PT']:
                                    citation_reporters[rep_upper] += 1
                                    
        except Exception as e:
            pass
            
    print("Top Citation Reporter Types Found:")
    for rep, count in citation_reporters.most_common(30):
        print(f"{rep}: {count} occurrences")

if __name__ == '__main__':
    get_citation_types()
