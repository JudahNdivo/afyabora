from flask import Blueprint, request, jsonify
from app.auth import require_auth, db, field_of, verified_totp_factors

profile_bp = Blueprint("profile", __name__)


def _sign_in_methods(user):
    # which ways this account can sign in, e.g. ["email", "google"]
    meta = field_of(user, "app_metadata") or {}
    methods = meta.get("providers") or ([meta["provider"]] if meta.get("provider") else [])
    return methods or ["email"]


def _profile_response(user):
    row = db.table("users").select("username, role").eq("id", user.id).single().execute()
    data = row.data or {}
    return {
        "id": user.id,
        "email": user.email,
        "username": data.get("username"),
        "role": data.get("role", "user"),
        "sign_in_methods": _sign_in_methods(user),
        "authenticator_enabled": bool(verified_totp_factors(user)),
        "created_at": str(field_of(user, "created_at") or ""),
    }


@profile_bp.route("/api/profile", methods=["GET"])
@require_auth
def get_profile():
    try:
        return jsonify(_profile_response(request.user)), 200
    except Exception:
        return jsonify({"error": "Could not load your profile, please try again"}), 503


@profile_bp.route("/api/profile", methods=["PUT"])
@require_auth
def update_profile():
    # only the username can be changed here; the email is read-only for now
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()

    if len(username) < 2 or len(username) > 40:
        return jsonify({"error": "Username must be 2 to 40 characters"}), 400
    if any(ord(c) < 32 for c in username):
        return jsonify({"error": "Username contains invalid characters"}), 400

    try:
        db.table("users").update({"username": username}).eq(
            "id", request.user.id
        ).execute()
    except Exception:
        # most likely a username that is already taken
        return jsonify({"error": "That username could not be used, try another"}), 409

    return jsonify({"username": username}), 200


@profile_bp.route("/api/profile", methods=["DELETE"])
@require_auth
def delete_account():
    # the person must type their own email to confirm
    data = request.get_json(silent=True) or {}
    confirm = str(data.get("confirm_email", "")).strip().lower()
    if confirm != (request.user.email or "").lower():
        return jsonify({"error": "Type your email address to confirm"}), 400

    row = db.table("users").select("role").eq("id", request.user.id).single().execute()
    if row.data and row.data.get("role") == "admin":
        return jsonify({"error": "Administrator accounts cannot be deleted here"}), 403

    user_id = request.user.id
    try:
        # their conversations go first (messages are removed with them);
        # the anonymous usage stats have no link to the user and stay
        db.table("conversations").delete().eq("user_id", user_id).execute()
        db.auth.admin.delete_user(user_id)
    except Exception as e:
        print(f"Account deletion failed: {type(e).__name__}: {e}")
        return jsonify({"error": "Could not delete the account, please try again"}), 502

    # the profile row may already be gone if the database removes it
    # together with the login account
    try:
        db.table("users").delete().eq("id", user_id).execute()
    except Exception:
        pass

    return jsonify({"message": "Account deleted"}), 200