"""
Comprehensive Statutory Extraction Pipeline v2
================================================
Sequential processing, safe regex, per-file progress.
Removes old ipc_mentions/act_mentions and adds 10 categorized columns.
"""

import os, re, json, sys, time
from pathlib import Path

# ── helpers ──────────────────────────────────────────────────────────────────

def clean(s):
    return ' '.join(s.split())

def dedup(lst):
    seen = set()
    out = []
    for x in lst:
        k = x.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x.strip())
    return out

def find_all(pattern, text):
    return dedup([clean(m.group(0)) for m in pattern.finditer(text)])

# ── SAFE REGEX PATTERNS ─────────────────────────────────────────────────────
# RULE: No [charset]*? or [charset]+? where charset includes \s.
#       Use bounded word patterns {0,N} instead.
# ─────────────────────────────────────────────────────────────────────────────

# --- 1. IPC (Indian Penal Code) ---
RE_IPC = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'(?:\s+(?:read\s+with|r/w)\s+(?:Section\s+)?\d[\w\(\)\-/]*)?'
    r'\s+(?:of\s+(?:the\s+)?)?I\.?P\.?C\.?\b', re.I)

RE_IPC_FULL = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+of\s+(?:the\s+)?Indian\s+Penal\s+Code(?:,?\s*\d{4})?\b', re.I)

RE_IPC_ABBR = re.compile(
    r'\b[Ss]s?\.\s*\d[\w\(\)\-/]*'
    r'(?:\s*[,/and]+\s*\d[\w\(\)\-/]*)*'
    r'\s+(?:of\s+(?:the\s+)?)?I\.?P\.?C\.?\b')

RE_IPC_PART = re.compile(
    r'\bSection\s+\d[\w\-]*\s+Part\s+(?:I{1,3}|IV|V)'
    r'\s+(?:of\s+(?:the\s+)?)?I\.?P\.?C\.?\b', re.I)

# --- 2. BNS (Bharatiya Nyaya Sanhita) ---
RE_BNS = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+(?:of\s+(?:the\s+)?)?(?:BNS|Bharatiya\s+Nyaya\s+Sanhita(?:,?\s*\d{4})?)\b', re.I)

# --- 3. CrPC (Code of Criminal Procedure) ---
RE_CRPC = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+(?:of\s+(?:the\s+)?)?Cr\.?\s*P\.?\s*C\.?\b', re.I)

RE_CRPC_FULL = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+of\s+(?:the\s+)?Code\s+of\s+Criminal\s+Procedure(?:,?\s*\d{4})?\b', re.I)

RE_CRPC_ABBR = re.compile(
    r'\b[Ss]s?\.\s*\d[\w\(\)\-/]*'
    r'(?:\s*[,/and]+\s*\d[\w\(\)\-/]*)*'
    r'\s+(?:of\s+(?:the\s+)?)?Cr\.?\s*P\.?\s*C\.?\b')

# --- 4. BNSS (Bharatiya Nagarik Suraksha Sanhita) ---
RE_BNSS = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+(?:of\s+(?:the\s+)?)?(?:BNSS|Bharatiya\s+Nagarik\s+Suraksha\s+Sanhita(?:,?\s*\d{4})?)\b', re.I)

# --- 5. CPC (Code of Civil Procedure) ---
RE_CPC = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+(?:of\s+(?:the\s+)?)?C\.?\s*P\.?\s*C\.?\b', re.I)

RE_CPC_FULL = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+of\s+(?:the\s+)?Code\s+of\s+Civil\s+Procedure(?:,?\s*\d{4})?\b', re.I)

RE_CPC_ABBR = re.compile(
    r'\b[Ss]s?\.\s*\d[\w\(\)\-/]*'
    r'(?:\s*[,/and]+\s*\d[\w\(\)\-/]*)*'
    r'\s+(?:of\s+(?:the\s+)?)?C\.?\s*P\.?\s*C\.?\b')

# --- 6. Constitutional Articles ---
RE_CONST = re.compile(
    r'\bArticles?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Article\s+)?\d[\w\(\)\-/]*)*'
    r'(?:\s+(?:read\s+with|r/w|or|and)\s+(?:Article\s+)?\d[\w\(\)\-/]*)?'
    r'\s+of\s+(?:the\s+)?Constitution(?:\s+of\s+India)?\b', re.I)

RE_CONST_ABBR = re.compile(
    r'\bArts?\.\s*\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Art\.\s*)?\d[\w\(\)\-/]*)*'
    r'\s+of\s+(?:the\s+)?Constitution\b', re.I)

