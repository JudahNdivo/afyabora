from flask import Flask, request, jsonify
from app.auth import signup, login, require_auth, db
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


@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "ok", "service": "AfyaBora"}, 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)