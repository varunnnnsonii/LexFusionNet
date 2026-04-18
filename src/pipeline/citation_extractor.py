import re

class CitationExtractor:
    def __init__(self):
        # A massive unified pattern to catch various reporters
        # \s+ will implicitly handle \n
        reporters = r'(?:SCC|SCR|AIR(?:\s*SCW|SC)?|INSC|SCALE|JT|ILR|Cri\s*LJ|ALL|BOM|SCW|SC|SUPREME\s*COURT)'
        
        # Matches formats like:
        # (2011) 7 SCC 59
        # 1951 AIR 9
        # [1950] SCR 792
        # AIR 1951 SC 9
        # 2023 INSC 1
        self.unified_pattern = re.compile(
            rf'\b(?:\[?\d{{4}}\]?|\d+)\s*[\(\[]?\d*[\)\]]?\s*{reporters}\s*(?:\([a-z\s]*\))?\s*\d+\b', 
            re.IGNORECASE | re.MULTILINE
        )

        self.air_pattern = re.compile(rf'\bAIR\s+\d{{4}}\s+(?:SC|SUPREME\s+COURT)\s+\d+\b', re.IGNORECASE | re.MULTILINE)

    def extract_from_body(self, text: str) -> list[str]:
        citations = set()
        
        for match in self.unified_pattern.finditer(text):
            citations.add(self.normalize_citation(match.group()))
            
        for match in self.air_pattern.finditer(text):
            citations.add(self.normalize_citation(match.group()))
            
        return list(citations)

    def normalize_citation(self, citation: str) -> str:
        # Clean up whitespace/newlines
        citation = re.sub(r'\s+', ' ', citation)
        citation = citation.replace('[', '').replace(']', '')
        if 'SUPREME COURT' in citation.upper():
            citation = re.sub(r'SUPREME COURT', 'SC', citation, flags=re.IGNORECASE)
        # remove parens at the start like (1988) -> 1988 ? No, SCC requires parens. Let's just strip surrounding brackets.
        
        return citation.strip()

if __name__ == "__main__":
    extractor = CitationExtractor()
    sample = "1933 All\\n394 and 2009 (11) SCALE 24 and AIR 1951 SC 9"
    print("Extracted:", extractor.extract_from_body(sample))
