import os
from pathlib import Path
from pdfminer.high_level import extract_text

# INPUT / OUTPUT ROOTS
PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_ROOT = PROJECT_ROOT / "data/input/supreme_court_judgments_pdf"
OUTPUT_ROOT = PROJECT_ROOT / "data/input/supreme_court_judgments_txt"
# LIMIT (for testing)
MAX_FILES = 2


def process_pdf(pdf_path, output_root):
    try:
        text = extract_text(str(pdf_path))

        # Create mirrored path
        relative_path = pdf_path.relative_to(INPUT_ROOT)
        output_path = output_root / relative_path.with_suffix(".txt")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"✅ Saved: {output_path}")

    except Exception as e:
        print(f"❌ Error processing {pdf_path}: {e}")


def main():
    count = 0

    for pdf_file in INPUT_ROOT.rglob("*.PDF"):
        process_pdf(pdf_file, OUTPUT_ROOT)

        count += 1
        if count >= MAX_FILES:
            break

    print(f"\nProcessed {count} files.")


if __name__ == "__main__":
    main()