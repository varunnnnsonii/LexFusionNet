import json
import re
import os

REPORTERS = r"AIR|SCC|SCR|SCALE|JT|INSC|LLJ|Cr\.?L\.?J\.?|CriLJ|ITR|STC|ELT|SCW|AC|Comp\.?\s*Cas(?:es)?|L\.?Ed\.?|U\.?S\.?|W\.?L\.?R\.?|S\.?C\.?R\.?|S\.?C\.?C\.?|A\.?I\.?R\.?"

def normalize_citation(c):
    c = c.upper()
    c = re.sub(r'[()\[\]]', '', c)
    c = re.sub(r'SUPREME\s*COURT', 'SC', c)
    return ' '.join(c.split()).strip()

def clean_case_name(name):
    # Remove leading "In "
    name = re.sub(r'^In\s+', '', name, flags=re.IGNORECASE)
    # Remove trailing " on"
    name = re.sub(r'\s+on$', '', name, flags=re.IGNORECASE)
    return ' '.join(name.split()).strip()

def main():
    input_file = "/home/vxrun/LexiFusionNet/data/processed/phase1/citations_network.jsonl"
    output_file = "/home/vxrun/LexiFusionNet/data/processed/phase1/citations_network_normalized.jsonl"
    
    print(f"Reading from {input_file}...")
    
    processed = 0
    filtered_self_cites = 0
    filtered_case_names = 0
    
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_file, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            obj = json.loads(line)
            if 'error' in obj:
                f_out.write(json.dumps(obj) + "\n")
                continue
                
            # Normalize self citations
            new_self = set()
            for sc in obj.get('self_citations', []):
                cleaned = normalize_citation(sc)
                if cleaned and len(cleaned) > 6:
                    new_self.add(cleaned)
                else:
                    filtered_self_cites += 1
            
            # Normalize body citations
            new_body = set()
            for bc in obj.get('cited_cases', []):
                cleaned = normalize_citation(bc)
                if cleaned:
                    new_body.add(cleaned)
            
            # Remove self citations from body
            new_body = new_body - new_self
            
            # Clean case names
            new_names = set()
            for cn in obj.get('case_names', []):
                cleaned_name = clean_case_name(cn)
                
                # Check for reporters
                has_reporter = bool(re.search(r'\b(?:' + REPORTERS + r'|ALLINDCAS|MANU|ILR)\b', cleaned_name, re.IGNORECASE))
                if not has_reporter and cleaned_name:
                    new_names.add(cleaned_name)
                else:
                    filtered_case_names += 1
                    
            # Write back
            new_obj = {
                'file_id': obj.get('file_id'),
                'year': obj.get('year'),
                'self_citations': list(new_self),
                'cited_cases': list(new_body),
                'case_names': list(new_names)
            }
            f_out.write(json.dumps(new_obj) + "\n")
            processed += 1
            
            if processed % 5000 == 0:
                print(f"Processed {processed} lines...")

    print(f"\nDone! Processed {processed} files.")
    print(f"Filtered out {filtered_self_cites} bad self-citations.")
    print(f"Filtered out {filtered_case_names} noisy case names.")
    print(f"Saved normalized data to {output_file}")
    
    # Atomic rename if we want to replace original
    os.rename(output_file, input_file)

if __name__ == '__main__':
    main()
