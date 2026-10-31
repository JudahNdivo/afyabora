# stage 1: build the React app
FROM node:20-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# stage 2: the Flask app, serving the built React files
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 HF_HOME=/srv/hf

# CPU-only torch is far smaller than the default build
RUN pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# download the embedding model now, so the server does not fetch it on start
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY app ./app
COPY scripts ./scripts
COPY --from=frontend /web/dist ./frontend/dist

# one worker (the model is about 750 MB), many threads for streaming answers
CMD gunicorn app.api:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 120