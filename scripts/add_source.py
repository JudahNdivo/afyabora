import os
import sys
import uuid
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from scripts.chunk_data import split_into_chunks, classify_chunk
from scripts.generate_answer import MODEL_NAME

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# usage: python -m scripts.add_source data/hiv/cleaned/hiv_gov_symptoms.txt
path = sys.argv[1]
source_name = os.path.splitext(os.path.basename(path))[0]

with open(path, "r", encoding="utf-8") as f:
    text = f.read()

chunks = split_into_chunks(text)
if not chunks:
    sys.exit("No chunks produced, the file is too short")

model = SentenceTransformer(MODEL_NAME)
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

# re-running replaces only this source, nothing else is touched
cur.execute("DELETE FROM document_chunks WHERE source_file = %s;", (source_name,))

for i, chunk in enumerate(chunks):
    disease = classify_chunk(chunk)
    vec = model.encode(chunk).tolist()
    cur.execute(
        """
        INSERT INTO document_chunks
            (id, disease, source_file, chunk_index, chunk_text, embedding)
        VALUES (%s, %s, %s, %s, %s, %s::vector);
        """,
        (str(uuid.uuid4()), disease, source_name, i, chunk, vec),
    )
    print(f"added chunk {i} tagged {disease}")

conn.close()