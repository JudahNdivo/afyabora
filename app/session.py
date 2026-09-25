import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def save_message(conversation_id: str, role: str, content: str,
                  language: str = None, latency_ms: int = None,
                  chunk_ids: list = None) -> str:
    """
    Saves a single message (user or assistant) to a conversation.
    Returns the new message's id.
    If chunk_ids are provided, also records which document chunks
    were used to generate this response (for assistant messages).
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO messages
            (conversation_id, role, content, language, latency_ms)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (conversation_id, role, content, language, latency_ms)
    )
    message_id = cursor.fetchone()[0]

    if chunk_ids:
        for rank, chunk_id in enumerate(chunk_ids, start=1):
            cursor.execute(
                """
                INSERT INTO query_chunk_matches
                    (message_id, chunk_id, rank)
                VALUES (%s, %s, %s);
                """,
                (message_id, chunk_id, rank)
            )

    cursor.close()
    conn.close()
    return message_id


def get_conversation_history(conversation_id: str, limit: int = 6) -> list:
    """
    Retrieves the most recent messages in a conversation, used to
    give the RAG pipeline context for follow-up questions.
    Returns them oldest-first, as (role, content) pairs.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at DESC
        LIMIT %s;
        """,
        (conversation_id, limit)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Reverse so it reads oldest to newest, as a real conversation would
    return list(reversed(rows))


def log_usage_stat(language: str, disease_category: str = None) -> None:
    """
    Logs a single anonymous usage statistic for the admin dashboard.
    Deliberately has no reference to any user, conversation, or
    message - it exists independently and survives deletions.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO usage_stats (language, disease_category)
        VALUES (%s, %s);
        """,
        (language, disease_category)
    )

    cursor.close()
    conn.close()