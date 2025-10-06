# server.py
import os
import base64
import tempfile
import eventlet
eventlet.monkey_patch()

from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room

from dotenv import load_dotenv
import openai

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

rooms = {}
user_rooms = {}
online_users = set()

@socketio.on("connect")
def on_connect():
    emit("online_users", list(online_users))

@socketio.on("register_user")
def register_user(data):
    username = data.get("username")
    online_users.add(username)
    emit("online_users", list(online_users), broadcast=True)

@socketio.on("create_room")
def create_room(data):
    user_a = data.get("from")
    user_b = data.get("to")
    room_id = f"room_{user_a}_{user_b}"
    rooms[room_id] = [user_a, user_b]
    user_rooms[user_a] = room_id
    user_rooms[user_b] = room_id
    emit("room_created", {"room_id": room_id}, to=request.sid)

@socketio.on("join_room")
def join_room_event(data):
    room_id = data.get("room_id")
    username = data.get("username")
    join_room(room_id)
    emit("status", {"msg": f"{username} joined {room_id}"}, room=room_id)

@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    room = data.get("room")
    b64_audio = data.get("chunk_base64")
    username = data.get("username")

    emit("audio_chunk", {
        "username": username,
        "chunk_base64": b64_audio
    }, room=room, include_self=False)

    # STT
    audio_bytes = base64.b64decode(b64_audio)
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_in.write(audio_bytes)
    tmp_in.close()

    transcript = ""
    try:
        with open(tmp_in.name, "rb") as f:
            transcript = openai.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f
            ).text
    except Exception as e:
        transcript = f"[Error STT: {e}]"

    emit("transcript", {
        "username": username,
        "transcript": transcript
    }, room=room, include_self=False)

    os.unlink(tmp_in.name)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
