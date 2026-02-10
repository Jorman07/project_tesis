# app/services/dashboard_service.py
from app.services.supabase_client import supabase

def dashboard_init():
    r = supabase.rpc("dashboard_init", {}).execute().data
    return r[0] if isinstance(r, list) and r else (r or {"ok": False})

def dashboard_data(periodo=None, vacuna=None, esquema=None):
    payload = {"p_periodo": periodo, "p_vacuna": vacuna, "p_esquema": esquema}
    r = supabase.rpc("dashdashboard_data_v4", payload).execute().data
    return r[0] if isinstance(r, list) and r else (r or {"ok": False})
