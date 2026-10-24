import time
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
import json
from flask import Blueprint, request, jsonify, Response, stream_with_context
from app.auth import require_regular_user, db
from app.session import (
    save_message, save_exchange, get_conversation_history, log_usage_stat,
)
from scripts.generate_answer import rag_pipeline, rag_pipeline_stream, get_connection
from sentence_transformers import SentenceTransformer

chat_bp = Blueprint("chat", __name__)

# Loaded once when this module is imported, shared across all requests
_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# The database connection used for retrieval. It is opened on first use
# and checked before a request when it has been idle for a while, because
# Supabase can drop an idle or unstable connection and a dead one would
# otherwise fail every later request until the server was restarted.
_conn = None
_conn_checked_at = 0.0
_conn_lock = threading.Lock()
# small pool so independent database reads can run at the same time
_io = ThreadPoolExecutor(max_workers=4)
CONN_CHECK_EVERY = 20  # seconds


def get_live_conn():
    global _conn, _conn_checked_at
    with _conn_lock:
        # a connection used a moment ago is trusted, which saves a
        # round trip to the database on every message
        if _conn is not None and time.time() - _conn_checked_at < CONN_CHECK_EVERY:
            return _conn
        try:
            cursor = _conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.close()
        except Exception:
            if _conn is not None:
                print("Database connection was stale, reconnecting")
            try:
                _conn.close()
            except Exception:
                pass
            _conn = get_connection()
        _conn_checked_at = time.time()
        return _conn


def lap(label, since):
    # prints how long a step took and returns the new start time
    now = time.time()
    print(f"  chat.py {label}: {now - since:.2f}s")
    return now


def build_history(rows, max_pairs=3, answer_chars=300):
    # turns (role, content) rows, oldest first, into (question, answer)
    # pairs for the prompt, keeping only the last few and a short piece
    # of each answer
    pairs = []
    pending = None
    for role, content in rows:
        if role == "user":
            pending = content
        elif role == "assistant" and pending is not None:
            pairs.append((pending, (content or "")[:answer_chars]))
            pending = None
    return pairs[-max_pairs:]


def log_stat_in_background(language, disease_category):
    # the anonymous usage stat is not needed for the reply, so it is
    # written after the response has gone out
    def run():
        try:
            log_usage_stat(language, disease_category)
        except Exception:
            traceback.print_exc()
    threading.Thread(target=run, daemon=True).start()


@chat_bp.route("/api/conversations", methods=["POST"])
@require_regular_user
def create_conversation():
    result = db.table("conversations").insert({
        "user_id": request.user.id,
        "title": "New Chat",
    }).execute()

    return jsonify(result.data[0]), 201


@chat_bp.route("/api/conversations", methods=["GET"])
@require_regular_user
def list_conversations():
    result = db.table("conversations").select("*").eq(
        "user_id", request.user.id
    ).order("updated_at", desc=True).execute()

    return jsonify(result.data), 200


@chat_bp.route("/api/conversations/<conversation_id>", methods=["DELETE"])
@require_regular_user
def delete_conversation(conversation_id):
    # Confirm this conversation actually belongs to the requesting user
    # before deleting, so one user can't delete another's conversation
    convo = db.table("conversations").select("id").eq(
        "id", conversation_id
    ).eq("user_id", request.user.id).execute()

    if not convo.data:
        return jsonify({"error": "Conversation not found"}), 404

    # Cascading foreign keys handle deleting its messages automatically
    db.table("conversations").delete().eq("id", conversation_id).execute()

    return jsonify({"message": "Conversation deleted"}), 200


@chat_bp.route("/api/conversations/<conversation_id>/messages", methods=["GET"])
@require_regular_user
def get_messages(conversation_id):
    convo = db.table("conversations").select("id").eq(
        "id", conversation_id
    ).eq("user_id", request.user.id).execute()

    if not convo.data:
        return jsonify({"error": "Conversation not found"}), 404

    result = db.table("messages").select("*").eq(
        "conversation_id", conversation_id
    ).order("created_at").execute()

    return jsonify(result.data), 200


