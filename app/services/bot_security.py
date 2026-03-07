import os
from functools import wraps
from flask import request, jsonify

def require_bot_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.getenv("BOT_KEY", "")
        got = request.headers.get("X-BOT-KEY", "")
        print("BOT_KEY esperada en flask:", bool(expected))
        print("X-BOT-KEY recibida:", bool(got))
        if expected:
            if got != expected:
                return jsonify({"error": "No autorizado"}), 401
        return fn(*args, **kwargs)
    return wrapper