import json
from collections import defaultdict
from pathlib import Path

# 📁 Paths
input_file = Path("/home/vxrun/LexiFusionNet/data/processed/phase1/citations_network.jsonl")
output_dir = Path("/home/vxrun/LexiFusionNet/artifacts/analysis")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "empty_statutes_by_year.json"

# 🔍 Helper
def is_statutes_empty(statutes):
    if not isinstance(statutes, dict):
        return True
    return all(not v for v in statutes.values())

yearwise = defaultdict(list)
year_counts = defaultdict(int)
total_per_year = defaultdict(int)

total_empty = 0

# 🚀 Single pass
with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        
        year = data.get("year", "UNKNOWN")
        statutes = data.get("statutes", {})
        
        total_per_year[year] += 1
        
        if is_statutes_empty(statutes):
            yearwise[year].append(data.get("file_id", "UNKNOWN"))
            year_counts[year] += 1
            total_empty += 1

# 📊 Summary
print("\n=== YEAR-WISE EMPTY STATUTES ===\n")
for year in sorted(year_counts):
    print(f"{year}: {year_counts[year]} files")

print(f"\nTotal problematic files: {total_empty}")

# 📊 Failure %
print("\n=== FAILURE % BY YEAR ===\n")
for year in sorted(total_per_year):
    total = total_per_year[year]
    failed = year_counts.get(year, 0)
    pct = (failed / total * 100) if total else 0
    print(f"{year}: {failed}/{total} ({pct:.1f}%)")

# 💾 Save output
with open(output_file, "w", encoding="utf-8") as out:
    json.dump(yearwise, out, indent=2)

print(f"\nSaved detailed output to: {output_file}")