@chat_bp.route("/api/conversations/<conversation_id>/messages", methods=["POST"])
@require_regular_user
def send_message(conversation_id):
    t = time.time()
    # the history read does not depend on the ownership check, so it starts
    # now and runs while the check does; its result is only used if the
    # conversation belongs to this user
    history_future = _io.submit(get_conversation_history, conversation_id, 6)

    convo = db.table("conversations").select("id, title").eq(
        "id", conversation_id
    ).eq("user_id", request.user.id).execute()
    t = lap("conversation lookup", t)

    if not convo.data:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json(silent=True) or {}
    query_text = data.get("message", "").strip()

    if not query_text:
        return jsonify({"error": "message is required"}), 400

    # Run the RAG pipeline, timed so we can log actual response latency.
    # Nothing is saved until generation succeeds, so a failed request
    # leaves no trace in the conversation.
    start_time = time.time()
    try:
        # recent history for follow-up context, read before this message
        # is saved so it isn't included in its own context
        history = build_history(history_future.result())
        t = lap("history fetch (wait)", t)
        # the connection is passed as a function, so a reply that needs no
        # search (a greeting) never opens or checks it
        result = rag_pipeline(query_text, _model, get_live_conn, history=history)
        t = lap("pipeline", t)
    except Exception:
        # print the full error in the server terminal so failures can be diagnosed
        traceback.print_exc()
        return jsonify({"error": "Failed to generate a response, please try again"}), 502
    latency_ms = int((time.time() - start_time) * 1000)

    answer = result["answer"]
    language = result["language"]
    chunk_ids = [source["chunk_id"] for source in result["sources"]]

    # Save the question and answer together, in one transaction. The same
    # transaction sets the title on the first message and touches
    # updated_at, so the conversation list sorts correctly.
    title_if_new = query_text[:50] if convo.data[0]["title"] == "New Chat" else None
    try:
        user_message_id, assistant_message_id = save_exchange(
            conversation_id, query_text, answer,
            language=language, latency_ms=latency_ms, chunk_ids=chunk_ids,
            title_if_new=title_if_new
        )
        t = lap("save exchange", t)
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Could not save your message, please try again"}), 502

    # The exchange is saved, so a failure here must not turn a successful
    # answer into an error
    try:
        # disease label of the top retrieved chunk, for the anonymous stat
        disease_category = result["sources"][0]["disease"] if result["sources"] else None
        log_stat_in_background(language, disease_category)
    except Exception:
        traceback.print_exc()

    return jsonify({
        "answer": answer,
        "language": language,
        "latency_ms": latency_ms,
        "user_message_id": user_message_id,
        "assistant_message_id": assistant_message_id,
    }), 200


