from flask import Flask, request, jsonify, render_template
from app.auth import (
    signup, login, require_auth, db,
    request_password_reset, complete_password_reset,
)
from app.chat import chat_bp

app = Flask(__name__)
app.register_blueprint(chat_bp)


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    username = data.get("username", "").strip()

    if not email or not password or not username:
        return jsonify({"error": "email, password and username are required"}), 400

    try:
        result = signup(email, password, username)
        return jsonify({
            "message": "Account created",
            "user_id": result.user.id,
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

        # Fetch the profile row (username, role) to send back alongside
        # the session, so the frontend has everything in one response
        profile = db.table("users").select("username, role").eq(
            "id", result.user.id
        ).single().execute()

        return jsonify({
            "access_token": result.session.access_token,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "username": profile.data.get("username") if profile.data else None,
                "role": profile.data.get("role") if profile.data else "user",
            },
        }), 200
    except Exception as e:
        return jsonify({"error": "Invalid email or password"}), 401


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

    redirect_to = request.host_url.rstrip("/") + "/reset-password"
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


@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/chat")
def chat_page():
    return render_template("chat.html")


@app.route("/forgot-password")
def forgot_password_page():
    return render_template("forgot_password.html")


@app.route("/reset-password")
def reset_password_page():
    return render_template("reset_password.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)