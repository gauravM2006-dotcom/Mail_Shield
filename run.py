import os
from app import create_app
from app.extensions import socketio

app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    # Run with Socket.IO web server
    socketio.run(app, host="0.0.0.0", port=port, debug=app.config.get("DEBUG", True), allow_unsafe_werkzeug=True)
