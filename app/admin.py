from flask import Blueprint, jsonify
from app.auth import require_auth, require_admin
from app.session import get_connection

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/stats", methods=["GET"])
@require_auth
@require_admin
def admin_stats():
    # aggregate numbers only: no user, conversation or message content
    conn = get_connection()
    try:
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
        return jsonify({
            "total_users": total_users,
            "total_queries": total_queries,
            "by_language": by_language,
            "by_disease": by_disease,
            "per_day": per_day,
            "avg_response_ms": round(float(avg_ms)) if avg_ms is not None else None,
            "median_response_ms": round(float(median_ms)) if median_ms is not None else None,
        }), 200
    finally:
        conn.close()