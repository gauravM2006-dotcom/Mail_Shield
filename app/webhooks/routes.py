import os
from flask import Blueprint, request, Response, jsonify
from ..extensions import csrf

webhooks_bp = Blueprint("webhooks", __name__)

# Exempt webhooks from CSRF verification
csrf.exempt(webhooks_bp)

@webhooks_bp.route("/gmail", methods=["POST"])
def gmail_webhook():
    # Pub/Sub push notification endpoint
    data = request.get_json() or {}
    message = data.get("message", {})
    # Return 204 immediately per blueprint Section 11.3
    return Response(status=204)

@webhooks_bp.route("/graph", methods=["POST"])
def graph_webhook():
    # Microsoft Graph validation handshake (?validationToken=...)
    val_token = request.args.get("validationToken")
    if val_token:
        return Response(val_token, mimetype="text/plain", status=200)

    # Change notification payload
    data = request.get_json() or {}
    return Response(status=202)
