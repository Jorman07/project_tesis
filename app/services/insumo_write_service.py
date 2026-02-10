from app.services.supabase_client import supabase

def upsert_insumo_lote(categoria, nombre_tipo, lote, packs, unidades, fecha_fabricacion, fecha_caducidad):
    res = supabase.rpc("upsert_insumo_lote", {
        "p_categoria": categoria,
        "p_nombre_tipo": nombre_tipo,
        "p_lote": lote,
        "p_packs": packs,
        "p_unidades": unidades,
        "p_fecha_fabricacion": fecha_fabricacion.isoformat() if fecha_fabricacion else None,
        "p_fecha_caducidad": fecha_caducidad.isoformat()
    }).execute()

    row = res.data[0] if res.data else None
    return row


def update_insumo_lote(categoria, nombre_tipo, lote, packs, unidades, fecha_fabricacion, fecha_caducidad):
    res = supabase.rpc("update_insumo_lote", {
        "p_categoria": categoria,
        "p_nombre_tipo": nombre_tipo,
        "p_lote": lote,
        "p_packs": int(packs),
        "p_unidades": unidades,
        "p_fecha_fabricacion": fecha_fabricacion.isoformat() if fecha_fabricacion else None,
        "p_fecha_caducidad": fecha_caducidad.isoformat()
    }).execute()
    return (res.data[0] if res.data else None)

def set_insumo_estado(categoria, nombre_tipo, lote, estado):
    res = supabase.rpc("set_insumo_estado", {
        "p_categoria": categoria,
        "p_nombre_tipo": nombre_tipo,
        "p_lote": lote,
        "p_estado": estado
    }).execute()
    return (res.data[0] if res.data else None)

