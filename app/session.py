import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


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


def save_exchange(conversation_id: str, user_text: str, answer: str,
                  language: str = None, latency_ms: int = None,
                  chunk_ids: list = None):
    """
    Saves a question, its answer and the chunk links in ONE transaction,
    so a failure can never leave a question without an answer.
    Returns (user_message_id, assistant_message_id).
    clock_timestamp() is used instead of the default now(), because now()
    returns the same time for every statement in a transaction and the
    question and answer would tie on created_at.
    """
    last_error = None

    for attempt in range(2):
        conn = None
        try:
            conn = get_connection()
            conn.autocommit = False
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO messages
                    (conversation_id, role, content, created_at)
                VALUES (%s, 'user', %s, clock_timestamp())
                RETURNING id;
                """,
                (conversation_id, user_text)
            )
            user_message_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO messages
                    (conversation_id, role, content, language, latency_ms, created_at)
                VALUES (%s, 'assistant', %s, %s, %s, clock_timestamp())
                RETURNING id;
                """,
                (conversation_id, answer, language, latency_ms)
            )
            assistant_message_id = cursor.fetchone()[0]

            for rank, chunk_id in enumerate(chunk_ids or [], start=1):
                cursor.execute(
                    """
                    INSERT INTO query_chunk_matches
                        (message_id, chunk_id, rank)
                    VALUES (%s, %s, %s);
                    """,
                    (assistant_message_id, chunk_id, rank)
                )

            conn.commit()
            cursor.close()
            return user_message_id, assistant_message_id

        except Exception as e:
            last_error = e
            print(f"save_exchange failed (attempt {attempt + 1}/2): {type(e).__name__}: {e}")
            try:
                if conn is not None:
                    conn.rollback()
            except Exception:
                pass
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    raise last_error


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