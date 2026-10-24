import os
import re
import time
import queue
import threading
import psycopg2
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from sentence_transformers import SentenceTransformer
from google import genai
from google.genai import types
from langdetect import detect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
GEMINI_MODEL = "gemini-3.5-flash"
TOP_K = 5

# How much the answer model reasons before it writes: None keeps the model's
# default. check_latency.py timed "low" and "minimal" on gemini-3.5-flash;
# change this only after reading the saved answers for each setting.
GENERATION_THINKING = "minimal"

# Setup Gemini client
client = genai.Client(api_key=GOOGLE_API_KEY)

# Used to enforce a hard timeout on Gemini calls, regardless of
# whether the client library itself supports a timeout parameter
_executor = ThreadPoolExecutor(max_workers=4)


def detect_language(text: str) -> str:
    # Kiswahili common words, question words, greetings and verb forms
    swahili_markers = {
        "je", "aje", "nini", "jinsi", "gani", "sasa", "mtu",
        "unaweza", "anaeza", "pata", "ni", "na", "ya", "kwa",
        "inaenezwa", "dalili", "matibabu", "ugonjwa", "dawa",
        "hospitali", "ngono", "kinga", "sindano", "damu",
        "naweza", "nawezaje", "kupata", "kupewa", "kuambukizwa", "huambukizwa",
        "zipi", "wapi", "vipi", "pia", "sana", "nataka", "kujua", "nilikuwa",
        "niaje", "mambo", "habari", "poa", "asante", "pole",
    }

    # words only, so "aje?" counts as "aje"
    words = re.findall(r"[a-z']+", text.lower())

    # a known Kiswahili word, or a Kiswahili glossary term, means Kiswahili
    for word in words:
        if word in swahili_markers or word in SW_TERMS:
            return "sw"

    # fall back to langdetect for longer queries
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


def build_prompt(query: str, chunks: list, language: str, history: list = None,
                 standalone: str = None) -> str:
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

    # the question as rewritten from the conversation, when it differs
    # from what the user typed
    asking = ""
    if standalone and standalone.strip().lower() != query.strip().lower():
        asking = (
            "\nWHAT THE USER IS ASKING (rewritten using the conversation): "
            f"{standalone}"
        )

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
            "lakini hakikisha maelezo ni rahisi kueleweka. "
            "Kwa neno gumu la mwili au la kitaalamu, weka tafsiri ya Kiingereza "
            "kwenye mabano mara ya kwanza, kwa mfano: korodani (testicles), "
            "kaswende (syphilis), uume (penis), uke (vagina). "
            "Epuka maneno kama 'kitiba', 'mhudumu wa afya' na 'ushauri wa "
            "kitaalamu'. Tumia maneno ya kawaida kama daktari, clinic, "
            "hospitali, dawa, na ushauri. Tumia sentensi fupi."
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
- If the message states something about the person's situation (for example that they are in a long-term relationship) and the previous conversation shows what they were asking about, treat it as a continuation of that question and answer for their situation using the CONTEXT. Do not treat it as an unclear message
- If the context contains partial information, share what's available and recommend visiting a health facility for more
- If the context has NO relevant information at all, say so clearly and recommend visiting a health facility
- Be empathetic and non-judgmental
- You may name medicines and vaccines (for example antibiotics or the HPV vaccine), but NEVER state doses, amounts, how often to take them, or for how long. Say that the right medicine and dose must come from a health worker.
- {language_instruction}
- End with a brief, short recommendation to seek professional care for personal medical decisions
- Do not start with a greeting or introduce yourself unless the user greeted you first.

{history_block}CONTEXT FROM VERIFIED HEALTH GUIDELINES:
{context}

USER QUESTION: {query}{asking}

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


def _gen_config():
    # thinking level for the answer model, or no special config
    if not GENERATION_THINKING:
        return None
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level=GENERATION_THINKING)
    )


def _call_gemini(prompt: str) -> str:
    # The raw, blocking Gemini call - wrapped separately so it can
    # be run in a thread with an enforced timeout. generate_content is used
    # because it answered in about 1.1s against 3.0s for the Interactions
    # API on the same prompt (check_call_latency.py).
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=_gen_config(),
    )
    return (response.text or "").strip()


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


# How long a streamed answer may stall: the wait for the first words, and the
# gap allowed between pieces after that
STREAM_FIRST_TIMEOUT = 20
STREAM_GAP_TIMEOUT = 15


def _stream_worker(prompt, out, stop):
    # Reads Gemini's streamed answer in its own thread and puts each piece of
    # text on a queue, so the caller can enforce timeouts between pieces
    stream = None
    try:
        stream = client.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=prompt,
            config=_gen_config(),
        )
        for chunk in stream:
            if stop.is_set():
                break
            # thought parts carry no text, so only the answer comes through
            if chunk.text:
                out.put(("text", chunk.text))
        out.put(("end", None))
    except Exception as e:
        out.put(("error", e))
    finally:
        try:
            if stream is not None and hasattr(stream, "close"):
                stream.close()
        except Exception:
            pass