# --- 7. Order-Rule references ---
RE_ORDER = re.compile(
    r'\bOrder\s+(?:[IVXLC]+|\d+)\s+Rule\s+\d+[\w\(\)]*'
    r'(?:\s+(?:of\s+(?:the\s+)?)?(?:CPC|C\.P\.C\.?|Code\s+of\s+Civil\s+Procedure))?\b', re.I)

# --- 8. Named Act Sections ---
# SAFE: uses \w+ word boundaries instead of charset+whitespace combos
# Captures: "Section 30 of the Indian Evidence Act, 1872"
RE_NAMED_ACT = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'(?:\s*[,/]\s*(?:Section\s+)?\d[\w\(\)\-/]*)*'
    r'\s+of\s+(?:the\s+)?'
    r'(?:[A-Z]\w+\s+){1,8}Act(?:,?\s*\d{4})?\b')

RE_NAMED_ACT_ABBR = re.compile(
    r'\b[Ss]s?\.\s*\d[\w\(\)\-/]*'
    r'(?:\s*[,/and]+\s*\d[\w\(\)\-/]*)*'
    r'\s+of\s+(?:the\s+)?'
    r'(?:[A-Z]\w+\s+){1,8}Act(?:,?\s*\d{4})?\b')

# Acronym Acts
RE_ACRONYM_ACT = re.compile(
    r'\bSections?\s+\d[\w\(\)\-/]*'
    r'\s+(?:of\s+(?:the\s+)?)?'
    r'(?:PMLA|NDPS|POCSO|NIA|TADA|UAPA|SEBI|SARFAESI|FEMA|FERA|DV|POSH|IT|PC|NI|MMDR|BR|RPA)'
    r'(?:\s+Act)?(?:,?\s*\d{4})?\b', re.I)

# Numbered Act: "s. 5 of Act 18 of 1947"
RE_NUMBERED_ACT = re.compile(
    r'\b[Ss]s?\.\s*\d[\w\(\)\-/]*'
    r'\s+of\s+Act\s+\d+\s+of\s+\d{4}\b', re.I)

# Clause-of-Section: "clause (b) of Section 153A"
RE_CLAUSE = re.compile(
    r'\b(?:sub-?)?clause\s*\([a-zA-Z0-9]+\)\s+of\s+Section\s+\d[\w\(\)\-]*'
    r'(?:\s+of\s+(?:the\s+)?(?:\w+\s+){0,6}(?:Act|Code|Sanhita)(?:,?\s*\d{4})?)?\b', re.I)

# sub-section: "sub-section (1) of Section 127C of the Act"
RE_SUBSEC = re.compile(
    r'\bsub-?sections?\s*\(\d+\)\s+of\s+Section\s+\d[\w\(\)\-]*'
    r'(?:\s+of\s+(?:the\s+)?(?:\w+\s+){0,6}Act(?:,?\s*\d{4})?)?\b', re.I)

# --- 9. Read-with / r/w combinations ---
RE_RW = re.compile(
    r'\bSection\s+\d[\w\(\)\-/]*\s+(?:read\s+with|r/w)\s+Section\s+\d[\w\(\)\-/]*'
    r'(?:\s+(?:of\s+(?:the\s+)?)?(?:\w+\s+){0,6}'
    r'(?:Act|Code|IPC|CrPC|CPC|PMLA|NDPS|BNS|BNSS)(?:,?\s*\d{4})?)?\b', re.I)

RE_RW_ABBR = re.compile(
    r'\b[Ss]\.\s*\d[\w\(\)\-/]*\s+(?:read\s+with|r/w)\s+[Ss]\.\s*\d[\w\(\)\-/]*'
    r'(?:\s+(?:of\s+(?:the\s+)?)?(?:\w+\s+){0,6}(?:Act|Code)(?:,?\s*\d{4})?)?\b')

# --- 10. Bare comma-separated section lists (3+ sections) ---
RE_BARE = re.compile(
    r'\bSections?\s+\d[\w\(\)\-]*'
    r'(?:\s*,\s*(?:Section\s+)?\d[\w\(\)\-]*){2,}'
    r'(?:\s+and\s+(?:Section\s+)?\d[\w\(\)\-]*)?\b', re.I)

# --- 11. Raw ACT: header block (Indian Kanoon metadata) ---
RE_ACT_BLOCK = re.compile(
    r'\bACT:\s*(.*?)\s*Indian\s+Kanoon\s*-\s*http://indiankanoon\.org',
    re.I | re.S)


# ── EXTRACTION ───────────────────────────────────────────────────────────────

def extract_raw_act_block(text):
    """Extract the raw ACT: header block from the document head.
    Only scans the first 4000 chars since the ACT block consistently
    appears near the top of Indian Kanoon judgments."""
    head = text[:4000]

    m = RE_ACT_BLOCK.search(head)
    if not m:
        return ""

    block = clean(m.group(1))

    # cleanup repeated whitespace/newlines/page artifacts
    block = re.sub(r'\s+', ' ', block)

    return block.strip()


