import os
import json
import uuid

# Configuration:
BASE_PATH = "data"
OUTPUT_PATH = "data/processed_chunks.json"
DISEASES = ["hiv", "sti"]

# Keyword-based classification, checked per chunk rather than per file.
# A generic source folder (e.g. "sti") can contain chunks about several
# different specific diseases - this assigns each chunk individually
# based on its actual content. Keywords are deduplicated to avoid one
# disease's count being inflated by substring overlap with another
# (e.g. "neisseria gonorrhoeae" contains "gonorrhoea" already).
DISEASE_KEYWORDS = {
    "syphilis": ["syphilis", "treponema pallidum"],
    "gonorrhoea": ["gonorrhoea", "gonorrhea", "gonococcal"],
    "chlamydia": ["chlamydia"],
    "hpv": ["hpv", "human papillomavirus", "genital warts"],
    "hiv": ["hiv", "antiretroviral", " arv ", "plhiv"],
}


def classify_chunk(text: str) -> str:
    """
    Classifies a chunk by counting disease-keyword mentions in its
    own text, rather than trusting the source folder name. Falls
    back to "sti" (generic) when no specific disease is detected.
    """
    text_lower = text.lower()
    matches = {}

    for disease, keywords in DISEASE_KEYWORDS.items():
        count = sum(text_lower.count(kw) for kw in keywords)
        if count > 0:
            matches[disease] = count

    if not matches:
        return "sti"

    return max(matches, key=matches.get)


# Chunking logic:
def split_into_chunks(text: str, chunk_size: int = 300, overlap: int = 50):
    """
    Splits text into fixed-size chunks of around 300 words with
    50-word overlap between consecutive chunks.

    300 words nearly 400 tokens.
    Overlap ensures clinical concepts spanning chunk
    boundaries are not lost.

    Skips chunks shorter than 50 words to avoid tiny
    trailing fragments at the end of documents.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        # Skip tiny trailing fragments
        if len(chunk_words) >= 50:
            chunks.append(chunk_text)

        start += (chunk_size - overlap)

    return chunks


# Process one disease folder:
def process_disease(disease: str) -> list:
    """
    Reads all cleaned .txt files for a disease category,
    splits them into chunks, and classifies each chunk
    individually based on its actual content.
    """
    cleaned_dir = os.path.join(BASE_PATH, disease, "cleaned")
    disease_chunks = []

    for filename in os.listdir(cleaned_dir):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(cleaned_dir, filename)
        source_name = filename.replace(".txt", "")

        print(f"Chunking: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = split_into_chunks(text)

        for i, chunk in enumerate(chunks):
            classified_disease = classify_chunk(chunk)
            disease_chunks.append({
                "id": str(uuid.uuid4()),
                "disease": classified_disease,  # classified per chunk, not per folder
                "source_file": source_name,
                "chunk_index": i,
                "text": chunk
            })

        print(f"  → {len(chunks)} chunks from {filename}")

    return disease_chunks


# Main:
def main():
    all_chunks = []

    for disease in DISEASES:
        chunks = process_disease(disease)
        all_chunks.extend(chunks)
        print(f"  Subtotal for {disease} folder: {len(chunks)} chunks\n")

    print(f"Total chunks created: {len(all_chunks)}")

    # Print breakdown by classified disease, not just source folder
    from collections import Counter
    classified_counts = Counter(c["disease"] for c in all_chunks)
    print("\nClassified disease breakdown:")
    for disease, count in sorted(classified_counts.items(), key=lambda x: -x[1]):
        print(f"  {disease}: {count} chunks")

    # Save all chunks to JSON for embedding in the next step
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {OUTPUT_PATH}")

    # Preview first chunk to verify structure
    print("\nSample Chunk: ")
    print(json.dumps(all_chunks[0], indent=2))


if __name__ == "__main__":
    main()