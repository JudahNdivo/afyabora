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
    # using pgvector cosine similarity search.
    # The multilingual embedding model handles cross-lingual retrieval
    # natively, so Kiswahili/mixed-language queries are embedded
    # directly without translating to English first — this was tested
    # and found to retrieve equally or more relevant chunks while
    # avoiding an extra ~9s translation round-trip per query.
    query_vector = model.encode(query).tolist()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, chunk_text, disease, source_file, chunk_index
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
            SELECT id, chunk_text, disease, source_file, chunk_index
            FROM document_chunks
            ORDER BY embedding <-> %s::vector
            LIMIT %s;
            """,
            (query_vector, top_k)
        )
        results = cursor.fetchall()
        cursor.close()
        return results


def build_prompt(query: str, chunks: list, language: str, history: list = None) -> str:
    # Combine retrieved chunks into a single context block
    # chunk[1] is chunk_text now that chunk[0] is id
    context = "\n\n".join([chunk[1] for chunk in chunks])

    # Include recent conversation history if provided, to help
    # interpret follow-up questions that refer back to a prior exchange
    history_block = ""
    if history:
        history_lines = []
        for past_query, past_response in history:
            history_lines.append(f"User asked: {past_query}")
            history_lines.append(f"You answered: {past_response}")
        history_block = "PREVIOUS CONVERSATION:\n" + "\n".join(history_lines) + "\n\n"

    if language == "sw":
        # Targets informal, everyday Kiswahili/Sheng register rather than
        # formal "textbook" Kiswahili, since target users are Nairobi
        # youth who typically speak casually and mix in some English
        language_instruction = (
            "Jibu kwa Kiswahili rahisi na cha kawaida, kama vile "
            "kijana wa Nairobi angependa kuongea na rafiki yake. "
            "Usitumie Kiswahili cha kitaalamu au maneno magumu. "
            "Unaweza kuchanganya maneno machache ya Kiingereza kama "
            "inavyofanyika kawaida (kwa mfano: STI, test, dawa), "
            "lakini hakikisha maelezo ni rahisi kueleweka."
        )
    else:
        language_instruction = "Answer in English."

    prompt = f"""You are AfyaBora, a friendly and trustworthy STI health \
education assistant for youth in Nairobi, Kenya.

Your role is to provide accurate, stigma-free sexual health information \
based ONLY on the verified health guidelines provided below.

IMPORTANT RULES:
- Do NOT use markdown formatting of any kind — no asterisks, no hashes/headings, no bold, no italics. Plain sentences and simple dashes for lists only.
- Keep the answer concise and focused. Aim for 2-4 short paragraphs or a short list at most. Cover the most important points only, not every detail in the context.
- Answer ONLY using the information in the CONTEXT below
- Do NOT use any outside knowledge or make up information
- If the previous conversation is provided below and the user's question refers back to it (e.g. "what about if untreated", "and for men?"), use it to understand what they are asking, but still answer only from the CONTEXT
- If the user's message is not a real health question (e.g. a greeting, a test message or unclear), do not force an answer from unrelated context — briefly explain what AfyaBora can help with and invite them to ask a specific question about HIV, syphilis, gonorrhoea, chlamydia, or HPV
- If the context contains partial information, share what's available and recommend visiting a health facility for more
- If the context has NO relevant information at all, say so clearly and recommend visiting a health facility
- Be empathetic and non-judgmental
- {language_instruction}
- End with a brief, short recommendation to seek professional care for personal medical decisions

{history_block}CONTEXT FROM VERIFIED HEALTH GUIDELINES:
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


def rag_pipeline(query: str, model, conn, history: list = None) -> dict:
    timings = {}

    # Step 1 - detect language
    t0 = time.time()
    language = detect_language(query)
    timings["language_detection"] = time.time() - t0

    # Step 2 - expand query and retrieve chunks directly using the
    # original query (no translation - see retrieve_chunks note)
    t0 = time.time()
    expanded_query = expand_query(query)
    chunks = retrieve_chunks(expanded_query, model, conn)
    timings["retrieval"] = time.time() - t0

    # Step 3 - build augmented prompt with original query and history
    t0 = time.time()
    prompt = build_prompt(query, chunks, language, history)
    timings["prompt_building"] = time.time() - t0

    # Step 4 - generate answer from Gemini
    t0 = time.time()
    answer = generate_answer(prompt)
    timings["generation"] = time.time() - t0

    print("Stage timings (seconds):")
    for stage, duration in timings.items():
        print(f"  {stage}: {duration:.2f}s")
    print(f"  TOTAL: {sum(timings.values()):.2f}s")

    return {
        "query": query,
        "language": language,
        "answer": answer,
        "sources": [
            {
                "chunk_id": chunk[0],
                "source_file": chunk[3],
                "disease": chunk[2],
                "chunk_index": chunk[4]
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
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nSources used:")
        for source in result['sources']:
            print(f"  - {source['source_file']} ({source['disease']})")
        print("\n" + "-" * 50)

    conn.close()
    print("Connection closed.")


if __name__ == "__main__":
    main()