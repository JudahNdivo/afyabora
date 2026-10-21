import os
import re
import json
import time
import base64
import requests
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
# enforcing authorization (via the decorators below), not the browser
# talking to Supabase directly.
db: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


class AuthServiceUnavailable(Exception):
    # raised when Supabase Auth could not be reached, as opposed to
    # the token being rejected
    pass


def validate_password(password: str) -> list:
    # Server-side enforcement, independent of any client-side check -
    # a direct API call (bypassing the frontend) must also obey this
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("one number")
    return errors


def signup(email: str, password: str, username: str):
    password_errors = validate_password(password)
    if password_errors:
        raise Exception(f"Password needs: {', '.join(password_errors)}")

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
    # Returns the user, or None if Supabase rejected the token.
    # Raises AuthServiceUnavailable if Supabase could not be reached,
    # so a network problem does not look like an invalid login.
    for attempt in range(2):
        try:
            result = auth_client.auth.get_user(access_token)
            return result.user
        except Exception as e:
            status = getattr(e, "status", None)
            if status in (400, 401, 403):
                return None
            # no rejection status, so treat it as a connection problem
            print(f"Auth check failed (attempt {attempt + 1}/2): {type(e).__name__}: {e}")
    raise AuthServiceUnavailable("Could not reach the authentication service")


def request_password_reset(email: str, redirect_to: str):
    auth_client.auth.reset_password_for_email(email, {"redirect_to": redirect_to})


def complete_password_reset(access_token: str, new_password: str):
    password_errors = validate_password(new_password)
    if password_errors:
        raise Exception(f"Password needs: {', '.join(password_errors)}")

    # The recovery link gives the browser a short-lived access_token
    # that's valid specifically for this one password update. We call
    # Supabase's REST API directly with it, rather than mutating the
    # shared auth_client's session, since that client is a long-lived
    # singleton shared across every request and isn't safe to swap
    # sessions on per-request.
    resp = requests.put(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Content-Type": "application/json",
        },
        json={"password": new_password},
    )
    if resp.status_code != 200:
        raise Exception("Reset link is invalid or has expired. Please request a new one.")
    return resp.json()


# ---------- authenticator app (TOTP) two-factor login ----------

def field_of(obj, key):
    # factors may arrive as objects or as plain dictionaries
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def totp_factors(user, status: str) -> list:
    # the user's authenticator-app factors with the given status
    found = []
    for f in field_of(user, "factors") or []:
        if (str(field_of(f, "factor_type")).lower() == "totp"
                and str(field_of(f, "status")).lower() == status):
            found.append(f)
    return found


def verified_totp_factors(user) -> list:
    return totp_factors(user, "verified")


def token_aal(access_token: str) -> str:
    # Reads the assurance level (aal1 = password only, aal2 = password and
    # code) from the token. The token was already verified by Supabase in
    # get_user_from_token, so this only reads a claim.
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("aal", "aal1")
    except Exception:
        return "aal1"


def _auth_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Content-Type": "application/json",
    }


def mfa_unenroll(access_token: str, factor_id: str):
    resp = requests.delete(
        f"{SUPABASE_URL}/auth/v1/factors/{factor_id}",
        headers=_auth_headers(access_token),
        timeout=10,
    )
    if resp.status_code not in (200, 204):
        print(f"MFA unenroll failed: {resp.status_code} {resp.text[:300]}")
        raise Exception("Could not turn off the authenticator")


def mfa_enroll(access_token: str, user) -> dict:
    # remove abandoned, never-confirmed factors so a new setup starts cleanly
    for f in totp_factors(user, "unverified"):
        try:
            mfa_unenroll(access_token, field_of(f, "id"))
        except Exception:
            pass

    resp = requests.post(
        f"{SUPABASE_URL}/auth/v1/factors",
        headers=_auth_headers(access_token),
        json={
            "factor_type": "totp",
            "friendly_name": f"AfyaBora {int(time.time())}",
            "issuer": "AfyaBora",
        },
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        print(f"MFA enrol failed: {resp.status_code} {resp.text[:300]}")
        raise Exception("Could not start authenticator setup")

    data = resp.json()
    totp = data.get("totp") or {}
    return {
        "factor_id": data.get("id"),
        "qr_code": totp.get("qr_code"),
        "secret": totp.get("secret"),
        "uri": totp.get("uri"),
    }


def mfa_verify(access_token: str, factor_id: str, code: str) -> dict:
    # challenge then verify; on success Supabase returns a new session
    # whose token is at the higher assurance level
    headers = _auth_headers(access_token)
    base = f"{SUPABASE_URL}/auth/v1/factors/{factor_id}"

    ch = requests.post(f"{base}/challenge", headers=headers, json={}, timeout=10)
    if ch.status_code not in (200, 201):
        print(f"MFA challenge failed: {ch.status_code} {ch.text[:300]}")
        raise Exception("Could not start verification")

    vr = requests.post(
        f"{base}/verify",
        headers=headers,
        json={"challenge_id": ch.json().get("id"), "code": code},
        timeout=10,
    )
    if vr.status_code != 200:
        print(f"MFA verify failed: {vr.status_code} {vr.text[:300]}")
        raise Exception("Invalid or expired code")
    return vr.json()


# ---------- request guards ----------

def _read_token():
    # returns (user, token, error_response)
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, None, (jsonify({"error": "Missing or invalid authorization header"}), 401)

    token = header.split(" ", 1)[1]
    try:
        user = get_user_from_token(token)
    except AuthServiceUnavailable:
        # 503, not 401, so the frontend keeps the session
        return None, None, (jsonify({"error": "Could not reach the authentication service, please try again"}), 503)

    if user is None:
        return None, None, (jsonify({"error": "Invalid or expired session"}), 401)
    return user, token, None


def require_session(f):
    # any valid session, including a password-only one that has not
    # finished the second step; used only by the code-check route
    @wraps(f)
    def decorated(*args, **kwargs):
        user, token, error = _read_token()
        if error:
            return error
        request.user = user
        request.token = token
        return f(*args, **kwargs)

    return decorated


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user, token, error = _read_token()
        if error:
            return error

        # a user with a confirmed authenticator must have passed the
        # code step; a password-only token is refused
        if verified_totp_factors(user) and token_aal(token) != "aal2":
            return jsonify({"error": "Two-factor verification required"}), 401

        request.user = user
        request.token = token
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


def require_regular_user(f):
    # chat routes are for regular users only; administrators use the dashboard
    @require_auth
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            profile = db.table("users").select("role").eq(
                "id", request.user.id
            ).single().execute()
        except Exception:
            return jsonify({"error": "Could not check your account, please try again"}), 503

        if profile.data and profile.data.get("role") == "admin":
            return jsonify({"error": "Administrator accounts cannot use the chat"}), 403

        return f(*args, **kwargs)

    return decorated