def stream_answer(prompt: str):
    # Yields the answer in pieces as Gemini writes it. A failure before the
    # first piece is retried like generate_answer does. Once text has been
    # sent to the user a retry would repeat or contradict it, so a failure
    # after that raises GenerationUnavailable and the caller discards the
    # answer instead of saving half of it.
    max_attempts = 3
    total_budget = 100
    started = time.time()

    for attempt in range(max_attempts):
        if total_budget - (time.time() - started) <= 5:
            break

        out = queue.Queue()
        stop = threading.Event()
        threading.Thread(target=_stream_worker, args=(prompt, out, stop), daemon=True).start()
        emitted = False

        while True:
            wait = STREAM_GAP_TIMEOUT if emitted else STREAM_FIRST_TIMEOUT
            wait = max(0.1, min(wait, total_budget - (time.time() - started)))
            try:
                kind, value = out.get(timeout=wait)
            except queue.Empty:
                stop.set()
                print(f"Gemini stream stalled (attempt {attempt + 1}/{max_attempts})")
                if emitted:
                    raise GenerationUnavailable("The answer stopped part way")
                break

            if kind == "text":
                if not emitted:
                    value = value.lstrip()
                    if not value:
                        continue
                emitted = True
                yield value
            elif kind == "end":
                if emitted:
                    return
                print(f"Gemini stream ended with no text (attempt {attempt + 1}/{max_attempts})")
                break
            else:
                stop.set()
                if emitted:
                    raise GenerationUnavailable("The answer stopped part way") from value
                if not _retryable(value):
                    raise value
                print(f"Gemini temporary error (attempt {attempt + 1}/{max_attempts}): {str(value)[:200]}")
                break

        # a short pause before trying again
        pause = (attempt + 1) * 3
        if attempt < max_attempts - 1 and (time.time() - started) + pause < total_budget:
            time.sleep(pause)

    raise GenerationUnavailable("Gemini did not return an answer in time")


TRANSLATE_MODEL = "gemini-3.5-flash-lite"


FOLLOW_UP_STARTS = (
    "and ", "what about", "how about", "also ", "but ", "so ", "then ",
    "what if", "how long", "is it", "does it", "can it", "can they",
    "do they", "na ", "je kuhusu", "vipi kuhusu", "na kama",
)
REFERENCE_WORDS = {
    "it", "this", "that", "they", "them", "those", "these",
    "he", "she", "him", "her", "there", "same", "too",
}
QUESTION_WORDS = {
    "who", "what", "when", "where", "which", "how", "is", "are",
    "can", "do", "does", "did", "should", "will", "could",
}


def looks_like_follow_up(query: str, history: list) -> bool:
    # no history means nothing to refer back to
    if not history:
        return False
    q = query.strip().lower()
    words = re.findall(r"[a-z']+", q)
    if not words:
        return False
    if q.startswith(FOLLOW_UP_STARTS) or REFERENCE_WORDS & set(words):
        return True
    # a full question that refers to nothing earlier stands alone
    if words[0] in QUESTION_WORDS and len(words) > 4:
        return False
    # short or statement-like messages ("I am in a long-term relationship")
    return len(words) <= 12 and not q.endswith("?")


# Bare greetings get a fixed reply, so they need no model call at all
GREETING_WORDS = {
    "hi", "hello", "hey", "yo", "niaje", "mambo", "habari", "yako",
    "sasa", "vipi", "poa", "jambo", "hujambo", "good", "morning",
    "afternoon", "evening", "sema",
}
SW_GREETING_WORDS = {
    "niaje", "mambo", "habari", "yako", "sasa", "vipi", "poa",
    "jambo", "hujambo", "sema",
}
GREETING_REPLIES = {
    "sw": (
        "Niaje! Mimi ni AfyaBora. Naweza kukusaidia na maswali kuhusu "
        "HIV, kaswende (syphilis), kisonono (gonorrhoea), chlamydia na HPV. "
        "Uliza tu, sitakuhukumu."
    ),
    "en": (
        "Hi! I'm AfyaBora. I can help with questions about HIV, syphilis, "
        "gonorrhoea, chlamydia and HPV. Ask me anything, no judgement."
    ),
}


def greeting_reply(query: str):
    # returns (language, reply) for a bare greeting, otherwise None
    words = re.findall(r"[a-z']+", query.lower())
    if 0 < len(words) <= 3 and all(w in GREETING_WORDS for w in words):
        lang = "sw" if set(words) & SW_GREETING_WORDS else "en"
        return lang, GREETING_REPLIES[lang]
    return None


