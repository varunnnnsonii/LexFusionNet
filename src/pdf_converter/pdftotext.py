import fitz  # PyMuPDF
from pathlib import Path
from tqdm import tqdm

def convert_pdfs_to_text(base_dir: str):
    base_path = Path(base_dir)

    # Scans the base directory for any .pdf or .PDF files
    pdf_files = [p for p in base_path.rglob("*") if p.suffix.lower() == '.pdf']

    if not pdf_files:
        print(f"No PDF files found in {base_dir}")
        return

    print(f"Found {len(pdf_files)} PDF files. Processing...")

    for pdf_file in tqdm(pdf_files, desc="Converting PDFs to text"):
        # Get the relative path starting from 'data' base dir
        rel_path = pdf_file.relative_to(base_path)
        
        # We need to construct the new output path
        # Replace occurrences of "pdf" with "txt" in the directory hierarchy to match the user's intent 
        # (e.g., supreme_court_judgments_pdf -> supreme_court_judgments_txt)
        new_parts = []
        for part in rel_path.parent.parts:
            # dynamically swap pdf identifying folders with text identifying folders
            lower_part = part.lower()
            if "pdf" in lower_part:
                # To be completely safe with different casings
                new_part = part.replace("pdf", "txt").replace("PDF", "TXT").replace("Pdf", "Txt")
                new_parts.append(new_part)
            else:
                new_parts.append(part)
        
        # Build the new output file path (replicating same structure and filenames)
        out_dir = base_path.joinpath(*new_parts)
        # Using the same filename but changing the extension to .txt
        txt_file = out_dir / f"{pdf_file.stem}.txt"
        
        # Ensure output directory exists, creating parents if necessary
        txt_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Skip if the target txt file already exists
            if txt_file.exists():
                print(f"Skipping (already exists): {txt_file}")
                continue
                
            # Open the PDF using PyMuPDF and extract text using list comprehension
            doc = fitz.open(pdf_file)
            text_pages = [page.get_text() for page in doc]
            
            # Write text content to the new .txt file
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write("\n".join(text_pages))
                
            doc.close()
            print(f"Successfully converted: {pdf_file} -> {txt_file}")
        except Exception as e:
            print(f"Error processing {pdf_file}: {e}")

if __name__ == "__main__":
    # Start looking from the "data" folder dynamically
    base_directory = "data"
    convert_pdfs_to_text(base_directory)
    print("All extraction tasks finished!")
