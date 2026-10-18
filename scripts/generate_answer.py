import os
import re
import time
import psycopg2
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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

# Used to enforce a hard timeout on Gemini calls, regardless of
# whether the client library itself supports a timeout parameter
_executor = ThreadPoolExecutor(max_workers=4)


def detect_language(text: str) -> str:
    # Kiswahili common words — if any appear, treat as Kiswahili
    swahili_markers = [
        "je", "aje", "nini", "jinsi", "gani", "sasa", "mtu",
        "unaweza", "anaeza", "pata", "ni", "na", "ya", "kwa",
        "inaenezwa", "dalili", "matibabu", "ugonjwa", "dawa",
        "hospitali", "ngono", "kinga", "sindano", "damu",  "naweza", "nawezaje", "kupata", "kupewa", "kuambukizwa", "huambukizwa",
        "zipi", "wapi", "vipi", "pia", "sana", "nataka", "kujua", "nilikuwa",
    ]

    words = re.findall(r"[a-z']+", text.lower()) # words only, so "aje?" counts as "aje"


    # Check if any Kiswahili marker words are present
    for word in words:
        if word in swahili_markers or word in SW_TERMS:
            return "sw"

    # Fall back to langdetect for longer queries
    try:
        lang = detect(text)
        if lang == "sw":
            return "sw"
        return "en"
    except Exception:
        return "en"


# Kiswahili/Sheng health terms the embedding model does not reliably
# match, mapped to English equivalents. When a query contains any of
# these, retrieval embeds the English terms instead of the Kiswahili
# wording. Added after tests showed Kiswahili disease names retrieved
# unrelated chunks, and that English terms alone ranked the plain-
# language factsheets higher.
SW_TERMS = {
    "kaswende": "syphilis",
    "kisonono": "gonorrhoea",
    "klamidia": "chlamydia",
    "vvu": "HIV",
    "ukimwi": "HIV AIDS",
    "dalili": "symptoms",
    "maambukizi": "infection transmission",
    "kuambukizwa": "transmission",
    "matibabu": "treatment",
    "kinga": "prevention",
    "kondomu": "condom",
    "vipimo": "testing",
}

# English disease names a user may type inside a Kiswahili sentence,
# kept so they are not lost when the Kiswahili words are dropped
ENGLISH_DISEASES = re.compile(
    r"\b(hiv|hpv|aids|syphilis|gonorrhoea|gonorrhea|chlamydia|stis?)\b"
)


def expand_query(query: str) -> str:
    original_lower = query.lower()

    # English equivalents of any Kiswahili glossary terms found
    terms = [en for sw, en in SW_TERMS.items()
             if re.search(rf"\b{sw}\b", original_lower)]

    if terms:
        # embed English terms only, but keep English disease names the
        # user typed that the glossary terms don't already cover
        covered = set(" ".join(terms).lower().split())
        kept = [d for d in ENGLISH_DISEASES.findall(original_lower)
                if d not in covered]
        text = " ".join(dict.fromkeys(terms + kept))
    else:
        text = query

    # casual-contact myths: check the original wording, so this still
    # works when the text above was replaced
    casual_contact_terms = [
        "toilet", "toilet seat", "doorknob", "swimming pool",
        "sharing", "utensils", "casual contact", "surfaces"
    ]
    for term in casual_contact_terms:
        if term in original_lower:
            return text + " syphilis casual contact cannot transmit toilet seats"
    return text


def get_connection():
    conn = psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )
    conn.autocommit = True
    return conn


def retrieve_chunks(query: str, model, conn, top_k: int = TOP_K) -> list:
    # Embed the query and retrieve the closest chunks using pgvector
    # L2 distance (the <-> operator). The multilingual embedding model
    # handles most cross-lingual retrieval directly, so queries are not
    # translated to English first, which avoids an extra ~9s round-trip.
    # It does miss Kiswahili disease names (e.g. "kaswende"), which
    # expand_query() covers with a small glossary.
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

    prompt = f"""You are AfyaBora, a friendly and trustworthy STI health education assistant for youth in Nairobi, Kenya.
Your role is to provide accurate, stigma-free sexual health information based ONLY on the verified health guidelines provided below.

IMPORTANT RULES:
- Do NOT use markdown formatting of any kind — no asterisks, no hashes/headings, no bold, no italics. Plain sentences and simple dashes for lists only.
- Keep the answer under 120 words. Cover only the most important points, not every detail in the context.
- Answer ONLY using the information in the CONTEXT below
- Do NOT use any outside knowledge or make up information
- If the previous conversation is provided below and the user's question refers back to it (e.g. "what about if untreated", "and for men?"), use it to understand what they are asking, but still answer only from the CONTEXT
- If the user's message is not a real health question (e.g. a greeting, a test message or unclear), do not force an answer from unrelated context — briefly explain what AfyaBora can help with and invite them to ask a specific question about HIV, syphilis, gonorrhoea, chlamydia, or HPV
- If the context contains partial information, share what's available and recommend visiting a health facility for more
- If the context has NO relevant information at all, say so clearly and recommend visiting a health facility
- Be empathetic and non-judgmental
- You may name medicines and vaccines (for example antibiotics or the HPV vaccine), but NEVER state doses, amounts, how often to take them, or for how long. Say that the right medicine and dose must come from a health worker.
- {language_instruction}
- End with a brief, short recommendation to seek professional care for personal medical decisions

{history_block}CONTEXT FROM VERIFIED HEALTH GUIDELINES:
{context}

USER QUESTION: {query}

ANSWER:"""

    return prompt


