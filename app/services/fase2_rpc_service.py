from app.services.supabase_client import supabase

def insert_registros_batch(rows):
    res = supabase.rpc("insert_registros_batch", {"p_rows": rows}).execute()
    return res.data[0] if isinstance(res.data, list) and res.data else res.data

def insert_alertas_batch(rows):
    if not rows:
        return {"ok": True, "inserted": 0}
    res = supabase.rpc("insert_alertas_batch", {"p_rows": rows}).execute()
    return res.data[0] if isinstance(res.data, list) and res.data else res.data

def insert_reportes_batch(rows):
    if not rows:
        return {"ok": True, "inserted": 0}
    res = supabase.rpc("insert_reportes_batch", {"p_rows": rows}).execute()
    return res.data[0] if isinstance(res.data, list) and res.data else res.data

def update_archivo_estado(id_archivo, estado, validas, invalidas, conflictos):
    res = supabase.rpc("update_archivo_estado", {
        "p_id_archivo": id_archivo,
        "p_estado": estado,
        "p_validas": validas,
        "p_invalidas": invalidas,
        "p_conflictos": conflictos
    }).execute()
    return res.data[0] if isinstance(res.data, list) and res.data else res.data
