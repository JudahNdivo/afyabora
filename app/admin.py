import re
import requests
from flask import Blueprint, request, jsonify
from app.auth import (
    require_auth, require_admin, db, field_of, verified_totp_factors,
    SUPABASE_URL, SUPABASE_SECRET_KEY,
)
from app.session import _run

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/stats", methods=["GET"])
@require_auth
@require_admin
def admin_stats():
    # aggregate numbers only: no user, conversation or message content
    def work(conn):
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM users;")
        total_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM usage_stats;")
        total_queries = cur.fetchone()[0]

        cur.execute(
            "SELECT language, COUNT(*) FROM usage_stats "
            "GROUP BY language ORDER BY COUNT(*) DESC;"
        )
        by_language = [{"label": r[0], "count": r[1]} for r in cur.fetchall()]

        cur.execute(
            "SELECT COALESCE(disease_category, 'unknown'), COUNT(*) "
            "FROM usage_stats GROUP BY 1 ORDER BY 2 DESC;"
        )
        by_disease = [{"label": r[0], "count": r[1]} for r in cur.fetchall()]

        # created_at is stored in UTC, so convert to Nairobi time before
        # grouping by day. Days with no questions are not returned.
        cur.execute(
            """
            SELECT (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Africa/Nairobi')::date AS day,
                   COUNT(*)
            FROM usage_stats
            WHERE created_at >= (now() AT TIME ZONE 'UTC') - interval '30 days'
            GROUP BY day ORDER BY day;
            """
        )
        per_day = [{"day": r[0].isoformat(), "count": r[1]} for r in cur.fetchall()]

        # response time comes from the messages table, so conversations
        # that users deleted are not included here
        cur.execute(
            """
            SELECT AVG(latency_ms),
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)
            FROM messages
            WHERE role = 'assistant' AND latency_ms IS NOT NULL;
            """
        )
        avg_ms, median_ms = cur.fetchone()
        cur.close()

        return {
            "total_users": total_users,
            "total_queries": total_queries,
            "by_language": by_language,
            "by_disease": by_disease,
            "per_day": per_day,
            "avg_response_ms": round(float(avg_ms)) if avg_ms is not None else None,
            "median_response_ms": round(float(median_ms)) if median_ms is not None else None,
        }

    return jsonify(_run(work)), 200


def _admin_headers():
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _find_user_by_email(email):
    # exact, case-insensitive match; returns (id, email) or None. The admin
    # types the address, so no list of users is ever sent to the browser.
    def work(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email FROM auth.users WHERE lower(email) = lower(%s) LIMIT 1;",
            (email,)
        )
        row = cur.fetchone()
        cur.close()
        return row
    return _run(work)


def _write_log(admin, target_id, target_email, action):
    db.table("admin_actions").insert({
        "admin_id": admin.id,
        "admin_email": admin.email,
        "target_id": str(target_id),
        "target_email": target_email,
        "action": action,
    }).execute()


@admin_bp.route("/api/admin/reset-authenticator", methods=["POST"])
@require_auth
@require_admin
def reset_authenticator():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip()

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"error": "Enter a valid email address"}), 400

    try:
        found = _find_user_by_email(email)
    except Exception:
        return jsonify({"error": "Could not look up that account, please try again"}), 503
    if not found:
        return jsonify({"error": "No account found with that email"}), 404
    target_id, target_email = str(found[0]), found[1]

    # an administrator cannot reset their own authenticator or another
    # administrator's through this form
    if target_id == request.user.id:
        return jsonify({"error": "You cannot reset your own authenticator here"}), 403
    role = db.table("users").select("role").eq("id", target_id).execute()
    if role.data and role.data[0].get("role") == "admin":
        return jsonify({"error": "Administrator accounts cannot be reset here"}), 403

    # the account's current authenticator factors, read from the auth service
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/auth/v1/admin/users/{target_id}",
            headers=_admin_headers(), timeout=10,
        )
        resp.raise_for_status()
        factors = verified_totp_factors(resp.json())
    except Exception:
        return jsonify({"error": "Could not read that account, please try again"}), 503
    if not factors:
        return jsonify({"error": "That account has no authenticator turned on"}), 400

    # the reset is logged BEFORE it happens: if the log cannot be written,
    # nothing is reset, so there is never an unlogged reset
    try:
        _write_log(request.user, target_id, target_email, "reset_authenticator")
    except Exception as e:
        print(f"Admin log write failed: {type(e).__name__}: {e}")
        return jsonify({"error": "Could not write the audit log, so nothing was reset"}), 503

    try:
        for f in all_factors(resp.json()):
            r = requests.delete(
                f"{SUPABASE_URL}/auth/v1/admin/users/{target_id}/factors/{field_of(f, 'id')}",
                headers=_admin_headers(), timeout=10,
            )
            if r.status_code not in (200, 204):
                raise Exception(f"factor delete returned {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"Authenticator reset failed: {type(e).__name__}: {e}")
        try:
            _write_log(request.user, target_id, target_email, "reset_authenticator_failed")
        except Exception:
            pass
        return jsonify({"error": "The reset failed, please try again"}), 502

    return jsonify({"message": f"Authenticator reset for {target_email}"}), 200


def all_factors(user_json):
    # every authenticator-app factor, including unfinished setups
    return [f for f in (field_of(user_json, "factors") or [])
            if str(field_of(f, "factor_type")).lower() == "totp"]


@admin_bp.route("/api/admin/actions", methods=["GET"])
@require_auth
@require_admin
def list_actions():
    # the most recent admin actions, newest first
    result = db.table("admin_actions").select(
        "admin_email, target_email, action, created_at"
    ).order("created_at", desc=True).limit(20).execute()
    return jsonify(result.data), 200