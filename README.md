# LexFusionNet

LexFusionNet is an advanced Python-based AI framework designed for legal research and judgment analysis.

## Project Vision & Problem Framing

The Indian legal system relies heavily on case law and historical precedent. However, analyzing decades of judgments can be computationally and manually intensive. LexFusionNet addresses this context by establishing an AI-powered pipeline to structure, query, and analyze massive volumes of Supreme Court judgments cleanly and effectively.

## Architecture (High-Level)

- **Data Layer**: Processing logic for structural extraction of judgment components.
- **Model Layer**: NLP models specialized in legal text retrieval and summarization.
- **Serving Layer**: Planned REST or GraphQL APIs to expose analytical features.

## Roadmap

- [x] Initial Repository Structure Setup
- [ ] Implement Data Ingestion Pipeline
- [ ] Establish Vector Database for Search
- [ ] Prototype RAG-based Querying Interface

## Intended Dataset

https://www.kaggle.com/datasets/vxrunsonii/supreme-court-judgments-txt

## Setup

Requirements and installation instructions will be added as the architecture matures.


## data 
data/
├── input/
│   └── supreme_court_judgments_txt/
│       └── 1951/
│           └── xyz.txt
│
├── output/
│
└── processed/
    ├── chunks/                  # (currently empty)
    │
    ├── phase0/
    │   └── yearwise_headnotes/
    │       └── 1950.jsonl       # multiple year-wise files
    │
    └── phase1/
        └── citations_network.jsonl