import hashlib
from app.services.supabase_client import supabase

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def insert_archivo(
    nombre_archivo: str,
    id_usuario_carga: int,
    hash_archivo: str,
    min_fecha,
    max_fecha,
    meses_detectados,
    total_filas: int,
    total_cols: int,
    headers_originales,
    headers_normalizados,
    contenido_base64: str
):
    res = supabase.rpc("insert_archivo", {
        "p_nombre_archivo": nombre_archivo,
        "p_id_usuario_carga": id_usuario_carga,
        "p_hash_archivo": hash_archivo,
        "p_min_fecha_vacunacion": min_fecha.isoformat() if min_fecha else None,
        "p_max_fecha_vacunacion": max_fecha.isoformat() if max_fecha else None,
        "p_meses_detectados": meses_detectados,
        "p_total_filas_leidas": total_filas,
        "p_total_columnas": total_cols,
        "p_headers_originales": headers_originales,
        "p_headers_normalizados": headers_normalizados,
        "p_contenido_base64": contenido_base64
    }).execute()

    return res.data[0] if isinstance(res.data, list) and res.data else None

from app.services.supabase_client import supabase

def update_archivo_content(
    id_archivo: int,
    nombre_archivo: str,
    hash_archivo: str,
    contenido_base64: str,
    min_fecha,
    max_fecha,
    meses_detectados,
    total_filas: int,
    total_columnas: int,
    headers_originales,
    headers_normalizados
):
    res = supabase.rpc("update_archivo_content", {
        "p_id_archivo": id_archivo,
        "p_nombre_archivo": nombre_archivo,
        "p_hash_archivo": hash_archivo,
        "p_contenido_base64": contenido_base64,
        "p_min_fecha_vacunacion": min_fecha.isoformat() if min_fecha else None,
        "p_max_fecha_vacunacion": max_fecha.isoformat() if max_fecha else None,
        "p_meses_detectados": meses_detectados,
        "p_total_filas": int(total_filas),
        "p_total_columnas": int(total_columnas),
        "p_headers_originales": headers_originales,
        "p_headers_normalizados": headers_normalizados
    }).execute()

    if isinstance(res.data, list) and res.data:
        return res.data[0]
    if isinstance(res.data, dict):
        return res.data
    return {"ok": False, "message": "Sin respuesta"}



def get_archivo_contenido(id_archivo: int):
    res = supabase.rpc("get_archivo_contenido", {"p_id_archivo": id_archivo}).execute()
    return res.data[0] if isinstance(res.data, list) and res.data else None

def list_archivos():
    res = supabase.rpc("list_archivos", {}).execute()
    return res.data or []

def clear_archivo_data(id_archivo: int):
    res = supabase.rpc("clear_archivo_data", {"p_id_archivo": id_archivo}).execute()
    if isinstance(res.data, list) and res.data:
        return res.data[0]
    if isinstance(res.data, dict):
        return res.data
    return {"ok": False, "message": "Sin respuesta"}