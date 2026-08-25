import os
import fitz  # PyMuPDF

# Configuration:
BASE_PATH = "data"
DISEASES = ["hiv", "sti"]

# Keywords to keep STI-relevant pages from the Kenya clinical
# guidelines which covers many diseases beyond STIs
STI_KEYWORDS = [
    "sexually transmitted", "gonorrhoea", "gonorrhea", "chlamydia",
    "syphilis", "hpv", "human papillomavirus", "genital ulcer",
    "vaginal discharge", "urethral discharge", "pelvic inflammatory",
    "herpes", "chancroid", "trichomoniasis", "sti ", "stis",
    "sexual health", "sexual transmission", "condom", "antibiotic",
    "penicillin", "doxycycline", "ceftriaxone", "azithromycin",
    "benzathine", "metronidazole", "cervical cancer", "genital warts"
]

# Keywords that indicate non-STI content to exclude from
# the Kenya clinical guidelines document
NON_STI_KEYWORDS = [
    "malaria", "tuberculosis", "hypertension", "diabetes",
    "cardiovascular", "fracture", "poisoning", "appendix",
    "anaesthesia", "surgical", "obstetric", "paediatric",
    "neonatal", "nutrition", "burns", "wound"
]


# Filtering logic:
def is_sti_relevant(text: str) -> bool:
    """
    Returns True if the page is more about STIs than other diseases.
    Used specifically for the Kenya clinical guidelines document
    which covers many conditions beyond STIs.
    """
    text_lower = text.lower()

    sti_score = sum(text_lower.count(kw) for kw in STI_KEYWORDS)
    non_sti_score = sum(text_lower.count(kw) for kw in NON_STI_KEYWORDS)

    # Keep page if it has any STI content and STI mentions
    # outnumber non-STI mentions
    return sti_score > 0 and sti_score >= non_sti_score


# PDF extraction:
def extract_text_from_pdf(pdf_path: str, apply_sti_filter: bool = False) -> str:
    """
    Extracts and returns text from a PDF file.
    Optionally filters pages to retain only STI-relevant content.
    """
    doc = fitz.open(pdf_path)
    pages = []
    skipped = 0

    for page in doc:
        text = page.get_text("text")
        if not text:
            continue

        if apply_sti_filter:
            if not is_sti_relevant(text):
                skipped += 1
                continue

        pages.append(text)

    doc.close()

    if apply_sti_filter:
        print(f"  STI filter: kept {len(pages)} pages, skipped {skipped} non-STI pages")

    return "\n".join(pages)


# Text cleaning:
def clean_text(text: str) -> str:
    """
    Removes unusual unicode characters and normalises whitespace
    while preserving meaningful line breaks between paragraphs.
    """
    text = text.replace("\u2028", " ")
    text = text.replace("\u2029", " ")
    text = text.replace("\xa0", " ")

    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# Process one disease folder:
def process_disease_folder(disease: str) -> None:
    """
    Processes all PDFs in a disease's raw folder,
    saves cleaned text to the cleaned folder.
    """
    raw_dir = os.path.join(BASE_PATH, disease, "raw")
    cleaned_dir = os.path.join(BASE_PATH, disease, "cleaned")
    os.makedirs(cleaned_dir, exist_ok=True)

    if not os.path.exists(raw_dir):
        print(f"Skipping missing folder: {raw_dir}")
        return

    for filename in os.listdir(raw_dir):
        if not filename.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(raw_dir, filename)
        txt_name = filename.rsplit(".", 1)[0] + ".txt"
        txt_path = os.path.join(cleaned_dir, txt_name)

        # STI filter only to the Kenya clinical guidelines document which covers many diseases beyond STIs
        apply_filter = "kenya_clinical_guidelines" in filename.lower()

        print(f"Processing: {pdf_path}")
        if apply_filter:
            print(f"  (STI content filter active)")

        try:
            raw_text = extract_text_from_pdf(pdf_path, apply_sti_filter=apply_filter)
            cleaned_text = clean_text(raw_text)

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(cleaned_text)

            print(f"  Saved: {txt_path}")
            print(f"  Characters extracted: {len(cleaned_text):,}\n")

        except Exception as e:
            print(f"  Failed to process {pdf_path}: {e}\n")


# Main:
def main():
    for disease in DISEASES:
        process_disease_folder(disease)

    print("\nExtraction Summary:")
    for disease in DISEASES:
        cleaned_dir = os.path.join(BASE_PATH, disease, "cleaned")
        if not os.path.exists(cleaned_dir):
            continue
        for filename in os.listdir(cleaned_dir):
            if not filename.endswith(".txt"):
                continue
            filepath = os.path.join(cleaned_dir, filename)
            size = os.path.getsize(filepath)
            status = "OK" if size > 50000 else "SMALL"
            print(f"{status}  {disease}/{filename}: {size:,} bytes")


if __name__ == "__main__":
    main()