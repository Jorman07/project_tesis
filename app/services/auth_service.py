from app.services.supabase_client import supabase

# ======================
# REGISTRO DE USUARIO (RPC)
# ======================
def register_user(cedula, nombres, apellidos, password, rol):
    res = supabase.rpc("register_usuario", {
        "p_cedula": str(cedula).strip(),
        "p_nombres": nombres,
        "p_apellidos": apellidos,
        "p_password": password,
        "p_rol": rol
    }).execute()

    row = (res.data[0] if res.data else None)

    if not row or row.get("ok") is not True:
        return {"error": (row.get("message") if row else "No se pudo registrar")}

    return row


# ======================
# LOGIN DE USUARIO (RPC)
# ======================
def authenticate(cedula, password):
    res = supabase.rpc("login_usuario", {
        "p_cedula": str(cedula).strip(),
        "p_password": password
    }).execute()

    row = (res.data[0] if res.data else None)

    if not row or row.get("ok") is not True:
        # devolvemos None y el mensaje para que routes lo use
        return None, (row.get("message") if row else "No se pudo iniciar sesión")

    user = {
        "id_usuario": row["id_usuario"],
        "cedula": row["cedula"],
        "nombres": row["nombres"].upper(),
        "apellidos": row["apellidos"].upper(),
        "rol": row["rol"],
        "estado": row.get("estado", True)
    }
    return user, None