def rewrite_for_retrieval(query: str, history: list = None):
    # Turns the new message into one standalone English question for
    # searching: translates Kiswahili, and fills in what a follow-up refers
    # to using the last turns. Returns None if anything goes wrong, so the
    # caller can fall back to the glossary query.
    lines = []
    for past_question, past_answer in (history or [])[-2:]:
        lines.append(f"User: {past_question}")
        lines.append(f"Assistant: {past_answer[:200]}")
    conversation = "\n".join(lines) if lines else "(no earlier messages)"

    prompt = (
        "You help a sexual health chatbot search its guidelines.\n\n"
        f"Conversation so far:\n{conversation}\n\n"
        f"New message: {query}\n\n"
        "Rewrite the new message as ONE standalone English question that can be "
        "searched without the conversation. Rules:\n"
        "- Use the conversation to fill in what the message refers to, such as the "
        "infection, \"it\", \"that\" or the topic being discussed.\n"
        "- If the message states something about the person, for example that they "
        "are in a long-term relationship or have a new partner, turn it into a general "
        "question about protection, testing or staying healthy in that situation, "
        "related to the earlier topic. Never assume the person has an infection or "
        "needs treatment.\n"
        "- If the message is in another language, translate it to English.\n"
        "- If it is a greeting, thanks, or has nothing to do with sexual health, "
        "return it unchanged (translated if needed).\n"
        "- Return ONLY the question."
    )

    def call():
        response = client.models.generate_content(
            model=TRANSLATE_MODEL, contents=prompt
        )
        return (response.text or "").strip()

    future = _executor.submit(call)
    try:
        text = future.result(timeout=8)
        if not text:
            return None
        # keep only the first line and cap its length, so an unexpected
        # long reply cannot become the search text
        first_line = text.splitlines()[0].strip().strip('"')
        return first_line[:300] or None
    except Exception as e:
        print(f"Rewrite failed, using glossary query: {str(e)[:120]}")
        return None


def _sources(chunks):
    return [
        {
            "chunk_id": chunk[0],
            "source_file": chunk[3],
            "disease": chunk[2],
            "chunk_index": chunk[4]
        }
        for chunk in chunks
    ]


def _prepare(query, model, conn, history, timings):
    # Steps 1 to 4, shared by the normal and the streaming pipeline. Returns
    # either {"quick": (language, reply)} for a bare greeting, which needs no
    # search or model call, or the language, chunks and prompt.

    # Step 1 - detect language
    t0 = time.time()
    language = detect_language(query)
    timings["language_detection"] = time.time() - t0

    quick = greeting_reply(query)
    if quick:
        return {"quick": quick}

    # Step 2 - rewrite the message into one standalone English question for
    # searching. Kiswahili questions always need it (translation), and so can
    # a follow-up that names no infection. If the rewrite fails, the glossary
    # query is used instead.
    t0 = time.time()
    english = None
    if language == "sw" or looks_like_follow_up(query, history):
        english = rewrite_for_retrieval(query, history)
    timings["rewrite"] = time.time() - t0

    # Step 3 - expand the query (glossary and casual-contact terms)
    # and retrieve chunks
    t0 = time.time()
    expanded_query = expand_query(english if english else query)
    print(f"Retrieval query: {expanded_query}")
    # conn may be a function that returns a live connection, so it is only
    # opened or checked when a search is actually needed
    if callable(conn):
        conn = conn()
    chunks = retrieve_chunks(expanded_query, model, conn)
    timings["retrieval"] = time.time() - t0

    # Step 4 - build the prompt from the original wording, the history and
    # the rewritten question
    t0 = time.time()
    prompt = build_prompt(query, chunks, language, history, standalone=english)
    timings["prompt_building"] = time.time() - t0

    return {"language": language, "chunks": chunks, "prompt": prompt}


def _print_timings(timings):
    print("Stage timings (seconds):")
    for stage, duration in timings.items():
        print(f"  {stage}: {duration:.2f}s")
    print(f"  TOTAL: {sum(timings.values()):.2f}s")


def rag_pipeline(query: str, model, conn, history: list = None) -> dict:
    timings = {}
    prep = _prepare(query, model, conn, history, timings)

    if "quick" in prep:
        lang, reply = prep["quick"]
        return {"query": query, "language": lang, "answer": reply, "sources": []}

    # Step 5 - generate answer from Gemini
    t0 = time.time()
    answer = generate_answer(prep["prompt"])
    timings["generation"] = time.time() - t0
    _print_timings(timings)

    return {
        "query": query,
        "language": prep["language"],
        "answer": answer,
        "sources": _sources(prep["chunks"]),
    }


def rag_pipeline_stream(query: str, model, conn, history: list = None):
    # Same steps as rag_pipeline, but the answer is yielded in pieces as
    # {"type": "delta", "text": ...}; the last event is
    # {"type": "done", "result": {...}} with the whole answer, in the same
    # shape rag_pipeline returns
    timings = {}
    prep = _prepare(query, model, conn, history, timings)

    if "quick" in prep:
        lang, reply = prep["quick"]
        yield {"type": "delta", "text": reply}
        yield {"type": "done", "result": {
            "query": query, "language": lang, "answer": reply, "sources": []
        }}
        return

    t0 = time.time()
    parts = []
    first_words = None
    for piece in stream_answer(prep["prompt"]):
        if first_words is None:
            first_words = time.time() - t0
        parts.append(piece)
        yield {"type": "delta", "text": piece}
    timings["generation"] = time.time() - t0
    _print_timings(timings)
    if first_words is not None:
        print(f"  (first words reached the user {first_words:.2f}s into generation)")

    yield {"type": "done", "result": {
        "query": query,
        "language": prep["language"],
        "answer": "".join(parts).strip(),
        "sources": _sources(prep["chunks"]),
    }}


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