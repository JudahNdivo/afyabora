import os
import sys
import time
import statistics
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer
from scripts.generate_answer import (
    client as gemini, build_prompt, retrieve_chunks,
    get_connection, detect_language, MODEL_NAME,
)

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

if "--list" in sys.argv:
    for m in groq_client.models.list().data:
        print(m.id)
    sys.exit()

# provider, model id, seconds to wait between calls
CANDIDATES = [
    ("gemini", "gemini-3.5-flash", 2),
    ("gemini", "gemini-3.5-flash-lite", 2),
]

QUERIES = [
    "How is syphilis transmitted?",
    "What is HPV?",
    "Ni aje mtu anaeza pata ugonjwa wa kaswende?",
    "Nilikuwa nataka kujua how someone gets HPV",
]
RUNS = 2


def ask(provider, name, prompt):
    if provider == "gemini":
        return gemini.interactions.create(model=name, input=prompt).output_text
    r = groq_client.chat.completions.create(
        model=name, messages=[{"role": "user", "content": prompt}]
    )
    return r.choices[0].message.content


model = SentenceTransformer(MODEL_NAME)
conn = get_connection()

# build each prompt once so every model gets identical input
prompts = []
for q in QUERIES:
    chunks = retrieve_chunks(q, model, conn)
    prompts.append((q, build_prompt(q, chunks, detect_language(q), None)))

# new file name so the earlier Groq results are not overwritten
with open("benchmark_results_gemini.txt", "w", encoding="utf-8") as f:
    for provider, name, pause in CANDIDATES:
        times, words = [], []
        for q, p in prompts:
            for _ in range(RUNS):
                t0 = time.time()
                try:
                    out = ask(provider, name, p)
                except Exception as e:
                    print(f"{name}: error {str(e)[:400]}", flush=True)
                    time.sleep(pause)
                    continue
                secs = time.time() - t0
                times.append(secs)
                words.append(len(out.split()))
                print(f"{name} | {q[:35]} | {secs:.1f}s", flush=True)
                f.write(f"=== {name} | {q} | {secs:.1f}s\n{out}\n\n")
                f.flush()
                time.sleep(pause)
        if times:
            print(f"{name}: median {statistics.median(times):.1f}s, "
                  f"max {max(times):.1f}s, avg words {statistics.mean(words):.0f}", flush=True)