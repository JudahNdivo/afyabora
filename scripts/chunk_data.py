import os
import json
import uuid

# Configuration:
BASE_PATH = "data"
OUTPUT_PATH = "data/processed_chunks.json"
DISEASES = ["hiv", "sti"]


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
    splits them into chunks, and attaches metadata to each.
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
            disease_chunks.append({
                "id": str(uuid.uuid4()), # unique identifier for each chunk
                "disease": disease, # hiv or sti
                "source_file": source_name, # which document it came from
                "chunk_index": i, # position within the document
                "text": chunk # the actual text content
            })

        print(f"  → {len(chunks)} chunks from {filename}")

    return disease_chunks


# Main:
def main():
    all_chunks = []

    for disease in DISEASES:
        chunks = process_disease(disease)
        all_chunks.extend(chunks)
        print(f"  Subtotal for {disease}: {len(chunks)} chunks\n")

    print(f"Total chunks created: {len(all_chunks)}")

    # Save all chunks to JSON for embedding in the next step
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {OUTPUT_PATH}")

    # Preview first chunk to verify structure
    print("\nSample Chunk: ")
    print(json.dumps(all_chunks[0], indent=2))


if __name__ == "__main__":
    main()