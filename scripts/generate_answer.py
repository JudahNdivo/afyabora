import os
import time
import psycopg2
from sentence_transformers import SentenceTransformer
from google import genai
from langdetect import detect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
GEMINI_MODEL = "gemini-3.5-flash"
TOP_K = 5

# Setup Gemini client
client = genai.Client(api_key=GOOGLE_API_KEY)


def detect_language(text: str) -> str:
    # Kiswahili common words — if any appear, treat as Kiswahili
    swahili_markers = [
        "je", "aje", "nini", "jinsi", "gani", "sasa", "mtu",
        "unaweza", "anaeza", "pata", "ni", "na", "ya", "kwa",
        "inaenezwa", "dalili", "matibabu", "ugonjwa", "dawa",
        "hospitali", "ngono", "kinga", "sindano", "damu"
    ]

    text_lower = text.lower()
    words = text_lower.split()

    # Check if any Kiswahili marker words are present
    for word in words:
        if word in swahili_markers:
            return "sw"

    # Fall back to langdetect for longer queries
    try:
        lang = detect(text)
        if lang == "sw":
            return "sw"
        return "en"
    except Exception:
        return "en"


def normalise_query_for_retrieval(query: str, language: str) -> str:
    # For Kiswahili queries, translate to English for retrieval
    # since the knowledge base is in English
    if language == "en":
        return query

    translation_prompt = f"""Translate this health question to English.
Return ONLY the English translation, nothing else.

Question: {query}
English translation:"""

    interaction = client.interactions.create(
        model=GEMINI_MODEL,
        input=translation_prompt
    )
    english_query = interaction.output_text.strip()
    print(f"Query translated for retrieval: {english_query}")
    return english_query


def expand_query(query: str) -> str:
    # Expand casual contact queries to improve retrieval
    # of myth-busting content from the knowledge base
    casual_contact_terms = [
        "toilet", "toilet seat", "doorknob", "swimming pool",
        "sharing", "utensils", "casual contact", "surfaces"
    ]

    query_lower = query.lower()
    for term in casual_contact_terms:
        if term in query_lower:
            return (
                query +
                " syphilis casual contact cannot transmit toilet seats"
            )
    return query


def get_connection():
    # Create a new database connection
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def retrieve_chunks(query: str, model, conn, top_k: int = TOP_K) -> list:
    # Embed the query and retrieve the most similar chunks
    # using pgvector cosine similarity search
    query_vector = model.encode(query).tolist()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT chunk_text, disease, source_file, chunk_index
            FROM document_chunks
            ORDER BY embedding <-> %s::vector
            LIMIT %s;
            """,
            (query_vector, top_k)
        )
        results = cursor.fetchall()
        cursor.close()
        return results
    except Exception:
        # Reconnect if connection was dropped and retry
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT chunk_text, disease, source_file, chunk_index
            FROM document_chunks
            ORDER BY embedding <-> %s::vector
            LIMIT %s;
            """,
            (query_vector, top_k)
        )
        results = cursor.fetchall()
        cursor.close()
        return results


def build_prompt(query: str, chunks: list, language: str) -> str:
    # Combine retrieved chunks into a single context block
    context = "\n\n".join([chunk[0] for chunk in chunks])

    if language == "sw":
        language_instruction = (
            "Jibu kwa Kiswahili. "
            "Jibu kwa lugha ile ile ambayo swali liliulizwa."
        )
    else:
        language_instruction = "Answer in English."

    prompt = f"""You are AfyaBora, a friendly and trustworthy STI health \
education assistant for youth in Nairobi, Kenya.

Your role is to provide accurate, stigma-free, and detailed sexual health \
information based ONLY on the verified health guidelines provided below.

IMPORTANT RULES:
- Answer ONLY using the information in the CONTEXT below
- Do NOT use any outside knowledge or make up information
- Provide a thorough and specific answer covering all relevant points from the context including causes, symptoms, prevention, and treatment where available
- Use numbered lists or bullet points to organise information clearly
- If the context contains partial information, share everything available and recommend visiting a health facility for more information
- If the context has NO relevant information at all, say so clearly and recommend visiting a health facility
- Be empathetic, non-judgmental, and clear
- For questions about casual contact such as toilet seats, doorknobs, swimming pools, or sharing utensils use specific STI evidence from the context to give a general answer about casual contact transmission
- {language_instruction}
- End with a brief recommendation to seek professional care for personal medical decisions

CONTEXT FROM VERIFIED HEALTH GUIDELINES:
{context}

USER QUESTION: {query}

ANSWER:"""

    return prompt


def generate_answer(prompt: str) -> str:
    # Send prompt to Gemini using the Interactions API
    # with retry on server errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            interaction = client.interactions.create(
                model=GEMINI_MODEL,
                input=prompt
            )
            return interaction.output_text.strip()
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                wait_time = (attempt + 1) * 5
                print(f"Server busy, retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e
    return "AfyaBora is temporarily unavailable. Please try again in a moment."


def rag_pipeline(query: str, model, conn) -> dict:
    # Step 1 - detect language
    language = detect_language(query)

    # Step 2 - translate query to English for retrieval if Kiswahili
    retrieval_query = normalise_query_for_retrieval(query, language)

    # Step 3 - expand query for better retrieval then retrieve chunks
    expanded_query = expand_query(retrieval_query)
    chunks = retrieve_chunks(expanded_query, model, conn)

    # Step 4 - build augmented prompt with original query
    prompt = build_prompt(query, chunks, language)

    # Step 5 - generate answer from Gemini
    answer = generate_answer(prompt)

    return {
        "query": query,
        "language": language,
        "retrieval_query": retrieval_query,
        "answer": answer,
        "sources": [
            {
                "source_file": chunk[2],
                "disease": chunk[1],
                "chunk_index": chunk[3]
            }
            for chunk in chunks
        ]
    }


def main():
    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded\n")

    print("Connecting to database...")
    conn = get_connection()
    print("Connected\n")

    print("AfyaBora RAG Pipeline - Interactive Test")
    print("Type 'exit' to quit\n")
    print("-" * 50)

    while True:
        query = input("\nAsk a question: ").strip()

        if query.lower() == "exit":
            break

        if not query:
            continue

        print("\nProcessing...")
        result = rag_pipeline(query, model, conn)

        print(f"\nLanguage detected: {result['language']}")
        if result['language'] != 'en':
            print(f"Retrieval query: {result['retrieval_query']}")
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nSources used:")
        for source in result['sources']:
            print(f"  - {source['source_file']} ({source['disease']})")
        print("\n" + "-" * 50)

    conn.close()
    print("Connection closed.")


if __name__ == "__main__":
    main()