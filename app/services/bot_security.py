import os
from functools import wraps
from flask import request, jsonify

def require_bot_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.getenv("BOT_KEY", "")
        # Si no configuras BOT_KEY, no bloquea (modo dev)
        if expected:
            got = request.headers.get("X-BOT-KEY", "")
            if got != expected:
                return jsonify({"error": "No autorizado"}), 401
        return fn(*args, **kwargs)
    return wrapper