def extract(text):
    raw_act_block = extract_raw_act_block(text)

    return {
        'ipc_sections':        dedup(find_all(RE_IPC, text) + find_all(RE_IPC_FULL, text) +
                                     find_all(RE_IPC_ABBR, text) + find_all(RE_IPC_PART, text)),
        'bns_sections':        find_all(RE_BNS, text),
        'crpc_sections':       dedup(find_all(RE_CRPC, text) + find_all(RE_CRPC_FULL, text) +
                                     find_all(RE_CRPC_ABBR, text)),
        'bnss_sections':       find_all(RE_BNSS, text),
        'cpc_sections':        dedup(find_all(RE_CPC, text) + find_all(RE_CPC_FULL, text) +
                                     find_all(RE_CPC_ABBR, text)),
        'constitutional_refs': dedup(find_all(RE_CONST, text) + find_all(RE_CONST_ABBR, text)),
        'order_rules':         find_all(RE_ORDER, text),
        'named_act_sections':  dedup(find_all(RE_NAMED_ACT, text) + find_all(RE_NAMED_ACT_ABBR, text) +
                                     find_all(RE_ACRONYM_ACT, text) + find_all(RE_NUMBERED_ACT, text) +
                                     find_all(RE_CLAUSE, text) + find_all(RE_SUBSEC, text)),
        'rw_combinations':     dedup(find_all(RE_RW, text) + find_all(RE_RW_ABBR, text)),
        'bare_section_lists':  find_all(RE_BARE, text),
        'raw_act_block':       raw_act_block,
    }


_LIST_KEYS = ['ipc_sections','bns_sections','crpc_sections','bnss_sections',
              'cpc_sections','constitutional_refs','order_rules',
              'named_act_sections','rw_combinations','bare_section_lists']
EMPTY = {k: [] for k in _LIST_KEYS}
EMPTY['raw_act_block'] = ''

# ── MAIN ─────────────────────────────────────────────────────────────────────

# ── CITATION REGEX (For healing missing files) ──────────────────────────────
RE_EQUIV = re.compile(r'Equivalent citations:\s*([^\n]+)', re.I)
RE_CASE_NO = re.compile(r'CASE NO\.:\s*\n([^\n]+)', re.I)
RE_INSC = re.compile(r'\b((?:19|20)\d{2}\s+INSC\s+\d+)\b', re.I)
RE_CITE_BLOCK = re.compile(
    r'CITATION:\s*\n(.*?)(?:\n\s*CITATOR INFO|\n\s*ACT|\n\s*JUDGMENT|\n\s*\n)',
    re.DOTALL | re.I)

REPORTERS = (r"AIR|SCC|SCR|SCALE|JT|INSC|LLJ|Cr\.?L\.?J\.?|CriLJ|ITR|STC|ELT|SCW|AC|"
             r"Comp\.?\s*Cas(?:es)?|L\.?Ed\.?|U\.?S\.?|W\.?L\.?R\.?|S\.?C\.?R\.?|"
             r"S\.?C\.?C\.?|A\.?I\.?R\.?")

RE_BODY_CITES = re.compile(
    rf'\b(?:19|20)\d{{2}}\s+(?:\(\d+\)\s+|\d+\s+)?(?:{REPORTERS})\s+(?:\w+\s+)?\d+\b|'
    rf'[\(\[](?:19|20)\d{{2}}[\)\]]\s+(?:\d+\s+)?(?:{REPORTERS})\s+(?:\w+\s+)?\d+\b|'
    rf'\b(?:{REPORTERS})\s+(?:19|20)\d{{2}}\s+(?:\(\d+\)\s+)?(?:SC|SUPREME COURT)?\s*\d+\b',
    re.I)

RE_CASE_NAMES = re.compile(
    r'\b([A-Z][\w\.\&\'\-]*?(?:\s+(?:[A-Z][\w\.\&\'\-]*?|of|the|and|in|on|&)){0,7}'
    r'\s+v(?:s)?\.?\s+'
    r'[A-Z][\w\.\&\'\-]*?(?:\s+(?:[A-Z][\w\.\&\'\-]*?|of|the|and|in|on|&)){0,7})\b')

