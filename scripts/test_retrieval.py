import os
import psycopg2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5


def retrieve_chunks(query: str, model, conn, disease: str = None, top_k: int = TOP_K) -> list:
    # Embed the query and retrieve the most similar chunks
    # using pgvector cosine similarity search
    query_vector = model.encode(query).tolist()

    cursor = conn.cursor()

    if disease:
        # Filter by disease category if provided
        cursor.execute(
            """
            SELECT chunk_text, disease, source_file, chunk_index,
                   1 - (embedding <-> %s::vector) AS score
            FROM document_chunks
            WHERE disease = %s
            ORDER BY embedding <-> %s::vector
            LIMIT %s;
            """,
            (query_vector, disease, query_vector, top_k)
        )
    else:
        cursor.execute(
            """
            SELECT chunk_text, disease, source_file, chunk_index,
                   1 - (embedding <-> %s::vector) AS score
            FROM document_chunks
            ORDER BY embedding <-> %s::vector
            LIMIT %s;
            """,
            (query_vector, query_vector, top_k)
        )

    results = cursor.fetchall()
    cursor.close()
    return results


def main():
    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded\n")

    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    print("Connected\n")

    print("Retrieval test ready.")
    print("Type 'exit' to quit.\n")

    while True:
        query = input("Ask a question: ").strip()

        if query.lower() == "exit":
            break

        if not query:
            continue

        disease = input("Disease filter (hiv/sti or blank): ").strip().lower()
        if disease == "":
            disease = None

        results = retrieve_chunks(query, model, conn, disease=disease)

        print(f"\nTop matches:\n")
        for i, result in enumerate(results, start=1):
            chunk_text, disease_cat, source_file, chunk_index, score = result
            print(f"Result {i}")
            print(f"Score: {score:.4f}")
            print(f"Disease: {disease_cat}")
            print(f"Source: {source_file}")
            print(f"Chunk index: {chunk_index}")
            print(f"Text: {chunk_text[:600]}")
            print("-" * 80)

    conn.close()
    print("Connection closed.")


if __name__ == "__main__":
    main()