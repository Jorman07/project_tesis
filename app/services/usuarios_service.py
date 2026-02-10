from app.services.supabase_client import supabase

def list_users():
    res = supabase.rpc("list_usuarios", {}).execute()
    return res.data or []

def update_user_role(id_usuario: int, rol: str):
    res = supabase.rpc("update_rol_usuario", {
        "p_id_usuario": int(id_usuario),
        "p_rol": rol
    }).execute()
    return res.data[0] if res.data else None

def admin_reset_password(id_usuario: int, new_password: str):
    res = supabase.rpc("reset_password_usuario", {
        "p_id_usuario": int(id_usuario),
        "p_new_password": new_password
    }).execute()
    return res.data[0] if res.data else None

def update_user_estado(id_usuario: int, estado: bool):
    res = supabase.rpc("update_estado_usuario", {
        "p_id_usuario": int(id_usuario),
        "p_estado": bool(estado)
    }).execute()
    return res.data[0] if res.data else None

def change_own_password(id_usuario, old_password, new_password):
    resp = supabase.rpc("change_password_usuario", {
        "p_id_usuario": int(id_usuario),
        "p_old_password": old_password,
        "p_new_password": new_password
    }).execute()

    # Supabase suele devolver lista de filas: [{"ok": true, "message": None}]
    data = resp.data
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data

    return {"ok": False, "message": "Respuesta inválida del servidor."}

