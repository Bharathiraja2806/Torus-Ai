import os
from datetime import datetime, timedelta, timezone

import jwt
from flask import Flask, jsonify, request
from flask_cors import CORS
from groq import Groq
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    add_message,
    create_chat,
    create_user,
    delete_chat,
    get_chat,
    get_user_by_id,
    get_user_by_username,
    init_db,
    list_chats,
    list_messages,
    rename_chat,
    update_user_password,
)

app = Flask(__name__)
CORS(app)

SECRET = os.getenv("JWT_SECRET", "supersecretkey")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
SYSTEM_PROMPT = (
    "You are a helpful, polished AI assistant. Give clear, practical, "
    "friendly answers in markdown when it helps."
)

init_db()


def issue_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def get_authenticated_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None

    return get_user_by_id(payload["user_id"])


def require_json(keys):
    payload = request.get_json(silent=True) or {}
    missing = [key for key in keys if not str(payload.get(key, "")).strip()]
    if missing:
        return None, jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    return payload, None, None


def chat_belongs_to_user(chat_id: int, user_id: int) -> bool:
    chat = get_chat(chat_id)
    return bool(chat and chat.user_id == user_id)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/register")
def register():
    data, error_response, status = require_json(["username", "password"])
    if error_response:
        return error_response, status

    username = data["username"].strip()
    password = data["password"]

    if get_user_by_username(username):
        return jsonify({"error": "Username already exists"}), 409

    user = create_user(username, generate_password_hash(password))
    token = issue_token(user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@app.post("/login")
def login():
    data, error_response, status = require_json(["username", "password"])
    if error_response:
        return error_response, status

    user = get_user_by_username(data["username"].strip())
    if user is None:
        return jsonify({"error": "Invalid username or password"}), 401

    submitted_password = data["password"]
    is_valid = False

    try:
        is_valid = check_password_hash(user.password_hash, submitted_password)
    except ValueError:
        is_valid = False

    if not is_valid and user.password_hash == submitted_password:
        upgraded_hash = generate_password_hash(submitted_password)
        update_user_password(user.id, upgraded_hash)
        user = get_user_by_id(user.id)
        is_valid = True

    if not is_valid:
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"token": issue_token(user.id), "user": user.to_dict()})


@app.get("/me")
def me():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"user": user.to_dict()})


@app.get("/chats")
def get_chats():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    chats = [chat.to_dict() for chat in list_chats(user.id)]
    return jsonify({"chats": chats})


@app.post("/chats")
def create_chat_route():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "New chat").strip() or "New chat"
    chat = create_chat(user.id, title)
    return jsonify({"chat": chat.to_dict()}), 201


@app.patch("/chats/<int:chat_id>")
def rename_chat_route(chat_id: int):
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if not chat_belongs_to_user(chat_id, user.id):
        return jsonify({"error": "Chat not found"}), 404

    data, error_response, status = require_json(["title"])
    if error_response:
        return error_response, status

    chat = rename_chat(chat_id, data["title"].strip())
    return jsonify({"chat": chat.to_dict()})


@app.delete("/chats/<int:chat_id>")
def delete_chat_route(chat_id: int):
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if not chat_belongs_to_user(chat_id, user.id):
        return jsonify({"error": "Chat not found"}), 404

    delete_chat(chat_id)
    return jsonify({"status": "deleted"})


@app.get("/chats/<int:chat_id>/messages")
def get_messages(chat_id: int):
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if not chat_belongs_to_user(chat_id, user.id):
        return jsonify({"error": "Chat not found"}), 404

    messages = [message.to_dict() for message in list_messages(chat_id)]
    return jsonify({"messages": messages})


@app.post("/chat")
def chat():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data, error_response, status = require_json(["chat_id", "prompt"])
    if error_response:
        return error_response, status

    chat_id = int(data["chat_id"])
    prompt = data["prompt"].strip()

    if not chat_belongs_to_user(chat_id, user.id):
        return jsonify({"error": "Chat not found"}), 404

    if not GROQ_API_KEY:
        return jsonify({"error": "Missing GROQ_API_KEY in backend environment"}), 500

    add_message(chat_id, "user", prompt)

    history = list_messages(chat_id)
    groq_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    groq_messages.extend(
        {"role": message.role, "content": message.content}
        for message in history
        if message.role in {"user", "assistant"}
    )

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=groq_messages,
        temperature=0.7,
    )
    assistant_message = (completion.choices[0].message.content or "").strip()

    add_message(chat_id, "assistant", assistant_message)

    existing_chat = get_chat(chat_id)
    if existing_chat and existing_chat.title.lower() == "new chat":
        rename_chat(chat_id, prompt[:50] or "New chat")

    return jsonify(
        {
            "reply": assistant_message,
            "chat": get_chat(chat_id).to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
