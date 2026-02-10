from app.services.supabase_client import supabase
from app.services.insumo_service import list_tipos

def list_biologicos_nombres(q=None, estado=True, excluir_caducados=True):
    payload = {"p_q": q, "p_estado": estado, "p_excluir_caducados": excluir_caducados}
    res = supabase.rpc("list_biologicos_nombres", payload).execute()
    return res.data or []



def get_biologicos_lotes(nombre_biologico):
    nombre_biologico = (nombre_biologico or "").strip().upper()
    if not nombre_biologico:
        return []

    payload = {"p_nombre_biologico": nombre_biologico}
    res = supabase.rpc("list_biologico_lotes", payload).execute()
    return res.data or []


def get_insumos_asociados_biologico(nombre_biologico):
    nombre_biologico = (nombre_biologico or "").strip().upper()
    if not nombre_biologico:
        return []

    payload = {"p_nombre_biologico": nombre_biologico}
    res = supabase.rpc("list_biologico_insumos", payload).execute()
    return res.data or []


def list_jeringas_tipos():
    # usando tu list_tipos()
    tipos = list_tipos("JERINGAS", q=None, estado=True, exp_days=None) or []
    return [{"nombre_tipo": t.get("nombre_tipo")} for t in tipos if t.get("nombre_tipo")]

def bio_tiene_jeringas(nombre_biologico):
    res = supabase.rpc("bio_tiene_jeringas", {"p_nombre_biologico": nombre_biologico}).execute()
    row = res.data[0] if isinstance(res.data, list) and res.data else None
    return bool(row and row.get("ok") is True)
