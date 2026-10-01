import time
from flask import Blueprint, request, jsonify
from app.auth import require_auth, db
from app.session import save_message, get_conversation_history, log_usage_stat
from scripts.generate_answer import rag_pipeline, get_connection
from sentence_transformers import SentenceTransformer

chat_bp = Blueprint("chat", __name__)

# Loaded once when this module is imported, shared across all requests
_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
_conn = get_connection()


@chat_bp.route("/api/conversations", methods=["POST"])
@require_auth
def create_conversation():
    result = db.table("conversations").insert({
        "user_id": request.user.id,
        "title": "New Chat",
    }).execute()

    return jsonify(result.data[0]), 201


@chat_bp.route("/api/conversations", methods=["GET"])
@require_auth
def list_conversations():
    result = db.table("conversations").select("*").eq(
        "user_id", request.user.id
    ).order("updated_at", desc=True).execute()

    return jsonify(result.data), 200


@chat_bp.route("/api/conversations/<conversation_id>", methods=["DELETE"])
@require_auth
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
@require_auth
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
@require_auth
def send_message(conversation_id):
    convo = db.table("conversations").select("id, title").eq(
        "id", conversation_id
    ).eq("user_id", request.user.id).execute()

    if not convo.data:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json(silent=True) or {}
    query_text = data.get("message", "").strip()

    if not query_text:
        return jsonify({"error": "message is required"}), 400

    # Get recent history for follow-up context, before saving the
    # current message so it isn't accidentally included in its own context
    history_rows = get_conversation_history(conversation_id, limit=6)
    history = [
        (content, "") for role, content in history_rows if role == "user"
    ]

    # Run the RAG pipeline, timed so we can log actual response latency.
    # Only save messages once generation succeeds, so a failed request
    # never leaves an orphaned user message.
    start_time = time.time()
    try:
        result = rag_pipeline(query_text, _model, _conn, history=history)
    except Exception as e:
        return jsonify({"error": "Failed to generate a response, please try again"}), 502
    latency_ms = int((time.time() - start_time) * 1000)

    answer = result["answer"]
    language = result["language"]
    chunk_ids = [source["chunk_id"] for source in result["sources"]]

    # Now save both messages together
    save_message(conversation_id, "user", query_text)
    save_message(
        conversation_id, "assistant", answer,
        language=language, latency_ms=latency_ms, chunk_ids=chunk_ids
    )

    # Log anonymous usage stat - disease category from the top chunk
    disease_category = None
    if result["sources"]:
        top_chunk = db.table("document_chunks").select("disease").eq(
            "id", chunk_ids[0]
        ).single().execute()
        disease_category = top_chunk.data.get("disease") if top_chunk.data else None

    log_usage_stat(language, disease_category)

    # If this was the first message, set the conversation title from it
    if convo.data[0]["title"] == "New Chat":
        new_title = query_text[:50]
        db.table("conversations").update({"title": new_title}).eq(
            "id", conversation_id
        ).execute()

    # Touch updated_at so the conversation list sorts correctly
    db.table("conversations").update({"updated_at": "now()"}).eq(
        "id", conversation_id
    ).execute()

    return jsonify({
        "answer": answer,
        "language": language,
        "latency_ms": latency_ms,
    }), 200


@chat_bp.route("/api/conversations/<conversation_id>/messages/<message_id>", methods=["PUT"])
@require_auth
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

    # Get history up to (not including) this message, for context
    history_rows = get_conversation_history(conversation_id, limit=6)
    history = [
        (content, "") for role, content in history_rows if role == "user"
    ]

    start_time = time.time()
    try:
        result = rag_pipeline(new_text, _model, _conn, history=history)
    except Exception:
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

    disease_category = None
    if result["sources"]:
        top_chunk = db.table("document_chunks").select("disease").eq(
            "id", chunk_ids[0]
        ).single().execute()
        disease_category = top_chunk.data.get("disease") if top_chunk.data else None
    log_usage_stat(language, disease_category)

    return jsonify({"answer": answer, "language": language}), 200