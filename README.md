# AfyaBora

A bilingual (English/Kiswahili) STI health education chatbot for youth in Nairobi, built using Retrieval-Augmented Generation. Answers questions on HIV, syphilis, gonorrhoea, chlamydia, and HPV, grounded strictly in verified NASCOP, WHO, and CDC guidelines — never the model's own general knowledge.


## Stack

Flask · Supabase (PostgreSQL + pgvector + Auth) · Gemini · Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`)

## What's Built

- RAG pipeline: retrieval, prompt construction, grounded generation
- English/Kiswahili support, with informal/Sheng-friendly tone for Kiswahili
- Auth, persistent multi-turn conversations, follow-up context
- Chunk-level source traceability per response
- Anonymous usage logging for future admin reporting

## What's Next

Frontend (chat UI, history, search) · admin dashboard · Google sign-in · 2FA · deployment

## Setup

```
pip install -r requirements.txt
```

Create `.env`:
```
DATABASE_URL=
GOOGLE_API_KEY=
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
```

Build the knowledge base:
```
python scripts/process_pdfs.py
python scripts/chunk_data.py
python scripts/embed_chunks.py
```

Run it:
```
python run.py
```
