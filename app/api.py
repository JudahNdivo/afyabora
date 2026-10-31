import os
import re
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template, redirect, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from app.auth import (
    signup, login, require_auth, require_session, db,
    request_password_reset, complete_password_reset,
    AuthServiceUnavailable, get_user_from_token,
    verified_totp_factors, field_of,
    mfa_enroll, mfa_verify, mfa_unenroll,
    SUPABASE_URL,
)
from app.chat import chat_bp
from app.admin import admin_bp
from app.profile import profile_bp

app = Flask(__name__)
# behind Render's proxy, so links are built with https and the real host
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.register_blueprint(chat_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(profile_bp)


def _session_response(access_token, user):
    # the token plus the profile, so the frontend has everything at once
    profile = db.table("users").select("username, role").eq(
        "id", user.id
    ).single().execute()
    data = profile.data or {}
    return {
        "access_token": access_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": data.get("username"),
            "role": data.get("role", "user"),
        },
    }


def _finish_login(token, user):
    # shared by password login and Google login: a user with a confirmed
    # authenticator still has to enter a code before the login is complete
    factors = verified_totp_factors(user)
    if factors:
        return jsonify({
            "mfa_required": True,
            "mfa_token": token,
            "factor_id": field_of(factors[0], "id"),
        }), 200
    return jsonify(_session_response(token, user)), 200


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    username = data.get("username", "").strip()

    if not email or not password or not username:
        return jsonify({"error": "email, password and username are required"}), 400

    base = (os.getenv("FRONTEND_URL") or request.host_url).rstrip("/")
    try:
        result = signup(email, password, username, redirect_to=base + "/auth/callback")
        return jsonify({
            "message": "Account created",
            # true when Supabase is waiting for the email link to be clicked
            "needs_confirmation": result.session is None,
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    try:
        result = login(email, password)
        token = result.session.access_token
        user = get_user_from_token(token) or result.user
        return _finish_login(token, user)
    except AuthServiceUnavailable:
        return jsonify({"error": "Could not reach the authentication service, please try again"}), 503
    except Exception as e:
        if "not confirmed" in str(e).lower():
            return jsonify({"error": "Please confirm your email first. Check your inbox for the link."}), 403
        return jsonify({"error": "Invalid email or password"}), 401

@app.route("/api/auth/google", methods=["GET"])
def api_google_start():
    # sends the browser to Supabase, which sends it on to Google
    base = (os.getenv("FRONTEND_URL") or request.host_url).rstrip("/")
    target = (
        f"{SUPABASE_URL}/auth/v1/authorize?provider=google"
        f"&redirect_to={quote(base + '/auth/callback', safe='')}"
    )
    return redirect(target)


def _ensure_profile(user):
    # accounts created through Google never went through signup, so the
    # profile row (username and role) is made the first time they appear
    existing = db.table("users").select("id").eq("id", user.id).execute()
    if existing.data:
        return

    meta = field_of(user, "user_metadata") or {}
    name = (meta.get("full_name") or meta.get("name")
            or (user.email or "user").split("@")[0]).strip()[:40] or "user"

    # a second try with a short suffix, in case usernames must be unique
    for username in (name, f"{name}-{user.id[:4]}"):
        try:
            db.table("users").insert({
                "id": user.id,
                "username": username,
                "role": "user",
            }).execute()
            return
        except Exception as e:
            print(f"Profile insert failed for {username}: {str(e)[:120]}")
    raise Exception("Could not create the profile")


@app.route("/api/google-login", methods=["POST"])
@require_session
def api_google_login():
    # the browser sends the session Supabase gave it after Google sign-in
    try:
        _ensure_profile(request.user)
    except Exception:
        return jsonify({"error": "Could not set up your account, please try again"}), 502
    return _finish_login(request.token, request.user)


@app.route("/api/mfa/verify", methods=["POST"])
@require_session
def api_mfa_verify():
    # used both to finish a login and to confirm a new authenticator;
    # the token in the header is the password-only one
    data = request.get_json(silent=True) or {}
    factor_id = str(data.get("factor_id", "")).strip()
    code = str(data.get("code", "")).strip()

    if not factor_id or not re.fullmatch(r"\d{6}", code):
        return jsonify({"error": "factor_id and a 6-digit code are required"}), 400

    try:
        session = mfa_verify(request.token, factor_id, code)
        new_token = session.get("access_token")
        user = get_user_from_token(new_token) if new_token else None
        if user is None:
            raise Exception("no session returned")
        return jsonify(_session_response(new_token, user)), 200
    except Exception:
        # 400 and not 401, so a wrong code does not log the user out
        return jsonify({"error": "Invalid or expired code"}), 400


@app.route("/api/mfa/status", methods=["GET"])
@require_auth
def api_mfa_status():
    factors = verified_totp_factors(request.user)
    return jsonify({
        "enabled": bool(factors),
        "factor_id": field_of(factors[0], "id") if factors else None,
    }), 200


@app.route("/api/mfa/enroll", methods=["POST"])
@require_auth
def api_mfa_enroll():
    if verified_totp_factors(request.user):
        return jsonify({"error": "Authenticator login is already on"}), 409
    try:
        return jsonify(mfa_enroll(request.token, request.user)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/mfa/disable", methods=["POST"])
@require_auth
def api_mfa_disable():
    # require_auth already insists on a code-verified session here
    factors = verified_totp_factors(request.user)
    if not factors:
        return jsonify({"error": "Authenticator login is not on"}), 400
    try:
        for f in factors:
            mfa_unenroll(request.token, field_of(f, "id"))
        return jsonify({"message": "Authenticator login turned off"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/me", methods=["GET"])
@require_auth
def api_me():
    # request.user is attached by the require_auth decorator
    profile = db.table("users").select("username, role").eq(
        "id", request.user.id
    ).single().execute()

    return jsonify({
        "id": request.user.id,
        "email": request.user.email,
        "username": profile.data.get("username") if profile.data else None,
        "role": profile.data.get("role") if profile.data else "user",
    }), 200


@app.route("/api/forgot-password", methods=["POST"])
def api_forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"error": "email is required"}), 400

    base = (os.getenv("FRONTEND_URL") or request.host_url).rstrip("/")
    redirect_to = base + "/reset-password"
    try:
        request_password_reset(email, redirect_to)
    except Exception:
        pass  # fall through to the same response either way, see note below

    # Always return the same message regardless of whether the email
    # actually has an account - revealing that would let someone probe
    # for which emails are registered users (user enumeration)
    return jsonify({
        "message": "If an account exists for that email, a reset link has been sent."
    }), 200


@app.route("/api/reset-password", methods=["POST"])
def api_reset_password():
    data = request.get_json(silent=True) or {}
    access_token = data.get("access_token", "")
    new_password = data.get("new_password", "")

    if not access_token or not new_password:
        return jsonify({"error": "access_token and new_password are required"}), 400

    try:
        complete_password_reset(access_token, new_password)
        return jsonify({"message": "Password updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "ok", "service": "AfyaBora"}, 200


@app.route("/forgot-password")
def forgot_password_page():
    return render_template("forgot_password.html")


@app.route("/reset-password")
def reset_password_page():
    return render_template("reset_password.html")


# the built React app; any path that is not an API route gets index.html
DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def react_app(path):
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    if path and os.path.isfile(os.path.join(DIST, path)):
        return send_from_directory(DIST, path)
    return send_from_directory(DIST, "index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)