class GenerationUnavailable(Exception):
    # raised when Gemini could not give an answer after all retries, so the
    # caller can report a failure instead of saving a made-up answer
    pass


def _retryable(error: Exception) -> bool:
    # rate limits (429) and temporary server problems (5xx) are worth
    # retrying; anything else, such as a bad request, is not
    text = str(error)
    code = getattr(error, "status_code", None) or getattr(error, "code", None)
    if code in (429, 500, 502, 503, 504):
        return True
    if re.search(r"\b(429|500|502|503|504)\b", text):
        return True
    return "RESOURCE_EXHAUSTED" in text or "UNAVAILABLE" in text


def _call_gemini(prompt: str) -> str:
    # The raw, blocking Gemini call - wrapped separately so it can
    # be run in a thread with an enforced timeout
    interaction = client.interactions.create(
        model=GEMINI_MODEL,
        input=prompt
    )
    return interaction.output_text.strip()


def generate_answer(prompt: str) -> str:
    # Retries temporary failures (timeouts, rate limits, server errors)
    # with a short wait between attempts, within a total time budget so a
    # user is never left waiting for minutes. Raises GenerationUnavailable
    # when it gives up.
    max_attempts = 3
    per_attempt_timeout = 45
    total_budget = 100
    started = time.time()

    for attempt in range(max_attempts):
        remaining = total_budget - (time.time() - started)
        if remaining <= 5:
            break

        future = _executor.submit(_call_gemini, prompt)
        try:
            return future.result(timeout=min(per_attempt_timeout, remaining))
        except FutureTimeoutError:
            print(f"Gemini timed out (attempt {attempt + 1}/{max_attempts})")
        except Exception as e:
            if not _retryable(e):
                raise
            print(f"Gemini temporary error (attempt {attempt + 1}/{max_attempts}): {str(e)[:200]}")
            wait = (attempt + 1) * 5
            if attempt < max_attempts - 1 and (time.time() - started) + wait < total_budget:
                time.sleep(wait)

    raise GenerationUnavailable("Gemini did not return an answer in time")

TRANSLATE_MODEL = "gemini-3.5-flash-lite"


def translate_for_retrieval(query: str):
    # Translates a Kiswahili question to English so it can be searched
    # against the English knowledge base. Returns None if anything goes
    # wrong, so the caller can fall back to the glossary query.
    prompt = (
        "Translate this health question to English. "
        "Return ONLY the translation.\n\n" + query
    )

    def call():
        return client.interactions.create(
            model=TRANSLATE_MODEL, input=prompt
        ).output_text.strip()

    future = _executor.submit(call)
    try:
        text = future.result(timeout=8)
        return text or None
    except Exception as e:
        print(f"Translation failed, using glossary query: {str(e)[:120]}")
        return None


def rag_pipeline(query: str, model, conn, history: list = None) -> dict:
    timings = {}

    # Step 1 - detect language
    t0 = time.time()
    language = detect_language(query)
    timings["language_detection"] = time.time() - t0

    # Step 2 - for Kiswahili questions, translate to English for searching.
    # Testing found the right sources more often this way than with the
    # glossary alone (7 of 7 against 5 of 7 on the test questions).
    # If the translation fails, the glossary query is used instead.
    t0 = time.time()
    english = translate_for_retrieval(query) if language == "sw" else None
    timings["translation"] = time.time() - t0

    # Step 3 - expand the query (glossary and casual-contact terms)
    # and retrieve chunks. The user's original wording is still
    # what goes into the prompt.
    t0 = time.time()
    expanded_query = expand_query(english if english else query)
    print(f"Retrieval query: {expanded_query}")
    chunks = retrieve_chunks(expanded_query, model, conn)
    timings["retrieval"] = time.time() - t0

    # Step 4 - build augmented prompt with original query and history
    t0 = time.time()
    prompt = build_prompt(query, chunks, language, history)
    timings["prompt_building"] = time.time() - t0

    # Step 5 - generate answer from Gemini
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