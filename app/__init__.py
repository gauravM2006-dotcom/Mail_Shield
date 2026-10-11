import os
import datetime
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask.json.provider import DefaultJSONProvider
from flask_login import current_user
from bson import ObjectId
from config import config_by_name
from .extensions import socketio, login_manager, csrf, limiter, mail_ext, scheduler
from .db import get_db, create_indexes, users_col
from .auth.models import User

class MongoJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

def create_app(config_name: str = None) -> Flask:
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")
        
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.json = MongoJSONProvider(app)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))
    
    # Initialize extensions
    socketio.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    mail_ext.init_app(app)
    
    # Initialize OAuth
    from .auth.oauth import init_oauth
    init_oauth(app)
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        if not user_id:
            return None
        try:
            doc = users_col().find_one({"_id": ObjectId(user_id)})
            if doc:
                return User.from_doc(doc)
        except Exception:
            return None
        return None

    # Global context processor for time-based salutation
    @app.context_processor
    def inject_salutation():
        hour = datetime.datetime.now().hour
        if 5 <= hour < 12:
            salutation = "Good morning"
        elif 12 <= hour < 17:
            salutation = "Good afternoon"
        else:
            salutation = "Good evening"
        return {"salutation": salutation}

    # Health check route
    @app.route("/healthz")
    def healthz():
        try:
            db = get_db()
            db.command("ping")
            return jsonify({"status": "ok", "db": True})
        except Exception as e:
            return jsonify({"status": "error", "db": False, "error": str(e)}), 500

    # CSRF Token endpoint for single page fetch requests
    @app.route("/api/csrf-token")
    def get_csrf():
        from flask_wtf.csrf import generate_csrf
        return jsonify({"ok": True, "csrf_token": generate_csrf()})

    # Register blueprints
    from .public.routes import public_bp
    from .auth.routes import auth_bp
    from .mail.routes import mail_bp
    from .scan.routes import scan_bp
    from .history.routes import history_bp
    from .rules.routes import rules_bp
    from .settings.routes import settings_bp
    from .account.routes import account_bp
    from .webhooks.routes import webhooks_bp
    from .realtime import events

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(mail_bp, url_prefix="/api/mail")
    app.register_blueprint(scan_bp, url_prefix="/api/scan")
    app.register_blueprint(history_bp, url_prefix="/api/history")
    app.register_blueprint(rules_bp, url_prefix="/api/rules")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")
    app.register_blueprint(account_bp, url_prefix="/api/account")
    app.register_blueprint(webhooks_bp, url_prefix="/webhooks")

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"code": "not_found", "message": "Resource not found"}}), 404
        return render_template("pages/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Forbidden"}}), 403
        return render_template("pages/403.html"), 403

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"code": "internal_error", "message": "Internal server error"}}), 500
        return render_template("pages/500.html"), 500

    with app.app_context():
        try:
            create_indexes()
        except Exception as err:
            app.logger.warning(f"Database index creation deferred: {err}")

    return app
