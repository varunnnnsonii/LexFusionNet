# Dummy extractor currently disabled
# Awaiting migration from experiments...
class CitationExtractor:
    def __init__(self):
        pass
    def extract_from_body(self, text: str) -> list[str]:
        return []
    def normalize_citation(self, citation: str) -> str:
        return citation
