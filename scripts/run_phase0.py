"""Phase 0 orchestrator — runs data audit and full corpus parse."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.diagnostics.data_audit import run_audit


if __name__ == '__main__':
    import random
    random.seed(42)
    print("=" * 60)
    print("PHASE 0: Data Reality & Diagnostics")
    print("=" * 60)
    run_audit()
