# Artifacts Documentation

This directory contains all pipeline outputs, reports, and reference materials
for LexiFusionNet, organized by phase.

## Directory Structure

```
artifacts/
├── phase0/                          # Phase 0: Data Audit & Quality
│   ├── audit_reports/               # Data audit reports
│   │   ├── data_audit_report.json        # Latest audit (auto-updated by pipeline)
│   │   └── data_audit_report_v1_pre_quality.json  # Original audit (before quality scoring)
│   └── quality_reports/             # Quality scoring summaries
│       └── quality_summary.json          # Quality distribution across corpus
│
├── phase1/                          # Phase 1: Retrieval MVP (future)
│
├── phase2/                          # Phase 2: Structural Intelligence (future)
│
├── docs/                            # Design documents & plans
│   ├── implementation_plan.md
│   ├── session_plan.md
│   └── task.md
│
├── eval_results/                    # Evaluation outputs
├── models/                          # Trained model artifacts
└── README.md                        # This file
```

## Dataset References

- **Primary Dataset**: Supreme Court of India Judgments (1950–2025)
- **Source**: [Kaggle](https://www.kaggle.com/datasets/vxrunsonii/supreme-court-judgments-txt)
- **Total files**: ~26,688
- **Total size**: ~860 MB

## Parsed Data (Output)

Parsed data is written to `data/processed/parsed/` as per-year `.jsonl` files:

```
data/processed/parsed/
├── 1950.jsonl
├── 1951.jsonl
├── ...
└── 2025.jsonl
```

Each line in a `.jsonl` file is a JSON record with fields:
`case_id`, `title`, `date_str`, `year`, `citations`, `author`, `bench`,
`body`, `quality_score`, `quality_flag`, `quality_issues`, `is_valid`