def extract_citations_for_missing(text):
    """Heal completely missing files by building citation fields on the fly."""
    head = text[:2000]
    self_cites = set()
    m = RE_EQUIV.search(head)
    if m:
        for c in m.group(1).split(','):
            if clean(c): self_cites.add(clean(c))
    for m in RE_INSC.finditer(head):
        self_cites.add(clean(m.group(1)))
    m = RE_CITE_BLOCK.search(head)
    if m:
        for c in re.findall(rf'((?:19|20)\d{{2}}\s+(?:{REPORTERS})\s+\d+)', m.group(1), re.I):
            self_cites.add(clean(c))
    if not self_cites:
        m = RE_CASE_NO.search(head)
        if m: self_cites.add(clean("CASE NO: " + m.group(1)))

    body_cites = set()
    for m in RE_BODY_CITES.finditer(text):
        body_cites.add(clean(m.group(0)))
    body_cites -= self_cites

    case_names = set()
    for m in RE_CASE_NAMES.finditer(text):
        case_names.add(clean(m.group(1)))

    return list(self_cites), list(body_cites), list(case_names)


# ── MAIN ─────────────────────────────────────────────────────────────────────

def process_file_full(fpath, existing_rec):
    """Process a single file: extract statutes, and heal citations if record was missing."""
    fid = fpath.stem
    yr = fpath.parent.name
    
    # Base structure
    rec = existing_rec or {
        'file_id': fid,
        'year': yr,
        'self_citations': [],
        'cited_cases': [],
        'case_names': []
    }
    
    # Remove old deprecated columns
    rec.pop('ipc_mentions', None)
    rec.pop('act_mentions', None)
    for k in EMPTY.keys():
        rec.pop(k, None)  # Cleans up the root level if they were generated in a previous run


    try:
        text = fpath.read_text(encoding='utf-8', errors='ignore')
    # except Exception:
    #     rec.update(EMPTY)
    except Exception as e:
        print(f"[ERROR] {fid}: {e}")
        rec['statutes'] = {k: [] for k in EMPTY.keys()} # Creates a fresh empty dict
        return rec, 0

    t0 = time.perf_counter()
    
    # 1. Healing citations if it was completely missing
    if not existing_rec:
        s_cites, b_cites, c_names = extract_citations_for_missing(text)
        rec['self_citations'] = s_cites
        rec['cited_cases'] = b_cites
        rec['case_names'] = c_names
        
    # 2. Extract statutes
    # rec.update(extract(text))
    rec['statutes'] = extract(text)
    ms = (time.perf_counter() - t0) * 1000
    
    return rec, ms


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[2]
    # base = Path(__file__).resolve().parent.parent / "archive" / "supreme_court_judgments_txt"

    base  = project_root / "data" / "input" / "supreme_court_judgments_txt"
    jpath = project_root / "data" / "processed" / "phase1" / "citations_network.jsonl"
    tmp = jpath.with_suffix('.tmp')

    # --- Load ---
    print("Loading JSONL to map existing files...")
    existing_map = {}
    if jpath.exists():
        for line in open(jpath, 'r', encoding='utf-8'):
            if line.strip():
                try:
                    obj = json.loads(line.strip())
                    existing_map[obj.get('file_id')] = obj
                except json.JSONDecodeError:
                    pass
    print(f"Loaded {len(existing_map)} records from JSONL.\n")

    # --- Discover Files ---
    print("Discovering files on disk...")
    all_files = list(Path(base).rglob("*.txt"))
    total = len(all_files)
    print(f"Found {total} files on disk. Commencing auto-healing statutory extraction...\n")

    start = time.time()
    out = open(tmp, 'w', encoding='utf-8')
    
    healed_count = 0

    import concurrent.futures
    # Sequential approach is fast enough but we use a robust loop
    for i, fpath in enumerate(all_files):
        fid = fpath.stem
        existing_rec = existing_map.get(fid)
        if not existing_rec:
            healed_count += 1
            
        rec, ms = process_file_full(fpath, existing_rec)
        
        if ms > 2000:
            sys.stdout.write(f"\n  [SLOW] {fid}: {ms:.0f}ms")
            
        out.write(json.dumps(rec, ensure_ascii=False) + '\n')

        # ASCII Progress every file
        if (i + 1) % 100 == 0 or i + 1 == total:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            pct = (i + 1) * 100 // total
            bar = '#' * (pct // 2) + '-' * (50 - pct // 2)
            sys.stdout.write(f"\r  [{bar}] {pct}%  {i+1}/{total}  "
                             f"({rate:.0f}/s  ETA {eta:.0f}s)  ")
            sys.stdout.flush()

    out.close()

    # Replace
    try:
        os.replace(tmp, jpath)
    except PermissionError:
        os.remove(jpath)
        os.rename(tmp, jpath)

    elapsed = time.time() - start

    # Stats
    print(f"\n\n=== Extraction & Auto-Healing Complete in {elapsed:.1f}s ===")
    print(f"Total Output Records: {total}")
    print(f"Files completely auto-healed (missed initially): {healed_count}")
    print(f"Saved to: {jpath}\n")

if __name__ == '__main__':
    main()
