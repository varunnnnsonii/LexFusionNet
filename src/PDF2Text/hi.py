import re
from pathlib import Path

def evaluate_text_quality(text):
    score = {}

    # 1. Citation patterns (core legal signal)
    citations = re.findall(r'\b(F|R|RF|E|D|E&F)\s+\d{4}\s+SC\s+\d+', text)
    score['citation_count'] = len(citations)

    # 2. Broken uppercase words (PDF artifacts)
    broken_words = re.findall(r'\b[A-Z]{2,}\s+[A-Z]{2,}\b', text)
    score['broken_word_patterns'] = len(broken_words)

    # 3. Long lines (bad formatting)
    long_lines = [line for line in text.split("\n") if len(line) > 200]
    score['long_lines'] = len(long_lines)

    # 4. Joined words (missing spaces)
    joined_words = re.findall(r'[a-z][A-Z]', text)
    score['joined_words'] = len(joined_words)

    return score


# ✅ Proper path handling
PROJECT_ROOT = Path(__file__).resolve().parents[2]

file_path = PROJECT_ROOT / "data/input/supreme_court_judgments_txt/1975/The_District_Controller_Of_Stores_vs_The_Assistant_Commercial_Taxation_on_9_December_1975_1.txt"

with open(file_path, "r", encoding="utf-8") as f:
    
    text = f.read()

print(evaluate_text_quality(text))