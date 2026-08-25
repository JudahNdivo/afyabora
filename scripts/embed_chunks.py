import json
import os
import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Configuration:
load_dotenv()

CHUNKS_PATH = "data/processed_chunks.json"
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 100 # embed and insert 100 chunks at a time


# Load chunks:
def load_chunks():
    print(f"Loading chunks from {CHUNKS_PATH}...")
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks")
    return chunks


# Connect to database:
def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


# Clear existing chunks:
def clear_existing_chunks(conn):
    """
    Removes all existing chunks before re-inserting.
    Ensures no duplicate data if script is run multiple times.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM document_chunks;")
    conn.commit()
    cursor.close()
    print("Cleared existing chunks from database")


# Embed and insert chunks:
def embed_and_insert(chunks, model, conn):
    """
    Generates embeddings for all chunks in batches
    and inserts them into PostgreSQL with pgvector.
    """
    cursor = conn.cursor()
    total = len(chunks)
    inserted = 0

    print(f"\nEmbedding and inserting {total} chunks...")
    print(f"Using model: {MODEL_NAME}")
    print(f"Batch size: {BATCH_SIZE}\n")

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]

        # Extract text from each chunk for embedding
        texts = [chunk["text"] for chunk in batch]

        # Generate embeddings for the entire batch at once
        # Returns a 2D array — one vector of 384 numbers per chunk
        embeddings = model.encode(texts, show_progress_bar=False)

        # Prepare rows for bulk insertion
        rows = []
        for chunk, embedding in zip(batch, embeddings):
            rows.append((
                chunk["id"],
                chunk["disease"],
                chunk["source_file"],
                chunk["chunk_index"],
                chunk["text"],
                embedding.tolist() # convert numpy array to Python list
            ))

        # Bulk insert all rows in this batch
        execute_values(
            cursor,
            """
            INSERT INTO document_chunks
                (id, disease, source_file, chunk_index, chunk_text, embedding)
            VALUES %s
            """,
            rows
        )

        conn.commit()
        inserted += len(batch)

        # Progress update
        progress = (inserted / total) * 100
        print(f"Progress: {inserted}/{total} chunks ({progress:.1f}%)")

    cursor.close()
    print(f"\nDone — {inserted} chunks inserted into database")


# Verify insertion:
def verify_insertion(conn):
    """
    Checks the database to confirm chunks were inserted correctly.
    Prints a breakdown by disease category.
    """
    cursor = conn.cursor()

    # Total count
    cursor.execute("SELECT COUNT(*) FROM document_chunks;")
    total = cursor.fetchone()[0]

    # Count by disease
    cursor.execute("""
        SELECT disease, COUNT(*)
        FROM document_chunks
        GROUP BY disease
        ORDER BY disease;
    """)
    breakdown = cursor.fetchall()

    cursor.close()

    print("\nDatabase Verification: ")
    print(f"Total chunks in database: {total}")
    for disease, count in breakdown:
        print(f"  {disease}: {count} chunks")


# Main: 
def main():
    # Load the multilingual sentence transformer model
    # Downloads automatically on first run
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded\n")

    # Load all chunks from JSON
    chunks = load_chunks()

    # Connect to Supabase PostgreSQL
    print("Connecting to database...")
    conn = get_connection()
    print("Connected\n")

    # Clear any existing data to avoid duplicates
    clear_existing_chunks(conn)

    # Embed all chunks and insert into database
    embed_and_insert(chunks, model, conn)

    # Verifying everything was inserted correctly
    verify_insertion(conn)

    conn.close()
    print("\nConnection closed. Embedding complete.")


if __name__ == "__main__":
    main()