from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from ..extensions import socketio

@socketio.on("connect")
def on_connect():
    if current_user.is_authenticated:
        room_name = f"user:{current_user.id}"
        join_room(room_name)
        emit("account:status", {"status": "connected", "message": "Realtime channel established."})
    else:
        return False # Reject unauthenticated sockets

@socketio.on("disconnect")
def on_disconnect():
    if current_user.is_authenticated:
        room_name = f"user:{current_user.id}"
        leave_room(room_name)

def emit_user_event(user_id: str, event: str, payload: dict):
    """Helper to emit real-time events exclusively to the user's private room."""
    socketio.emit(event, payload, room=f"user:{user_id}")
