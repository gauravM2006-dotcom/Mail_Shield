from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import current_user, login_required

public_bp = Blueprint("public", __name__)

@public_bp.route("/")
@public_bp.route("/home")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("public.dashboard_page"))
    return render_template("pages/home.html", is_logged_in=False)

@public_bp.route("/dashboard")
@login_required
def dashboard_page():
    active_tab = request.args.get("tab", "gmail")
    if active_tab not in ("gmail", "outlook", "yahoo", "icloud"):
        active_tab = "gmail"
    return render_template("pages/dashboard.html", active_tab=active_tab, user=current_user)

@public_bp.route("/scan-all")
@login_required
def scan_all_page():
    return render_template("pages/scan_all.html", user=current_user)

@public_bp.route("/manual-scan")
@login_required
def manual_scan_page():
    return render_template("pages/manual_scan.html", user=current_user)

@public_bp.route("/history")
@login_required
def history_page():
    return render_template("pages/history.html", user=current_user)

@public_bp.route("/rules")
@login_required
def rules_page():
    return render_template("pages/rules.html", user=current_user)

@public_bp.route("/settings")
@login_required
def settings_page():
    return render_template("pages/settings.html", user=current_user)

@public_bp.route("/account")
@login_required
def account_page():
    return render_template("pages/account.html", user=current_user)

@public_bp.route("/api/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary_alias():
    from ..mail.routes import dashboard_summary
    return dashboard_summary()

@public_bp.route("/privacy")
def privacy():
    return render_template("pages/privacy.html")
@public_bp.route("/system-health")
@public_bp.route("/health")
def system_health():
    import time
    from ..db import get_db
    db_status = "operational"
    db_latency_ms = None
    try:
        t0 = time.time()
        db = get_db()
        db.command("ping")
        db_latency_ms = round((time.time() - t0) * 1000, 1)
    except Exception:
        db_status = "degraded"

    return render_template(
        "pages/system_health.html",
        db_status=db_status,
        db_latency_ms=db_latency_ms,
        is_logged_in=current_user.is_authenticated
    )

@public_bp.route("/api/system-health/status")
def system_health_status_api():
    import time
    from flask import jsonify
    from ..db import get_db
    db_ok = True
    db_latency_ms = 0.0
    try:
        t0 = time.time()
        db = get_db()
        db.command("ping")
        db_latency_ms = round((time.time() - t0) * 1000, 1)
    except Exception:
        db_ok = False
        db_latency_ms = None

    return jsonify({
        "ok": True,
        "services": {
            "engine": {"status": "operational", "version": "1.0.0", "name": "Deterministic Rule Engine"},
            "database": {"status": "operational" if db_ok else "degraded", "latency_ms": db_latency_ms, "type": "MongoDB Primary"},
            "realtime": {"status": "operational", "name": "Flask-SocketIO WebSockets"},
            "sandbox": {"status": "operational", "name": "Isolated Manual Sandbox"},
            "connectors": {"status": "operational", "providers": ["Gmail", "Outlook", "Yahoo", "iCloud"]}
        },
        "overall": "operational" if db_ok else "degraded"
    })

@public_bp.route("/terms")
def terms():
    return render_template("pages/terms.html")

@public_bp.route("/mail/connect/google/callback", methods=["GET", "POST"])
def mail_connect_google_callback_alias():
    from ..mail.routes import connect_google_callback
    return connect_google_callback()


