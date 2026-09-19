import hashlib
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def hash_phone(phone_number: str) -> str:
    # Hash phone number using SHA-256 for anonymisation
    # No personally identifiable information is stored
    return hashlib.sha256(phone_number.encode()).hexdigest()


def get_connection():
    # Create a new database connection
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def log_interaction(
    phone_number: str,
    query: str,
    response: str,
    language: str,
    latency_ms: int,
    chunk_ids: list = None
) -> None:
    # Log anonymised interaction to the query_logs table
    # Phone number is hashed before storage
    phone_hash = hash_phone(phone_number)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO query_logs
                (phone_hash, query_text, response_text, language, latency_ms)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (phone_hash, query, response, language, latency_ms)
        )
        query_log_id = cursor.fetchone()[0]

        # Record which document chunks were used to generate this
        # response, preserving retrieval rank for later evaluation
        if chunk_ids:
            for rank, chunk_id in enumerate(chunk_ids, start=1):
                cursor.execute(
                    """
                    INSERT INTO query_chunk_matches
                        (query_log_id, chunk_id, rank)
                    VALUES (%s, %s, %s);
                    """,
                    (query_log_id, chunk_id, rank)
                )

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Failed to log interaction: {e}")


def get_session_history(phone_number: str, limit: int = 3) -> list:
    # Retrieve recent conversation history for a user
    # Used for multi-turn conversation context
    phone_hash = hash_phone(phone_number)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT query_text, response_text, created_at
            FROM query_logs
            WHERE phone_hash = %s
            ORDER BY created_at DESC
            LIMIT %s;
            """,
            (phone_hash, limit)
        )
        history = cursor.fetchall()
        cursor.close()
        conn.close()
        return history
    except Exception as e:
        print(f"Failed to get session history: {e}")
        return []