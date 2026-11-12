# AfyaBora

A bilingual (English/Kiswahili) STI health education chatbot for youth in Nairobi, built using Retrieval-Augmented Generation. It answers questions on HIV, syphilis, gonorrhoea, chlamydia and HPV using passages from WHO, CDC and Kenyan national guidelines, instead of relying on the language model's general knowledge. It gives general health information only and does not replace a clinic.

Live demo: https://afyabora-y1up.onrender.com

## Stack

- Backend: Flask, served by gunicorn in production
- Database and login: Supabase (PostgreSQL with pgvector, Supabase Auth)
- Frontend: React, Vite and Bootstrap
- Language model: Gemini (gemini-3.5-flash for answers, gemini-3.5-flash-lite for query rewriting)
- Embeddings: Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions)

## How it works

A question is language-detected, rewritten into a standalone English search query when needed (Kiswahili questions and follow-ups), matched against the knowledge base by vector search (top five passages), and answered by Gemini using only those passages. Answers stream to the browser. Every exchange is saved with the passages used, so answers can be traced to their sources.

## Setup

You need Python 3.12 or later, Node 20 or later, and a Supabase project.

1. Clone the repository and create a virtual environment.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Create a `.env` file in the project folder with these variables (values come from your own accounts and are never committed):

```
DATABASE_URL=
GOOGLE_API_KEY=
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
FRONTEND_URL=
```

`FRONTEND_URL` is the address the site is served from, for example `http://localhost:5173` while developing. Use the Supabase session pooler address for `DATABASE_URL` when running on a host that cannot reach the direct address.

3. Create the database tables by running `schema.sql` in the Supabase SQL editor (this also enables the pgvector extension).

4. Build the knowledge base from the PDFs in the data folder:

```
python scripts/process_pdfs.py
python scripts/chunk_data.py
python scripts/embed_chunks.py
```

## Run

Development, with two terminals:

```
python run.py
```

```
cd frontend
npm install
npm run dev
```

Open the address that Vite prints. Requests to `/api` are forwarded to Flask on port 5000.

Single server, as in production:

```
cd frontend
npm run build
cd ..
python run.py
```

Flask then serves the built frontend and the API together on port 5000.

## First administrator

Sign up through the site, then set that user's `role` to `admin` in the `users` table in Supabase. Further administrators are added from the Administrators page.

## Deployment

The `Dockerfile` builds the React frontend, installs the Python dependencies with the CPU build of PyTorch, bakes in the embedding model and starts gunicorn. The live site runs it as a Docker web service on Render, which redeploys automatically when a change is merged to `main`. Set the environment variables above in Render, and add the service address to Supabase under Authentication, URL Configuration. The `/health` address reports service status.

## Evaluation and tests

The `evaluation` folder holds the model benchmark, latency and retrieval coverage scripts and their saved results. `check_answers.py`, `check_call_latency.py` and `check_429.py` in the project root are quick checks for answer quality, call latency and rate limits.

## Project

Final year project for the BSc Informatics and Computer Science at Strathmore University. 
All rights reserved. The source documents in the knowledge base belong to their publishers.
