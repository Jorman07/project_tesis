from app.services.supabase_client import supabase

def upsert_biologico_lote(
    nombre_biologico,
    lote,
    fecha_caducidad,
    via,
    dosis_por_frasco,
    dosis_administrada,
    angulo="",
    descripcion="",
    cajas=0,
    frascos_por_caja=1,
    frascos=0
):
    return supabase.rpc("upsert_biologico_lote", {
        "p_nombre_biologico": nombre_biologico,
        "p_lote": lote,
        "p_fecha_caducidad": fecha_caducidad,
        "p_via": via,
        "p_dosis_por_frasco": dosis_por_frasco,
        "p_dosis_administrada": dosis_administrada,
        "p_angulo": angulo,
        "p_descripcion": descripcion,
        "p_cajas": cajas,
        "p_frascos_por_caja": frascos_por_caja,
        "p_frascos": frascos
    }).execute().data


def update_biologico_lote(
    nombre_biologico,
    lote,
    fecha_caducidad,
    via,
    dosis_por_frasco,
    dosis_administrada,
    angulo="",
    descripcion="",
    cajas=0,
    frascos_por_caja=1,
    frascos=0
):
    return supabase.rpc("update_biologico_lote", {
        "p_nombre_biologico": nombre_biologico,
        "p_lote": lote,
        "p_fecha_caducidad": fecha_caducidad,
        "p_via": via,
        "p_dosis_por_frasco": dosis_por_frasco,
        "p_dosis_administrada": dosis_administrada,
        "p_angulo": angulo,
        "p_descripcion": descripcion,
        "p_cajas": cajas,
        "p_frascos_por_caja": frascos_por_caja,
        "p_frascos": frascos
    }).execute().data


def set_biologico_estado(nombre_biologico, lote, estado):
    return supabase.rpc("set_biologico_estado", {
        "p_nombre_biologico": nombre_biologico,
        "p_lote": lote,
        "p_estado": estado
    }).execute().data

## tabla puente biologico_insumo_tipo

def upsert_bio_insumo_tipo(nombre_biologico, categoria_insumo, nombre_tipo_insumo):
    res = supabase.rpc("upsert_bio_insumo_tipo", {
        "p_nombre_biologico": nombre_biologico,
        "p_categoria_insumo": categoria_insumo,
        "p_nombre_tipo_insumo": nombre_tipo_insumo
    }).execute()

    # la función retorna json, PostgREST lo entrega como dict dentro de data[0] o directamente
    if isinstance(res.data, list) and res.data:
        return res.data[0]
    if isinstance(res.data, dict):
        return res.data
    return {"ok": False, "message": "Sin respuesta"}

