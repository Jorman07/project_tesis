from app.services.supabase_client import supabase

def list_categorias(only_active=True):
    res = supabase.rpc("list_insumo_categorias", {"p_only_active": bool(only_active)}).execute()
    return res.data or []

def list_tipos(categoria, q=None, estado=True, exp_days=None, excluir_caducados=True):
    payload = {
        "p_categoria": categoria,
        "p_q": q,
        "p_estado": estado,  # por defecto True
        "p_exp_days": exp_days,
        "p_excluir_caducados": excluir_caducados
    }
    res = supabase.rpc("list_insumo_tipos", payload).execute()
    return res.data or []


def get_lotes(categoria, nombre_tipo, estado=None):
    payload = {
        "p_categoria": categoria,
        "p_nombre_tipo": nombre_tipo,
        "p_estado": estado
    }
    res = supabase.rpc("get_insumo_lotes", payload).execute()
    return res.data or []

def get_biologicos_asociados(nombre_tipo):
    res = supabase.rpc("get_biologicos_asociados", {"p_nombre_tipo_insumo": nombre_tipo}).execute()
    return res.data or []
