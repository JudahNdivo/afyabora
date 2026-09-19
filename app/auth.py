import os
from functools import wraps
from flask import request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

# Used for auth operations - signup, login, verifying tokens
auth_client: Client = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)

# Used for all direct database table operations. This key bypasses
# Row Level Security, since Flask itself is the trusted backend
# enforcing authorization (via require_auth/require_admin below),
# not the browser talking to Supabase directly.
db: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def signup(email: str, password: str, username: str):
    result = auth_client.auth.sign_up({
        "email": email,
        "password": password,
    })

    if result.user is None:
        raise Exception("Signup failed, no user returned")

    db.table("users").insert({
        "id": result.user.id,
        "username": username,
        "role": "user",
    }).execute()

    return result


def login(email: str, password: str):
    result = auth_client.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })
    return result


def get_user_from_token(access_token: str):
    try:
        result = auth_client.auth.get_user(access_token)
        return result.user
    except Exception:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        user = get_user_from_token(token)

        if user is None:
            return jsonify({"error": "Invalid or expired session"}), 401

        request.user = user
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        profile = db.table("users").select("role").eq(
            "id", request.user.id
        ).single().execute()

        if profile.data is None or profile.data.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        return f(*args, **kwargs)

    return decorated