@chat_bp.route("/api/conversations/<conversation_id>/messages/stream", methods=["POST"])
@require_regular_user
def send_message_stream(conversation_id):
    # Same as send_message, but the answer is sent to the browser as it is
    # written: one JSON object per line, {"type": "delta", "text": ...} for
    # each piece, then {"type": "done", ...} once the exchange is saved, or
    # {"type": "error", ...}. Nothing is saved unless the whole answer arrives.
    history_future = _io.submit(get_conversation_history, conversation_id, 6)

    convo = db.table("conversations").select("id, title").eq(
        "id", conversation_id
    ).eq("user_id", request.user.id).execute()

    if not convo.data:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json(silent=True) or {}
    query_text = data.get("message", "").strip()

    if not query_text:
        return jsonify({"error": "message is required"}), 400

    title_if_new = query_text[:50] if convo.data[0]["title"] == "New Chat" else None

    def line(obj):
        return json.dumps(obj) + "\n"

    def generate():
        start_time = time.time()
        result = None
        try:
            history = build_history(history_future.result())
            for event in rag_pipeline_stream(query_text, _model, get_live_conn, history=history):
                if event["type"] == "delta":
                    yield line(event)
                else:
                    result = event["result"]
        except Exception:
            traceback.print_exc()
            yield line({"type": "error", "error": "Failed to generate a response, please try again"})
            return

        latency_ms = int((time.time() - start_time) * 1000)
        answer = result["answer"]
        language = result["language"]
        chunk_ids = [source["chunk_id"] for source in result["sources"]]

        try:
            user_message_id, assistant_message_id = save_exchange(
                conversation_id, query_text, answer,
                language=language, latency_ms=latency_ms, chunk_ids=chunk_ids,
                title_if_new=title_if_new
            )
        except Exception:
            traceback.print_exc()
            yield line({"type": "error", "error": "Could not save your message, please try again"})
            return

        try:
            disease_category = result["sources"][0]["disease"] if result["sources"] else None
            log_stat_in_background(language, disease_category)
        except Exception:
            traceback.print_exc()

        yield line({
            "type": "done",
            "answer": answer,
            "language": language,
            "latency_ms": latency_ms,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        })

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        # tell proxies not to hold the answer back until it is complete
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@chat_bp.route("/api/conversations/<conversation_id>/messages/<message_id>", methods=["PUT"])
@require_regular_user
def edit_message(conversation_id, message_id):
    convo = db.table("conversations").select("id").eq(
        "id", conversation_id
    ).eq("user_id", request.user.id).execute()

    if not convo.data:
        return jsonify({"error": "Conversation not found"}), 404

    # Confirm the message exists, belongs to this conversation, and is
    # actually a user message - only user messages can be edited
    message = db.table("messages").select("id, role, created_at").eq(
        "id", message_id
    ).eq("conversation_id", conversation_id).execute()

    if not message.data or message.data[0]["role"] != "user":
        return jsonify({"error": "Message not found or not editable"}), 404

    data = request.get_json(silent=True) or {}
    new_text = data.get("message", "").strip()

    if not new_text:
        return jsonify({"error": "message is required"}), 400

    # Find the assistant message that immediately follows this one,
    # so we can update it in place rather than creating a duplicate
    original_created_at = message.data[0]["created_at"]
    following = db.table("messages").select("id").eq(
        "conversation_id", conversation_id
    ).eq("role", "assistant").gt(
        "created_at", original_created_at
    ).order("created_at").limit(1).execute()

    start_time = time.time()
    try:
        # History is only the messages BEFORE the one being edited, so the
        # old wording and its old answer do not leak into the new answer
        earlier = db.table("messages").select("role, content").eq(
            "conversation_id", conversation_id
        ).lt("created_at", original_created_at).order(
            "created_at", desc=True
        ).limit(6).execute()
        history_rows = [
            (m["role"], m["content"]) for m in reversed(earlier.data or [])
        ]
        history = build_history(history_rows)
        result = rag_pipeline(new_text, _model, get_live_conn, history=history)
    except Exception:
        # print the full error in the server terminal so failures can be diagnosed
        traceback.print_exc()
        return jsonify({"error": "Failed to regenerate response, please try again"}), 502
    latency_ms = int((time.time() - start_time) * 1000)

    answer = result["answer"]
    language = result["language"]
    chunk_ids = [source["chunk_id"] for source in result["sources"]]

    # Update the user's message text
    db.table("messages").update({"content": new_text}).eq("id", message_id).execute()

    if following.data:
        # Update the existing assistant response in place
        assistant_message_id = following.data[0]["id"]
        db.table("messages").update({
            "content": answer, "language": language, "latency_ms": latency_ms
        }).eq("id", assistant_message_id).execute()

        # Clear old chunk matches and log the new ones
        db.table("query_chunk_matches").delete().eq(
            "message_id", assistant_message_id
        ).execute()
        for rank, chunk_id in enumerate(chunk_ids, start=1):
            db.table("query_chunk_matches").insert({
                "message_id": assistant_message_id,
                "chunk_id": chunk_id,
                "rank": rank
            }).execute()
    else:
        # No following assistant message existed (shouldn't normally
        # happen) - create one
        save_message(
            conversation_id, "assistant", answer,
            language=language, latency_ms=latency_ms, chunk_ids=chunk_ids
        )

    try:
        disease_category = result["sources"][0]["disease"] if result["sources"] else None
        log_stat_in_background(language, disease_category)
    except Exception:
        traceback.print_exc()

    return jsonify({"answer": answer, "language": language}), 200