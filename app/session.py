import os
import threading
import psycopg2
from psycopg2 import pool, extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    # a single new connection, kept for scripts that want their own
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


# Opening a connection to Supabase took about 3 seconds each time, and every
# function below used to open its own. A pool opens connections once and
# reuses them, so a request only pays for the queries themselves.
_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = pool.ThreadedConnectionPool(
                1, 8, DATABASE_URL,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
        return _pool


def _run(work):
    # Runs work(conn) on a pooled connection. A pooled connection can have
    # been closed by the server while idle; that shows up as an
    # OperationalError or InterfaceError on first use, so the dead
    # connection is thrown away and the work is tried again on another.
    last_error = None
    for attempt in range(3):
        p = _get_pool()
        conn = p.getconn()
        broken = False
        try:
            conn.autocommit = True
            return work(conn)
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            broken = True
            last_error = e
            print(f"Database connection failed (attempt {attempt + 1}/3): "
                  f"{type(e).__name__}: {e}")
        finally:
            # leave the connection clean before it goes back to the pool
            try:
                if not conn.closed:
                    conn.rollback()
                    conn.autocommit = True
            except Exception:
                broken = True
            try:
                p.putconn(conn, close=broken)
            except Exception:
                pass
    raise last_error


def save_message(conversation_id: str, role: str, content: str,
                 language: str = None, latency_ms: int = None,
                 chunk_ids: list = None) -> str:
    """
    Saves a single message (user or assistant) to a conversation.
    Returns the new message's id.
    If chunk_ids are provided, also records which document chunks
    were used to generate this response (for assistant messages).
    """
    def work(conn):
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
            extras.execute_values(
                cursor,
                "INSERT INTO query_chunk_matches (message_id, chunk_id, rank) VALUES %s",
                [(message_id, chunk_id, rank)
                 for rank, chunk_id in enumerate(chunk_ids, start=1)]
            )
        cursor.close()
        return message_id

    return _run(work)


def save_exchange(conversation_id: str, user_text: str, answer: str,
                  language: str = None, latency_ms: int = None,
                  chunk_ids: list = None, title_if_new: str = None):
    """
    Saves a question, its answer and the chunk links in ONE transaction,
    so a failure can never leave a question without an answer. The same
    transaction touches the conversation's updated_at and, when
    title_if_new is given and the title is still "New Chat", sets the title.
    Returns (user_message_id, assistant_message_id).
    clock_timestamp() is used instead of the default now(), because now()
    returns the same time for every statement in a transaction and the
    question and answer would tie on created_at.
    """
    def work(conn):
        conn.autocommit = False
        cursor = conn.cursor()
        try:
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

            if chunk_ids:
                extras.execute_values(
                    cursor,
                    "INSERT INTO query_chunk_matches (message_id, chunk_id, rank) VALUES %s",
                    [(assistant_message_id, chunk_id, rank)
                     for rank, chunk_id in enumerate(chunk_ids, start=1)]
                )

            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = now(),
                    title = CASE
                        WHEN title = 'New Chat' AND %s::text IS NOT NULL
                        THEN %s::text ELSE title END
                WHERE id = %s;
                """,
                (title_if_new, title_if_new, conversation_id)
            )

            conn.commit()
            return user_message_id, assistant_message_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    return _run(work)


def get_conversation_history(conversation_id: str, limit: int = 6) -> list:
    """
    Retrieves the most recent messages in a conversation, used to
    give the RAG pipeline context for follow-up questions.
    Returns them oldest-first, as (role, content) pairs.
    """
    def work(conn):
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
        return rows

    # Reverse so it reads oldest to newest, as a real conversation would
    return list(reversed(_run(work)))


def log_usage_stat(language: str, disease_category: str = None) -> None:
    """
    Logs a single anonymous usage statistic for the admin dashboard.
    Deliberately has no reference to any user, conversation, or
    message - it exists independently and survives deletions.
    """
    def work(conn):
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO usage_stats (language, disease_category)
            VALUES (%s, %s);
            """,
            (language, disease_category)
        )
        cursor.close()

    _run(work)