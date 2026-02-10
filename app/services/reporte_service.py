from app.services.supabase_client import supabase

def get_reporte_agregado(tipo: str, fecha: str):
    tipo = (tipo or "").upper().strip()

    if tipo == "ANUAL":
        res = supabase.rpc("reporte_anual_agregado", {"p_year": fecha}).execute()
    elif tipo == "MENSUAL":
        res = supabase.rpc("reporte_mensual_agregado", {"p_month": fecha}).execute()
    elif tipo == "DIARIO":
        res = supabase.rpc("reporte_diario_agregado", {"p_date": fecha}).execute()
    else:
        return None

    # PostgREST a veces devuelve lista, a veces dict
    data = res.data
    if isinstance(data, list) and data:
        # si viene [{"reporte_anual_agregado": {...}}]
        if isinstance(data[0], dict) and len(data[0].keys()) == 1:
            return list(data[0].values())[0]
        return data[0]

    if isinstance(data, dict):
        return data

    return None


def get_alertas_periodo(tipo: str, fecha: str):
    res = supabase.rpc("list_alertas_periodo", {
        "p_tipo": tipo,
        "p_fecha": fecha
    }).execute()
    return res.data or []
