from email.mime import message
from functools import wraps
from app.services.bot_security import require_bot_key
from flask import Blueprint, session, redirect, url_for, render_template, flash, request, jsonify, make_response
from app.services.supabase_client import supabase
import base64, hashlib, re
from datetime import date

from app.services.consult_service import (
    process_in_memory,
    get_cached_registros_page
)

from app.services.usuarios_service import (
    list_users,
    update_user_estado,
    update_user_role,
    admin_reset_password,
    change_own_password
)

from app.services.insumo_service import (
    list_categorias,
    list_tipos,
    get_lotes,
    get_biologicos_asociados
)
from app.services.insumo_write_service import upsert_insumo_lote, update_insumo_lote, set_insumo_estado
from app.services.utils import (
    calcular_unidades, 
    dato_normalizado, 
    edad_texto, 
    month_to_first_day, 
    month_to_last_day, 
    build_prass_report_pdf, 
    PACIENTE_DATO_MAP, 
    pick_value, 
    edad_texto, 
    paciente_from_datos
)
from app.services.archivo_service import list_archivos, get_archivo_contenido, update_archivo_content, insert_archivo,clear_archivo_data
from app.services.prass_parser import parse_any_prass_file, extract_fecha_vacunacion_stats
from app.services.carga_vacunacion_service import process_file_bytes
from app.services.fase2_rpc_service import (
    insert_registros_batch, insert_alertas_batch, insert_reportes_batch, update_archivo_estado
)

from app.services.biologico_service import (
    bio_tiene_jeringas,
    list_biologicos_nombres,
    get_biologicos_lotes,
    get_insumos_asociados_biologico,
    list_jeringas_tipos,
    bio_tiene_jeringas
)

from app.services.biologico_write_service import (
    upsert_biologico_lote,
    update_biologico_lote,
    set_biologico_estado,
    upsert_bio_insumo_tipo
)

from app.services.predict_service import predict_ml_bundle, insumos_estimados_bundle
from app.services.chatbot_service import ChatbotService


main_bp = Blueprint('main', __name__)

# ==========================
# GUARDS
# ==========================
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login_view'))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    roles_up = [r.upper() for r in roles]

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('auth.login_view'))

            role = (session['user'].get('rol') or '').upper()
            if role not in roles_up:
                # si es endpoint api, devolvemos 403 json
                if request.path.startswith('/api/'):
                    return jsonify({"error": "forbidden"}), 403
                return redirect(url_for('main.dashboard'))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ==========================
# CONTEXTO GLOBAL (MENÚ)
# ==========================
def build_context():
    user = session.get('user')
    if not user:
        return None, None

    ALL_ITEMS = [
        {"name": "Mi Perfil", "endpoint": "main.perfil"},
        {"name": "Dashboard", "endpoint": "main.dashboard"},
        {"name": "Usuarios", "endpoint": "main.usuarios"},
        {"name": "Archivos", "endpoint": "main.archivos"},
        {"name": "Registros de Vacunación", "endpoint": "main.registros"},
        {"name": "Biológicos", "endpoint": "main.biologicos"},
        {"name": "Insumos", "endpoint": "main.insumos"},
        {"name": "Reportes", "endpoint": "main.reportes"},
        {"name": "Alertas", "endpoint": "main.alertas"},
        {"name": "Consultas rápidas", "endpoint": "main.consultas"},
    ]

    role = (user.get("rol") or "").upper()

    if role == "ADMINISTRADOR":
        menu_items = ALL_ITEMS
    elif role == "COORDINADOR":
        menu_items = [x for x in ALL_ITEMS if x["name"] not in ["Usuarios", "Archivos"]]
    else:  # ASISTENTE
        allowed = ["Mi Perfil", "Dashboard", "Registros de Vacunación", "Reportes", "Alertas", "Consultas rápidas"]
        menu_items = [x for x in ALL_ITEMS if x["name"] in allowed]

    data = {
        "title": "PRASS_ANALYTICS",
        "name_project": "PRASS_ANALYTICS",
        "menu": menu_items,
        "footer": "© 2026 PRASS_ANALYTICS - All Rights Reserved",
        "autor": "Jorman Holguín & Cesar Campaña"
    }

    return user, data


# ==========================
# HOME / DASHBOARD
# ==========================
@main_bp.route('/')
@login_required
def home():
    user, data = build_context()
    return render_template("dashboard.html", user=user, data=data)


@main_bp.route('/dashboard')
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def dashboard():
    user, data = build_context()
    return render_template("dashboard.html", user=user, data=data)


@main_bp.route('/api/dashboard/init', methods=['GET'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_dashboard_init():
    r = supabase.rpc("dashboard_init", {}).execute().data
    # a veces viene lista con un jsonb dentro
    if isinstance(r, list) and r:
        return jsonify(r[0])
    return jsonify(r or {"ok": False})


@main_bp.route('/api/dashboard/data', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_dashboard_data():
    p = request.get_json() or {}

    def _n(v):
    # normaliza strings vacíos -> None
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            return v if v != "" else None
        return v


    payload = {
        "p_periodo": _n(p.get("periodo")),
        "p_vacuna": _n(p.get("vacuna")),
        "p_esquema": _n(p.get("esquema")),

        # opcionales
        "p_sexo": _n(p.get("sexo")),
        "p_grupo_riesgo": _n(p.get("grupo_riesgo")),
        "p_etnia": _n(p.get("etnia")),
        "p_parroquia": _n(p.get("parroquia")),
        "p_vacuna_variante": _n(p.get("vacuna_variante")),
        "p_vacuna_canon": _n(p.get("vacuna_canon")),

        # numéricos
        "p_edad_min": int(p["edad_min"]) if p.get("edad_min") not in (None, "",) else None,
        "p_edad_max": int(p["edad_max"]) if p.get("edad_max") not in (None, "",) else None,

        # fechas (YYYY-MM-DD o None)
        "p_fecha_desde": _n(p.get("fecha_desde")),
        "p_fecha_hasta": _n(p.get("fecha_hasta")),
    }

    print("PAYLOAD RPC:", payload, flush=True) 
    r = supabase.rpc("dashboard_data_v4", payload).execute().data
    

    if isinstance(r, list) and r:
        return jsonify(r[0])
    return jsonify(r or {"ok": False})

@main_bp.route('/api/dashboard/insumos_estimados', methods=['POST'])
@login_required
def api_dashboard_insumos_estimados():
    try:
        p = request.get_json(silent=True) or {}
        periodo = _n(p.get("periodo"))  # YYYY-MM
        vacuna = _n(p.get("vacuna"))

        if not periodo:
            return jsonify({"ok": False, "error": "periodo requerido"}), 400

        out = insumos_estimados_bundle(periodo=periodo, vacuna=vacuna)  # <- tu wrapper
        return jsonify(out)
    except Exception as e:
        print("insumos_estimados error:", e, flush=True)
        return jsonify({"ok": False, "error": str(e)}), 500



def _n(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v if v != "" else None
    return v


import numpy as np
@main_bp.route('/api/dashboard/predict', methods=['POST'])
@login_required
def api_dashboard_predict():
    try:
        import numpy as np

        p = request.get_json() or {}

        payload_dbg = {
            "periodo": _n(p.get("periodo")),
            "vacuna": _n(p.get("vacuna")),
            "parroquia": _n(p.get("parroquia")),
            "fecha_desde": _n(p.get("fecha_desde")),
            "fecha_hasta": _n(p.get("fecha_hasta")),
            "window_days": p.get("window_days"),
            "horizon_m": p.get("horizon_m"),
        }
        print("PREDICT_ML input:", payload_dbg, flush=True)

        # Ventana: default 180 (≈6 meses), con límites duros para no reventar la BD
        try:
            wd = int(payload_dbg["window_days"]) if payload_dbg["window_days"] is not None else 180
        except Exception:
            wd = 180
        wd = max(60, min(wd, 365))  # mínimo razonable / máximo controlado

        # NUEVO: horizon_m (1,3,6,12)
        try:
            hm = int(payload_dbg["horizon_m"]) if payload_dbg["horizon_m"] is not None else 1
        except Exception:
            hm = 1
        hm = max(1, min(hm, 12))  # límite duro

        # IMPORTANTE: solo una ejecución
        out = predict_ml_bundle(
            periodo=payload_dbg["periodo"],
            vacuna=payload_dbg["vacuna"],
            window_days=wd,
            horizon_m=hm,
        )
        # Debug (sin recalcular)
        try:
            people = (out.get("people") or {}).get("series", {}) or {}
            y_hist = people.get("y_hist", []) or []
            y_fc = people.get("y_fc", []) or []

            print("PEOPLE y_hist last 10:", y_hist[-10:], flush=True)
            print("PEOPLE y_hist last 7 mean:", float(np.mean(y_hist[-7:])) if len(y_hist) >= 7 else None, flush=True)
            print("PEOPLE y_fc (first 10):", y_fc[:10], flush=True)
            print("PEOPLE model:", (out.get("people") or {}).get("model"), flush=True)
            print("PEOPLE next:", (out.get("people") or {}).get("next"), flush=True)

            print("WINDOW_DAYS effective:", wd, flush=True)
        except Exception as e:
            print("DEBUG PEOPLE error:", e, flush=True)

        return jsonify(out)

    except Exception as e:
        print("predict_ml error:", e, flush=True)
        return jsonify({"ok": False, "error": str(e)}), 500



@main_bp.route('/api/dashboard/compare', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_dashboard_compare():
    p = request.get_json() or {}

    def _n(v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            return v if v != "" else None
        return v

    payload = {
        "p_periodo_a": _n(p.get("periodo_a")),
        "p_periodo_b": _n(p.get("periodo_b")),
    }

    print("PAYLOAD RPC COMPARE:", payload, flush=True)
    r = supabase.rpc("dashboard_compare_v3", payload).execute().data

    if isinstance(r, list) and r:
        return jsonify(r[0])
    return jsonify(r or {"ok": False})



@main_bp.route('/api/dashboard/anual', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_dashboard_anual():
    body = request.get_json(silent=True) or {}

    args = {
        "p_year": body.get("year"),  # solo año
        # opcional: reglas (si no mandas, usa defaults de la RPC)
        "p_dosis_por_rollo": body.get("dosis_por_rollo"),
        "p_ml_alcohol_por_dosis": body.get("ml_alcohol_por_dosis"),
    }

    # limpia None (supabase rpc a veces se pone sensible)
    args = {k: v for k, v in args.items() if v is not None}

    r = supabase.rpc("dashboard_anual_v2", args).execute().data
    if isinstance(r, list) and r:
        return jsonify(r[0])
    return jsonify(r or {"ok": False})




# ==========================
# USUARIOS (ADMIN ONLY)
# ==========================
@main_bp.route('/usuarios')
@login_required
@role_required("ADMINISTRADOR")
def usuarios():
    user, data = build_context()

    users = list_users()
    for u in users:
        u["nombres"] = (u.get("nombres") or "").upper()
        u["apellidos"] = (u.get("apellidos") or "").upper()
        u["rol"] = (u.get("rol") or "").upper()

    return render_template("usuarios.html", user=user, data=data, users=users)


@main_bp.route('/usuarios/update-rol', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR")
def usuarios_update_rol():
    current = session['user']

    id_usuario = request.form.get("id_usuario")
    nuevo_rol = request.form.get("rol")

    if not id_usuario or not nuevo_rol:
        flash("Datos incompletos para actualizar el rol.", "error")
        return redirect(url_for('main.usuarios'))

    try:
        id_usuario_int = int(id_usuario)
        current_id_int = int(current.get("id_usuario"))
    except:
        flash("ID inválido.", "error")
        return redirect(url_for('main.usuarios'))

    # Bloqueo: no puede cambiar su propio rol
    if id_usuario_int == current_id_int:
        flash("No puedes cambiar tu propio rol de ADMINISTRADOR.", "error")
        return redirect(url_for('main.usuarios'))

    res = update_user_role(id_usuario_int, nuevo_rol)

    if res and res.get("ok"):
        flash("Rol actualizado correctamente.", "success")
    else:
        flash("No se pudo actualizar el rol.", "error")

    return redirect(url_for('main.usuarios'))


@main_bp.route('/usuarios/reset-password', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR")
def usuarios_reset_password():
    id_usuario = request.form.get("id_usuario")
    new_password = request.form.get("new_password")

    if not id_usuario or not new_password:
        flash("Datos incompletos para restablecer contraseña.", "error")
        return redirect(url_for('main.usuarios'))

    res = admin_reset_password(id_usuario, new_password)
    if res and res.get("ok"):
        flash("Contraseña restablecida correctamente.", "success")
    else:
        flash("No se pudo restablecer la contraseña.", "error")

    return redirect(url_for('main.usuarios'))


@main_bp.route('/usuarios/update-estado', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR")
def usuarios_update_estado():
    current = session['user']

    id_usuario = request.form.get("id_usuario")
    estado = request.form.get("estado")

    if not id_usuario or estado is None:
        flash("Datos incompletos para actualizar estado.", "error")
        return redirect(url_for('main.usuarios'))

    try:
        id_usuario_int = int(id_usuario)
        current_id_int = int(current.get("id_usuario"))
    except:
        flash("ID inválido.", "error")
        return redirect(url_for('main.usuarios'))

    # Bloqueo: no puede cambiar su propio estado
    if id_usuario_int == current_id_int:
        flash("No puedes cambiar tu propio estado.", "error")
        return redirect(url_for('main.usuarios'))

    new_estado = True if estado.lower() == "true" else False
    res = update_user_estado(id_usuario_int, new_estado)

    if res and res.get("ok"):
        flash("Estado actualizado correctamente.", "success")
    else:
        flash("No se pudo actualizar el estado.", "error")

    return redirect(url_for('main.usuarios'))


# ==========================
# PERFIL (TODOS)
# ==========================
@main_bp.route('/perfil')
@login_required
def perfil():
    user, data = build_context()
    return render_template("perfil.html", user=user, data=data)


@main_bp.route('/perfil/change-password', methods=['POST'])
@login_required
def perfil_change_password():
    user = session.get('user') or {}
    id_usuario = user.get("id_usuario")

    old_password = (request.form.get("old_password") or "").strip()
    new_password = (request.form.get("new_password") or "").strip()

    if not id_usuario or not old_password or not new_password:
        flash("Completa todos los campos.", "error")
        return redirect(url_for('main.perfil'))

    # Llama a tu servicio (debe invocar RPC change_password_usuario)
    r = change_own_password(id_usuario, old_password, new_password)

    # Esperado: r = {"ok": True/False, "message": "..."} o lista con fila
    ok = False
    msg = None

    if isinstance(r, dict):
        ok = bool(r.get("ok"))
        msg = r.get("message")
    elif isinstance(r, list) and r:
        ok = bool(r[0].get("ok"))
        msg = r[0].get("message")

    if ok:
        flash("Contraseña actualizada.", "success")
    else:
        flash(msg or "No se pudo cambiar la contraseña.", "error")

    return redirect(url_for('main.perfil'))



# ==========================
# archivos (admin)
# ==========================

@main_bp.route('/archivos')
@login_required
@role_required("ADMINISTRADOR")
def archivos():
    user, data = build_context()
    return render_template("archivos.html", user=user, data=data)

@main_bp.route('/api/archivos/list')
@login_required
@role_required("ADMINISTRADOR")
def api_archivos_list():
    return jsonify(list_archivos())


@main_bp.route('/api/archivos/preview', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR")
def api_archivos_preview():
    if 'file' not in request.files:
        return jsonify({"message":"No se envió archivo."}), 400

    f = request.files['file']
    filename = (f.filename or "archivo").strip()
    content = f.read()

    if not content:
        return jsonify({"message":"El archivo está vacío."}), 400

    try:
        parsed = parse_any_prass_file(filename, content)
        headers_norm = parsed["headers_normalizados"]
        rows = parsed["rows"]
        headers_originales = parsed.get("headers_originales", [])
        tipo = parsed.get("tipo_detectado", "DESCONOCIDO")
    except Exception as e:
        return jsonify({
            "message":"No se pudo procesar el archivo.",
            "detail": str(e),
            "filename": filename
        }), 400

    min_d, max_d, months = extract_fecha_vacunacion_stats(headers_norm, rows)

    return jsonify({
        "nombre_archivo": filename,
        "tipo_detectado": tipo,
        "total_filas": len(rows),
        "total_columnas": len(headers_norm),
        "headers_originales": headers_originales,
        "headers": headers_norm,
        "preview": rows[:25],
        "min_fecha_vacunacion": min_d.isoformat() if min_d else None,
        "max_fecha_vacunacion": max_d.isoformat() if max_d else None,
        "meses_detectados": months
    })


@main_bp.route('/api/archivos/procesar', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR")
def api_archivos_procesar():
    data = request.get_json() or {}
    id_archivo = data.get("id_archivo")
    if not id_archivo:
        return jsonify({"message":"Falta id_archivo."}), 400

    id_archivo = int(id_archivo)

    # 1) limpiar resultados previos (registros/alertas/reportes)
    clear_archivo_data(id_archivo)

    row = get_archivo_contenido(id_archivo)
    if not row or not row.get("contenido_base64"):
        return jsonify({"message":"No se encontró contenido del archivo. Vuelve a guardar la carga."}), 400

    content = base64.b64decode(row["contenido_base64"])
    filename = row.get("nombre_archivo") or "archivo"

    registros, alertas, reportes, metrics = process_file_bytes(id_archivo, filename, content)

    r1 = insert_registros_batch(registros)
    a1 = insert_alertas_batch(alertas)
    rep1 = insert_reportes_batch(reportes)

    # 2) Link alertas a registros (id_registro) por hash_fila
    try:
        linked = supabase.rpc("asignar_id_registro_alertas", {"p_id_archivo": id_archivo}).execute().data
    except Exception:
        linked = None

    # 3) Aplicar consumo (internamente hace revertir + recalcular)
    try:
        consumo = supabase.rpc("aplicar_consumo_archivo", {"p_id_archivo": id_archivo}).execute().data
    except Exception as e:
        consumo = {"ok": False, "detail": str(e)}

    # 4) Evaluar alertas de inventario (60 días, bio<=500 dosis, insumo<=1500 unidades)
    try:
        inventario_alertas = supabase.rpc(
            "evaluar_alertas_inventario",
            {"p_dias_caducar": 60, "p_umbral_bio_dosis": 500, "p_umbral_ins_unidades": 1500}
        ).execute().data
    except Exception as e:
        inventario_alertas = {"ok": False, "detail": str(e)}

    update_archivo_estado(id_archivo, "PROCESADO", metrics["validas"], metrics["invalidas"], metrics["conflictos"])

    # 5) Refresh dashboard (series para ML / gráficos)
    try:
        supabase.rpc(
            "dashboard_refresh_by_archivo",
            {"p_id_archivo": id_archivo}
        ).execute()
    except Exception as e:
        # No rompemos el flujo si falla el dashboard
        print("WARN dashboard_refresh_by_archivo:", e, flush=True)


    return jsonify({
        "ok": True,
        "metrics": metrics,
        "registros": r1,
        "alertas": a1,
        "reportes": rep1,
        "alertas_linked": linked,
        "consumo_inventario": consumo,
        "alertas_inventario": inventario_alertas
    })


@main_bp.route('/api/archivos/guardar', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR")
def api_archivos_guardar():
    if 'file' not in request.files:
        return jsonify({"message":"No se envió archivo."}), 400

    f = request.files['file']
    filename = (f.filename or "archivo").strip()
    content = f.read()

    if not content:
        return jsonify({"message":"El archivo está vacío."}), 400

    # Parse para métricas (reusa tu parser estable)
    parsed = parse_any_prass_file(filename, content)
    headers_norm = parsed["headers_normalizados"]
    headers_originales = parsed.get("headers_originales", [])
    rows = parsed["rows"]

    min_d, max_d, months = extract_fecha_vacunacion_stats(headers_norm, rows)

    # hash archivo real
    hash_archivo = hashlib.sha256(content).hexdigest()

    # base64 para guardar
    contenido_b64 = base64.b64encode(content).decode("utf-8")

    user = session["user"]
    id_usuario = int(user.get("id_usuario"))

    res = insert_archivo(
        nombre_archivo=filename,
        id_usuario_carga=id_usuario,
        hash_archivo=hash_archivo,
        min_fecha=min_d,
        max_fecha=max_d,
        meses_detectados=months,
        total_filas=len(rows),
        total_cols=len(headers_norm),
        headers_originales=headers_originales,
        headers_normalizados=headers_norm,
        contenido_base64=contenido_b64
    )

    if not res or not res.get("ok"):
        return jsonify({"message": (res.get("message") if res else "No se pudo guardar")}), 400

    return jsonify({"ok": True, "id_archivo": res.get("id_archivo")})


@main_bp.route('/api/archivos/update', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR")
def api_archivos_update():
    id_archivo = request.form.get("id_archivo")
    if not id_archivo:
        return jsonify({"message": "Falta id_archivo."}), 400

    if 'file' not in request.files:
        return jsonify({"message": "No se envió archivo."}), 400

    id_archivo = int(id_archivo)

    f = request.files['file']
    filename = (f.filename or "archivo").strip()
    content = f.read()

    if not content:
        return jsonify({"message": "El archivo está vacío."}), 400

    # Parse del nuevo archivo
    try:
        parsed = parse_any_prass_file(filename, content)
        headers_norm = parsed["headers_normalizados"]
        headers_originales = parsed.get("headers_originales", [])
        rows = parsed["rows"]
        min_d, max_d, months = extract_fecha_vacunacion_stats(headers_norm, rows)
    except Exception as e:
        return jsonify({"message": "No se pudo procesar el nuevo archivo.", "detail": str(e)}), 400

    hash_archivo = hashlib.sha256(content).hexdigest()
    contenido_b64 = base64.b64encode(content).decode("utf-8")

    # 0) Revertir inventario del consumo anterior (si existía)
    try:
        rev = supabase.rpc("revertir_consumo_archivo", {"p_id_archivo": id_archivo}).execute().data
    except Exception as e:
        rev = {"ok": False, "detail": str(e)}

    # 1) limpiar datos previos del archivo (registros/alertas/reportes)
    clear_archivo_data(id_archivo)

    # 2) actualizar metadata + contenido y dejar PENDIENTE
    res = update_archivo_content(
        id_archivo=id_archivo,
        nombre_archivo=filename,
        hash_archivo=hash_archivo,
        contenido_base64=contenido_b64,
        min_fecha=min_d,
        max_fecha=max_d,
        meses_detectados=months,
        total_filas=len(rows),
        total_columnas=len(headers_norm),
        headers_originales=headers_originales,
        headers_normalizados=headers_norm
    )

    if not res or not res.get("ok"):
        return jsonify({"message": res.get("message", "No se pudo actualizar el archivo.")}), 400

    return jsonify({"ok": True, "inventario_revertido": rev})



# ==========================
# REGISTROS DE VACUNACIÓN (TODOS)
# ==========================

@main_bp.route('/registros')
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def registros():
    user, data = build_context()
    return render_template("registros.html", user=user, data=data)


@main_bp.route('/api/registros/years')
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_registros_years():
    res = supabase.rpc("list_registros_years", {}).execute()
    return jsonify(res.data or [])

@main_bp.route('/api/registros/page')
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_registros_page():
    year = (request.args.get("year") or "").strip()
    month = (request.args.get("month") or "").strip()
    day = (request.args.get("day") or "").strip()
    sexo = (request.args.get("sexo") or "").strip()
    esquema = (request.args.get("esquema") or "").strip()
    grupo = (request.args.get("grupo") or "").strip()
    vacuna = (request.args.get("vacuna") or "").strip()
    estado = (request.args.get("estado") or "").strip()
    nombre = (request.args.get("nombre") or "").strip()
    cedula = (request.args.get("cedula") or "").strip()

    edad_min = request.args.get("edad_min")
    edad_max = request.args.get("edad_max")
    edad_min = int(edad_min) if edad_min and edad_min.isdigit() else None
    edad_max = int(edad_max) if edad_max and edad_max.isdigit() else None

    page = int(request.args.get("page") or 1)
    page_size = int(request.args.get("page_size") or 50)
    offset = (page - 1) * page_size

    res = supabase.rpc("list_registros_page", {
        "p_year": year,
        "p_month": month,
        "p_day": day,
        "p_sexo": sexo,
        "p_esquema": esquema,
        "p_grupo_riesgo": grupo,
        "p_vacuna": vacuna,
        "p_estado": estado,
        "p_nombre": nombre,
        "p_cedula": cedula,
        "p_edad_min": edad_min,
        "p_edad_max": edad_max,
        "p_limit": page_size,
        "p_offset": offset
    }).execute()

    return jsonify(res.data or [])



@main_bp.route('/api/registros/count')
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_registros_count():
    year = (request.args.get("year") or "").strip()
    month = (request.args.get("month") or "").strip()
    day = (request.args.get("day") or "").strip()
    sexo = (request.args.get("sexo") or "").strip()
    esquema = (request.args.get("esquema") or "").strip()
    grupo = (request.args.get("grupo") or "").strip()
    vacuna = (request.args.get("vacuna") or "").strip()
    estado = (request.args.get("estado") or "").strip()
    nombre = (request.args.get("nombre") or "").strip()
    cedula = (request.args.get("cedula") or "").strip()

    edad_min = request.args.get("edad_min")
    edad_max = request.args.get("edad_max")
    edad_min = int(edad_min) if edad_min and edad_min.isdigit() else None
    edad_max = int(edad_max) if edad_max and edad_max.isdigit() else None

    res = supabase.rpc("count_registros", {
        "p_year": year,
        "p_month": month,
        "p_day": day,
        "p_sexo": sexo,
        "p_esquema": esquema,
        "p_grupo_riesgo": grupo,
        "p_vacuna": vacuna,
        "p_estado": estado,
        "p_nombre": nombre,
        "p_cedula": cedula,
        "p_edad_min": edad_min,
        "p_edad_max": edad_max
    }).execute()

    total = res.data[0]["total"] if res.data else 0
    return jsonify({"total": total})


@main_bp.route('/api/paciente/historial')
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_paciente_historial():
    cedula = (request.args.get("cedula") or "").strip()
    if not cedula:
        return jsonify([])

    res = supabase.rpc("historial_paciente", {"p_cedula": cedula}).execute()
    return jsonify(res.data or [])

# ==========================
# Biologicos (ADMINISTRADOR + COORDINADOR)
# ==========================

@main_bp.route('/biologicos')
@role_required("ADMINISTRADOR", "COORDINADOR")
def biologicos():
    user, data = build_context()
    return render_template("biologicos.html", user=user, data=data)


@main_bp.route('/api/biologicos/nombres')
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_biologicos_nombres():
    q = request.args.get("q", "").strip() or None
    return jsonify(list_biologicos_nombres(q=q))


@main_bp.route('/api/biologicos/lotes')
@role_required("ADMINISTRADOR","COORDINADOR")
def api_biologicos_lotes():
    nombre = request.args.get("nombre", "").strip()

    data = get_biologicos_lotes(nombre)

    return jsonify(data)


@main_bp.route('/api/biologicos/insumos')
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_biologicos_insumos():
    nombre = request.args.get("nombre_biologico", "").strip()
    if not nombre:
        return jsonify([])
    return jsonify(get_insumos_asociados_biologico(nombre))


@main_bp.route('/api/biologicos/jeringas')
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_biologicos_jeringas():
    return jsonify(list_jeringas_tipos())


# ==========================
# Biologicos (ADMIN ONLY)
# ==========================
@main_bp.route('/api/biologicos/registrar', methods=['POST'])
@role_required("ADMINISTRADOR")
def api_biologicos_registrar():
    data = request.get_json() or {}

    nombre_biologico = (data.get("nombre_biologico") or "").strip().upper()
    lote = (data.get("lote") or "").strip()
    fecha_caducidad = (data.get("fecha_caducidad") or "").strip()
    via = (data.get("via") or "").strip().upper()

    try:
        dosis_por_frasco = float(data.get("dosis_por_frasco") or 0)
        dosis_administrada = float(data.get("dosis_administrada") or 0)
    except:
        return jsonify({"message": "Dosis inválidas."}), 400

    cajas = int(data.get("cajas") or 0)
    frascos_por_caja = int(data.get("frascos_por_caja") or 1)

    # frascos total = cajas * frascos_por_caja (SIEMPRE)
    frascos_total = max(0, cajas) * max(1, frascos_por_caja)

    angulo = (data.get("angulo") or "").strip()
    descripcion = (data.get("descripcion") or "").strip()

    jeringas = data.get("jeringas_asociadas") or []

    if not nombre_biologico or not lote or not fecha_caducidad or not via:
        return jsonify({"message": "Completa: nombre, lote, caducidad y vía."}), 400

    if via not in ["IM", "SC", "ID", "VO"]:
        return jsonify({"message": "Vía inválida. Usa IM / SC / ID / VO."}), 400

    if dosis_por_frasco <= 0 or dosis_administrada <= 0:
        return jsonify({"message": "Dosis por frasco y dosis aplicada deben ser mayores a 0."}), 400

    if frascos_por_caja <= 0:
        return jsonify({"message": "Frascos por caja inválido."}), 400
    
    ya_tiene = bio_tiene_jeringas(nombre_biologico)

    # solo exigir jeringas si no tiene aún
    if (not ya_tiene) and (not isinstance(jeringas, list) or len(jeringas) == 0):
        return jsonify({"message": "Selecciona al menos una jeringa asociada."}), 400


    res = upsert_biologico_lote(
        nombre_biologico=nombre_biologico,
        lote=lote,
        fecha_caducidad=fecha_caducidad,
        via=via,
        dosis_por_frasco=dosis_por_frasco,
        dosis_administrada=dosis_administrada,
        angulo=angulo,
        descripcion=descripcion,
        cajas=cajas,
        frascos_por_caja=frascos_por_caja,
        frascos=frascos_total
    )
    

    if not res or not res.get("ok"):
        return jsonify({"message": (res.get("message") if res else "No se pudo registrar")}), 400


    # tabla puente (biologico -> jeringas)
    if isinstance(jeringas, list) and len(jeringas) > 0:
        for nombre_tipo in jeringas:
            upsert_bio_insumo_tipo(
                nombre_biologico=nombre_biologico,
                categoria_insumo="JERINGAS",
                nombre_tipo_insumo=nombre_tipo
            )

    # Recalcular alertas inventario tras cambios
    try:
        supabase.rpc("evaluar_alertas_inventario", {
            "p_dias_caducar": 60,
            "p_umbral_bio_dosis": 500,
            "p_umbral_ins_unidades": 1500
        }).execute()
    except Exception:
        pass


    return jsonify({"ok": True})


@main_bp.route('/api/biologicos/editar-lote', methods=['POST'])
@role_required("ADMINISTRADOR")
def api_biologicos_editar_lote():
    data = request.get_json() or {}

    nombre_biologico = (data.get("nombre_biologico") or "").strip().upper()
    lote = (data.get("lote") or "").strip()
    fecha_caducidad = (data.get("fecha_caducidad") or "").strip()
    via = (data.get("via") or "").strip().upper()

    try:
        dosis_por_frasco = float(data.get("dosis_por_frasco") or 0)
        dosis_administrada = float(data.get("dosis_administrada") or 0)
    except:
        return jsonify({"message": "Dosis inválidas."}), 400

    cajas = int(data.get("cajas") or 0)
    frascos_por_caja = int(data.get("frascos_por_caja") or 1)

    frascos_total = max(0, cajas) * max(1, frascos_por_caja)

    angulo = (data.get("angulo") or "").strip()
    descripcion = (data.get("descripcion") or "").strip()

    if not nombre_biologico or not lote or not fecha_caducidad or not via:
        return jsonify({"message": "Datos incompletos."}), 400

    if via not in ["IM", "SC", "ID", "VO"]:
        return jsonify({"message": "Vía inválida. Usa IM / SC / ID / VO."}), 400

    if dosis_por_frasco <= 0 or dosis_administrada <= 0:
        return jsonify({"message": "Dosis inválidas."}), 400

    if frascos_por_caja <= 0:
        return jsonify({"message": "Frascos por caja inválido."}), 400

    res = update_biologico_lote(
        nombre_biologico=nombre_biologico,
        lote=lote,
        fecha_caducidad=fecha_caducidad,
        via=via,
        dosis_por_frasco=dosis_por_frasco,
        dosis_administrada=dosis_administrada,
        angulo=angulo,
        descripcion=descripcion,
        cajas=cajas,
        frascos_por_caja=frascos_por_caja,
        frascos=frascos_total
    )

    if not res or not res.get("ok"):
        return jsonify({"message": (res.get("message") if res else "No se pudo actualizar")}), 400
    
    # Recalcular alertas inventario tras cambios
    try:
        supabase.rpc("evaluar_alertas_inventario", {
            "p_dias_caducar": 60,
            "p_umbral_bio_dosis": 500,
            "p_umbral_ins_unidades": 1500
        }).execute()
    except Exception:
        pass

    return jsonify({"ok": True})


@main_bp.route('/api/biologicos/estado-lote', methods=['POST'])
@role_required("ADMINISTRADOR")
def api_biologicos_estado_lote():
    data = request.get_json() or {}

    nombre_biologico = (data.get("nombre_biologico") or "").strip().upper()
    lote = (data.get("lote") or "").strip()
    estado = data.get("estado")

    if not nombre_biologico or not lote or estado is None:
        return jsonify({"message": "Datos incompletos."}), 400

    if isinstance(estado, str):
        estado = estado.strip().lower() == "true"
    else:
        estado = bool(estado)

    res = set_biologico_estado(nombre_biologico, lote, estado)

    # Normalizar respuesta (puede venir como lista o dict)
    row = None
    if isinstance(res, list) and res:
        row = res[0]
    elif isinstance(res, dict):
        row = res

    if not row or not row.get("ok"):
        return jsonify({"message": row.get("message") if row else "No se pudo actualizar"}), 400
    
    # Recalcular alertas inventario tras cambios
    try:
        supabase.rpc("evaluar_alertas_inventario", {
            "p_dias_caducar": 60,
            "p_umbral_bio_dosis": 500,
            "p_umbral_ins_unidades": 1500
        }).execute()
    except Exception:
        pass


    return jsonify({"ok": True, "estado": estado})

@main_bp.route('/api/biologicos/focus', methods=['GET'])
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_biologicos_focus():
    focus_id = request.args.get("focus_id")
    lote = request.args.get("lote")

    p_focus_id = None
    if focus_id and str(focus_id).strip().isdigit():
        p_focus_id = int(focus_id.strip())

    p_lote = (lote or "").strip() or None

    if p_focus_id is None and p_lote is None:
        return jsonify({"ok": False, "message": "Falta focus_id o lote"}), 400

    try:
        r = supabase.rpc("find_biologico_focus", {
            "p_focus_id": p_focus_id,
            "p_lote": p_lote
        }).execute()
        rows = r.data or []
    except Exception as e:
        return jsonify({"ok": False, "message": "Error consultando focus", "detail": str(e)}), 500

    if not rows:
        return jsonify({"ok": False, "message": "No se encontró el biológico para el foco"}), 404

    row = rows[0]
    return jsonify({
        "ok": True,
        "id_biologico": row.get("id_biologico"),
        "nombre_biologico": row.get("nombre_biologico"),
        "lote": row.get("lote")
    })


# ==========================
# INSUMOS (ADMINISTRADOR + COORDINADOR)
# ==========================
@main_bp.route('/insumos')
@role_required("ADMINISTRADOR", "COORDINADOR")
def insumos():
    user, data = build_context()
    return render_template("insumos.html", user=user, data=data)


@main_bp.route('/api/insumos/categorias')
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_insumos_categorias():
    return jsonify(list_categorias(True))


@main_bp.route('/api/insumos/tipos')
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_insumos_tipos():
    categoria = request.args.get("categoria", "").strip()
    q = request.args.get("q", "").strip() or None

    estado_raw = request.args.get("estado", "").strip().lower()
    estado = None
    if estado_raw == "true":
        estado = True
    elif estado_raw == "false":
        estado = False

    exp_raw = request.args.get("exp", "").strip()
    exp_days = int(exp_raw) if exp_raw.isdigit() else None

    if not categoria:
        return jsonify([])

    return jsonify(list_tipos(categoria, q=q, estado=estado, exp_days=exp_days))


@main_bp.route('/api/insumos/lotes')
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_insumos_lotes():
    categoria = request.args.get("categoria", "").strip()
    nombre_tipo = request.args.get("nombre_tipo", "").strip()

    estado_raw = request.args.get("estado", "").strip().lower()
    estado = None
    if estado_raw == "true":
        estado = True
    elif estado_raw == "false":
        estado = False

    if not categoria or not nombre_tipo:
        return jsonify([])

    return jsonify(get_lotes(categoria, nombre_tipo, estado=estado))


@main_bp.route('/api/insumos/vacunas')
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_insumos_vacunas():
    nombre_tipo = request.args.get("nombre_tipo", "").strip()
    if not nombre_tipo:
        return jsonify([])

    return jsonify(get_biologicos_asociados(nombre_tipo))


@main_bp.route('/api/insumos/registrar', methods=['POST'])
@role_required("ADMINISTRADOR")  
def api_insumos_registrar():
    data = request.get_json() or {}

    categoria = (data.get("categoria") or "").upper().strip()

    # Puede venir base o final (si más adelante lo usas)
    nombre_base = (data.get("nombre_tipo_base") or "").strip()
    nombre_final = (data.get("nombre_tipo_final") or "").strip()

    lote = (data.get("lote") or "").strip()
    packs = int(data.get("packs") or 0)

    fab_month = (data.get("fab_month") or "").strip()   # "YYYY-MM" o ""
    cad_month = (data.get("cad_month") or "").strip()   # "YYYY-MM" obligatorio

    alcohol_cap = data.get("alcohol_cap_ml")
    alcohol_cap = int(alcohol_cap) if alcohol_cap else None

    if not categoria or not lote or not cad_month:
        return jsonify({"message": "Completa categoría, lote y caducidad."}), 400

    # ===========================
    # Construcción del nombre tipo
    # ===========================
    if categoria == "ALCOHOL":
        # Para alcohol SIEMPRE exigimos capacidad
        if not alcohol_cap:
            return jsonify({"message": "Selecciona la capacidad del alcohol (ml)."}), 400

        # Si por error te mandan "Alcohol 70% 1000ml" en base, limpiamos el sufijo ml
        cleaned = nombre_base or nombre_final
        cleaned = cleaned.strip()

        if not cleaned:
            return jsonify({"message": "Completa el nombre del tipo (ej: Alcohol 70%)."}), 400

        # quita "####ml" del final si viene pegado
        cleaned = re.sub(r"\s*\d{2,4}\s*ml\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        # quita "galon/galón" si lo usaste en nombre
        cleaned = re.sub(r"\s*gal[oó]n\s*$", "", cleaned, flags=re.IGNORECASE).strip()

        # Nombre final único y estable
        nombre_tipo = f"{cleaned} {alcohol_cap}ml"

    else:
        # Para otras categorías:
        # - si viene nombre_final úsalo
        # - si no, usa nombre_base
        nombre_tipo = (nombre_final or nombre_base).strip()
        if not nombre_tipo:
            return jsonify({"message": "Completa el nombre del tipo."}), 400

    # ===========================
    # Calcular unidades SIEMPRE
    # ===========================
    unidades = calcular_unidades(categoria, packs, alcohol_cap)

    if unidades <= 0:
        return jsonify({"message": "Las unidades calculadas no pueden ser 0. Revisa packs/capacidad."}), 400

    # ===========================
    # Fechas month -> date
    # ===========================
    fecha_fab = month_to_first_day(fab_month) if fab_month else None
    fecha_cad = month_to_last_day(cad_month)

    # ===========================
    # Guardar (RPC UPSERT)
    # ===========================
    upsert_insumo_lote(
        categoria=categoria,
        nombre_tipo=nombre_tipo,
        lote=lote,
        packs=packs,
        unidades=unidades,
        fecha_fabricacion=fecha_fab,
        fecha_caducidad=fecha_cad
    )

    # Recalcular alertas inventario tras cambios
    try:
        supabase.rpc("evaluar_alertas_inventario", {
            "p_dias_caducar": 60,
            "p_umbral_bio_dosis": 500,
            "p_umbral_ins_unidades": 1500
        }).execute()
    except Exception:
        pass


    return jsonify({"ok": True, "nombre_tipo": nombre_tipo})


@main_bp.route('/api/insumos/editar-lote', methods=['POST'])
@role_required("ADMINISTRADOR")
def api_insumos_editar_lote():
    data = request.get_json() or {}

    categoria = (data.get("categoria") or "").upper().strip()
    nombre_tipo = (data.get("nombre_tipo") or "").strip()
    lote = (data.get("lote") or "").strip()
    packs = int(data.get("packs") or 0)

    fab_month = (data.get("fab_month") or "").strip()
    cad_month = (data.get("cad_month") or "").strip()

    if not categoria or not nombre_tipo or not lote or not cad_month:
        return jsonify({"message":"Datos incompletos."}), 400

    alcohol_cap = None
    if categoria == "ALCOHOL":
        # extraer capacidad desde el nombre_tipo "Alcohol 70% 1000ml"
        import re
        m = re.search(r'(\d{2,4})\s*ml', nombre_tipo.lower())
        alcohol_cap = int(m.group(1)) if m else None

    unidades = calcular_unidades(categoria, packs, alcohol_cap)
    if unidades <= 0:
        return jsonify({"message":"Unidades calculadas inválidas. Revisa packs."}), 400

    fecha_fab = month_to_first_day(fab_month) if fab_month else None
    fecha_cad = month_to_last_day(cad_month)

    res = update_insumo_lote(categoria, nombre_tipo, lote, packs, unidades, fecha_fab, fecha_cad)
    if not res or not res.get("ok"):
        return jsonify({"message": (res.get("message") if res else "No se pudo actualizar")}), 400
    
    # Recalcular alertas inventario tras cambios
    try:
        supabase.rpc("evaluar_alertas_inventario", {
            "p_dias_caducar": 60,
            "p_umbral_bio_dosis": 500,
            "p_umbral_ins_unidades": 1500
        }).execute()
    except Exception:
        pass

    return jsonify({"ok": True})


@main_bp.route('/api/insumos/estado-lote', methods=['POST'])
@role_required("ADMINISTRADOR")
def api_insumos_estado_lote():
    data = request.get_json() or {}

    categoria = (data.get("categoria") or "").upper().strip()
    nombre_tipo = (data.get("nombre_tipo") or "").strip()
    lote = (data.get("lote") or "").strip()
    estado = data.get("estado")

    if estado is None or not categoria or not nombre_tipo or not lote:
        return jsonify({"message":"Datos incompletos."}), 400
    
    estado = data.get("estado")

    if isinstance(estado, str):
        estado = estado.strip().lower() == "true"
    else:
        estado = bool(estado)


    res = set_insumo_estado(categoria, nombre_tipo, lote, estado)
    if not res or not res.get("ok"):
        return jsonify({"message": (res.get("message") if res else "No se pudo actualizar")}), 400
    
    # Recalcular alertas inventario tras cambios
    try:
        supabase.rpc("evaluar_alertas_inventario", {
            "p_dias_caducar": 60,
            "p_umbral_bio_dosis": 500,
            "p_umbral_ins_unidades": 1500
        }).execute()
    except Exception:
        pass


    return jsonify({"ok": True})


# ==========================
# REPORTES
# ==========================
@main_bp.route('/reportes')
@login_required
def reportes():
    user, data = build_context()
    return render_template("reportes.html", user=user, data=data)


@main_bp.route('/api/reportes', methods=['GET'])
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_reportes():
    tipo = (request.args.get("tipo") or "").strip().upper()
    fecha = (request.args.get("fecha") or "").strip()

    if tipo not in ["ANUAL","MENSUAL","DIARIO"] or not fecha:
        return jsonify({"message":"Parámetros inválidos."}), 400

    if tipo == "ANUAL":
        rep = supabase.rpc("reporte_anual_agregado", {"p_year": fecha}).execute().data
    elif tipo == "MENSUAL":
        rep = supabase.rpc("reporte_mensual_agregado", {"p_month": fecha}).execute().data
    else:
        rep = supabase.rpc("reporte_diario_agregado", {"p_date": fecha}).execute().data

    als = supabase.rpc("list_alertas_periodo", {"p_tipo": tipo, "p_fecha": fecha}).execute().data

    return jsonify({"reporte": rep, "alertas": als or []})

@main_bp.route('/api/insumos/focus', methods=['GET'])
@role_required("ADMINISTRADOR", "COORDINADOR")
def api_insumos_focus():
    focus_id = request.args.get("focus_id")
    lote = request.args.get("lote")

    p_focus_id = None
    if focus_id and str(focus_id).strip().isdigit():
        p_focus_id = int(focus_id.strip())

    p_lote = (lote or "").strip() or None

    if p_focus_id is None and p_lote is None:
        return jsonify({"ok": False, "message": "Falta focus_id o lote"}), 400

    try:
        r = supabase.rpc("find_insumo_focus", {
            "p_focus_id": p_focus_id,
            "p_lote": p_lote
        }).execute()
        rows = r.data or []
    except Exception as e:
        return jsonify({"ok": False, "message": "Error consultando focus", "detail": str(e)}), 500

    if not rows:
        return jsonify({"ok": False, "message": "No se encontró el insumo para el foco"}), 404

    row = rows[0]
    return jsonify({
        "ok": True,
        "id_insumo": row.get("id_insumo"),
        "categoria": row.get("categoria"),
        "nombre_tipo": row.get("nombre_tipo"),
        "lote": row.get("lote")
    })


@main_bp.route('/api/reportes/pdf', methods=['GET'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_reportes_pdf():
    tipo = (request.args.get("tipo") or "").strip().upper()
    fecha = (request.args.get("fecha") or "").strip()

    if tipo not in ["ANUAL","MENSUAL","DIARIO"] or not fecha:
        return jsonify({"message":"Parámetros inválidos."}), 400

    # Reporte principal (misma lógica que /api/reportes)
    if tipo == "ANUAL":
        rep = supabase.rpc("reporte_anual_agregado", {"p_year": fecha}).execute().data
    elif tipo == "MENSUAL":
        rep = supabase.rpc("reporte_mensual_agregado", {"p_month": fecha}).execute().data
    else:
        rep = supabase.rpc("reporte_diario_agregado", {"p_date": fecha}).execute().data

    # Alertas resumen (tabla)
    als_resumen = supabase.rpc("list_alertas_periodo", {"p_tipo": tipo, "p_fecha": fecha}).execute().data or []

    # Alertas detalle (para marcar con novedad por fecha/mes y mostrar detalle)
    als_detalle = supabase.rpc("list_alertas_detalle_periodo", {"p_tipo": tipo, "p_fecha": fecha}).execute().data or []

    pdf_bytes = build_prass_report_pdf(
        tipo=tipo,
        fecha=fecha,
        rep=rep or {},
        alertas_resumen=als_resumen,
        alertas_detalle=als_detalle
    )

    filename = f"INFORME_PRASS_{tipo}_{fecha}.pdf".replace(" ", "_")
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


# ==========================
# ALERTAS
# ==========================
@main_bp.route('/alertas')
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def alertas():
    user, data = build_context()

    # tu id es id_usuario (confirmado)
    user_role = (user.get("rol") or user.get("role") or user.get("tipo") or "").strip().upper()

    return render_template("alertas.html", user=user, data=data, user_role=user_role)


@main_bp.route('/api/alertas', methods=['GET'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_alertas_list():
    estado = (request.args.get("estado") or "PENDIENTE").strip().upper()
    tipo_entidad = (request.args.get("tipo_entidad") or "").strip().upper() or None
    refresh = (request.args.get("refresh") or "").strip() == "1"

    user, _ = build_context()
    user_role = (user.get("rol") or user.get("role") or user.get("tipo") or "").strip().upper()

    # Solo admin/coordinador pueden forzar refresh
    # Y solo tiene sentido si estás viendo inventario o si pides refresh explícito
    want_inventory = (tipo_entidad in ["INSUMO", "BIOLOGICO"]) or (tipo_entidad is None)
    if user_role in ["ADMINISTRADOR", "COORDINADOR"] and want_inventory and refresh:
        try:
            supabase.rpc(
                "evaluar_alertas_inventario",
                {"p_dias_caducar": 60, "p_umbral_bio_dosis": 500, "p_umbral_ins_unidades": 1500}
            ).execute()
        except Exception:
            pass

    res = supabase.rpc("list_alertas_pendientes", {
        "p_estado": estado,
        "p_tipo_entidad": tipo_entidad
    }).execute().data

    return jsonify(res or [])


@main_bp.route('/api/alertas/accion', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_alertas_accion():
    payload = request.get_json() or {}
    id_alerta = payload.get("id_alerta")
    accion = (payload.get("accion") or "").strip().upper()
    accion_detalle = (payload.get("accion_detalle") or "").strip()

    if not id_alerta or accion not in ["CORREGIR", "RESOLVER"]:
        return jsonify({"ok": False, "message": "Parámetros inválidos."}), 400

    user, _ = build_context()
    id_usuario = user.get("id_usuario")
    if not id_usuario:
        return jsonify({"ok": False, "message": "No se pudo identificar el usuario en sesión."}), 400

    user_role = (user.get("rol") or user.get("role") or user.get("tipo") or "").strip().upper()

    # Control de permisos
    if accion == "CORREGIR":
        if user_role not in ["ADMINISTRADOR", "COORDINADOR"]:
            return jsonify({"ok": False, "message": "No tienes permisos para corregir alertas."}), 403

        out = supabase.rpc("alerta_corregir_registro", {
            "p_id_alerta": int(id_alerta),
            "p_id_usuario": int(id_usuario),
            "p_accion_detalle": accion_detalle
        }).execute().data

        return jsonify(out or {"ok": False})

    # RESOLVER = GESTIONAR inventario (solo admin)
    if user_role != "ADMINISTRADOR":
        return jsonify({"ok": False, "message": "Solo el ADMINISTRADOR puede gestionar inventario."}), 403

    out = supabase.rpc("alerta_redirect_inventario", {
        "p_id_alerta": int(id_alerta)
    }).execute().data

    return jsonify(out or {"ok": False})

# ==========================
# CONSULTAS RAPIDAS
# ==========================
@main_bp.route('/consultas')
@login_required
def consultas():
    user, data = build_context()
    return render_template("consultas.html", user=user, data=data)


@main_bp.route('/consulta-rapida')
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def consulta_rapida_view():
    user, data = build_context()
    return render_template("consulta_rapida.html", user=user, data=data)


@main_bp.route('/api/consulta-rapida/procesar', methods=['POST'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_consulta_rapida_procesar():
    user, _ = build_context()
    user_id = int(user.get("id_usuario"))

    if 'file' not in request.files:
        return jsonify({"ok": False, "message": "No se envió archivo."}), 400

    f = request.files['file']
    filename = (f.filename or "archivo").strip()
    content = f.read()
    if not content:
        return jsonify({"ok": False, "message": "El archivo está vacío."}), 400

    #  NUEVO: sin tipo/mes/día (multi-mes automático)
    out = process_in_memory(
        user_id=user_id,
        filename=filename,
        content=content
    )

    return jsonify(out), 200


@main_bp.route('/api/consulta-rapida/registros', methods=['GET'])
@login_required
@role_required("ADMINISTRADOR", "COORDINADOR", "ASISTENTE")
def api_consulta_rapida_registros():
    user, _ = build_context()
    user_id = int(user.get("id_usuario"))

    session_key = (request.args.get("session_key") or "").strip()
    page = request.args.get("page") or 1
    page_size = request.args.get("page_size") or 25

    out = get_cached_registros_page(
        user_id=user_id,
        session_key=session_key,
        page=int(page),
        page_size=int(page_size),
        estado=request.args.get("estado") or "",
        vacuna=request.args.get("vacuna") or "",
        captacion=request.args.get("captacion") or "",
        cedula=request.args.get("cedula") or "",
        fecha=request.args.get("fecha") or "",
        nombre=request.args.get("nombre") or ""
    )

    status = 200 if out.get("ok") else 400
    return jsonify(out), status


#==========================
###CHATBOT PRASS
#=========================

@main_bp.post("/api/chat")
@login_required
def api_chat():
    p = request.get_json() or {}
    message = (p.get("message") or "").strip()
    if not message:
        return jsonify({"reply": "Escribe una consulta para poder ayudarte.", "engine": "none"}), 400

    user, _ = build_context()
    id_usuario = int(user.get("id_usuario") or 0)
    if not id_usuario:
        return jsonify({"reply": "No se pudo identificar al usuario.", "engine": "none"}), 400

    # 1) conversation_id persistente por sesión del navegador
    conv_id = session.get("chat_conversation_id")
    if not conv_id:
        conv_id = ChatbotService.start_conversation(id_usuario=id_usuario, metadata={
            "channel": "web",
            # opcional: user-agent
            "ua": request.headers.get("User-Agent", "")
        })
        session["chat_conversation_id"] = conv_id

    # 2) log del mensaje del usuario
    ChatbotService.log_message(
        conversation_id=conv_id,
        id_usuario=id_usuario,
        role="user",
        text=message,
        source="web",
    )

    # 3) llamar a Rasa
    session_id = str(id_usuario)  # tu sender por usuario (ok)
    try:
        ChatbotService.update_memory_from_text(id_usuario, message)
        message2 = ChatbotService.enrich_message_with_memory(id_usuario, message)
        reply = ChatbotService.ask_rasa(message2, session_id=session_id)

        # 4) si Rasa devuelve texto, log del bot
        if reply:
            ChatbotService.update_memory_from_bot_reply(id_usuario, reply)

            ChatbotService.log_message(
                conversation_id=conv_id,
                id_usuario=id_usuario,
                role="bot",
                text=reply,
                source="rasa",
            )
            return jsonify({"reply": reply, "engine": "rasa"})

        # 5) Rasa respondió vacío -> fallback front (log opcional)
        ChatbotService.log_message(
            conversation_id=conv_id,
            id_usuario=id_usuario,
            role="bot",
            text="",
            source="rasa",
            error={"warning": "empty_reply"}
        )
        return jsonify({"reply": "", "engine": "fallback"}), 200

    except Exception as e:
        # 6) Rasa caído -> fallback front (log del error)
        ChatbotService.log_message(
            conversation_id=conv_id,
            id_usuario=id_usuario,
            role="bot",
            text="",
            source="rasa",
            error={"error": "rasa_down_or_error", "detail": str(e)}
        )
        return jsonify({"reply": "", "engine": "fallback"}), 200



@main_bp.get("/api/bot/reporte-mensual")
@require_bot_key
def bot_reporte_mensual():
    month = (request.args.get("month") or "").strip()
    if not month:
        return jsonify({"error": "Falta month"}), 400
    try:
        rep = supabase.rpc("reporte_mensual_agregado", {"p_month": month}).execute().data
        rep0 = rep[0] if isinstance(rep, list) and rep else rep
        if isinstance(rep0, dict) and len(rep0.keys()) == 1:
            rep0 = list(rep0.values())[0]
        rep0 = rep0 or {}
        return jsonify({"data": rep0})
    except Exception:
        return jsonify({"error": "No se pudo obtener reporte"}), 500


@main_bp.get("/api/bot/historial-paciente")
@require_bot_key
def bot_historial_paciente():
    cedula = (request.args.get("cedula") or "").strip()
    if not cedula:
        return jsonify({"error": "Falta cedula"}), 400

    try:
        rows = supabase.rpc("historial_paciente", {"p_cedula": cedula}).execute().data or []
        if not rows:
            return jsonify({"rows": []}), 404

        datos = (rows[0].get("datos_archivo") or {}) if isinstance(rows[0], dict) else {}
        paciente = paciente_from_datos(datos, cedula)

        return jsonify({"paciente": paciente, "rows": rows})
    except Exception:
        return jsonify({"error": "No se pudo obtener historial"}), 500



@main_bp.get("/api/bot/contar-vacuna-dia")
@require_bot_key
def bot_contar_vacuna_dia():
    vacuna = (request.args.get("vacuna") or "").strip()
    fecha = (request.args.get("fecha") or "").strip()  # YYYY-MM-DD
    if not vacuna or not fecha:
        return jsonify({"error": "Falta vacuna o fecha"}), 400

    try:
        yyyy, mm, dd = fecha.split("-")
        r = supabase.rpc("count_registros", {
            "p_year": yyyy,
            "p_month": mm,
            "p_day": dd,
            "p_sexo": "",
            "p_esquema": "",
            "p_grupo_riesgo": "",
            "p_vacuna": vacuna,
            "p_estado": "",
            "p_nombre": "",
            "p_cedula": "",
            "p_edad_min": None,
            "p_edad_max": None
        }).execute().data
        total = r[0]["total"] if r else 0
        return jsonify({"total": total})
    except Exception:
        return jsonify({"error": "No se pudo contar"}), 500


@main_bp.get("/api/bot/paciente-dato")
@require_bot_key
def bot_paciente_dato():
    cedula = (request.args.get("cedula") or "").strip()
    dato_raw = (request.args.get("dato") or "").strip()

    if not cedula or not dato_raw:
        return jsonify({"error": "Falta cedula o dato"}), 400

    dato = dato_normalizado(dato_raw)

    try:
        rows = supabase.rpc("historial_paciente", {"p_cedula": cedula}).execute().data or []
    except Exception:
        rows = []

    if not rows:
        return jsonify({"cedula": cedula, "dato": dato, "valor": None, "error": "Sin registros"}), 404

    last = rows[-1]
    datos = last.get("datos_archivo") or {}

    # nombres / apellidos compuestos (especial)
    if dato in ["nombres", "nombre_completo"]:
        pn = pick_value(datos, "primer_nombre") or ""
        sn = pick_value(datos, "segundo_nombre") or ""
        ap = pick_value(datos, "apellido_paterno") or ""
        am = pick_value(datos, "apellido_materno") or ""
        full = " ".join([x for x in [pn, sn, ap, am] if str(x).strip() != ""]).strip() or None
        return jsonify({
            "cedula": cedula,
            "dato": "nombres",
            "valor": full,
            "fuente": "datos_archivo",
            "fecha_vacunacion": str(last.get("fecha_vacunacion") or pick_value(datos, "fecha_vacunacion") or "")
        })

    if dato in ["apellidos"]:
        ap = pick_value(datos, "apellido_paterno") or ""
        am = pick_value(datos, "apellido_materno") or ""
        full = " ".join([x for x in [ap, am] if str(x).strip() != ""]).strip() or None
        return jsonify({
            "cedula": cedula,
            "dato": "apellidos",
            "valor": full,
            "fuente": "datos_archivo",
            "fecha_vacunacion": str(last.get("fecha_vacunacion") or pick_value(datos, "fecha_vacunacion") or "")
        })


    # edad compuesta (especial)
    if dato in ["edad", "edad_texto"]:
        return jsonify({
            "cedula": cedula,
            "dato": "edad",
            "valor": edad_texto(datos),
            "fuente": "datos_archivo",
            "fecha_vacunacion": str(last.get("fecha_vacunacion") or pick_value(datos, "fecha_vacunacion") or "")
        })

    if dato not in PACIENTE_DATO_MAP:
        return jsonify({
            "error": "Dato no permitido",
            "dato": dato,
            "permitidos": sorted(PACIENTE_DATO_MAP.keys())
        }), 400

    key, fuente = PACIENTE_DATO_MAP[dato]
    valor = pick_value(datos, key)

    # fallback a columnas del RPC si aplica
    if valor is None:
        if dato == "vacuna_canon":
            valor = last.get("vacuna_canon")
        elif dato == "vacuna_raw":
            valor = last.get("vacuna_raw")
        elif dato == "esquema":
            valor = last.get("esquema")
        elif dato == "dosis":
            valor = last.get("dosis")

    return jsonify({
        "cedula": cedula,
        "dato": dato,
        "valor": valor,
        "fuente": fuente,
        "fecha_vacunacion": str(last.get("fecha_vacunacion") or pick_value(datos, "fecha_vacunacion") or "")
    })


@main_bp.get("/api/bot/conteo-total-dia")
@require_bot_key
def bot_conteo_total_dia():
    fecha = request.args.get("fecha", "").strip()
    if not fecha:
        return jsonify({"error": "Falta fecha"}), 400

    r = supabase.rpc("bot_conteo_total_dia", {"p_fecha": fecha}).execute()
    total = int(((r.data or [{}])[0] or {}).get("total", 0) or 0)
    return jsonify({"total": total})


@main_bp.get("/api/bot/conteo-captacion-periodo")
@require_bot_key
def bot_conteo_captacion_periodo():
    month = (request.args.get("month") or "").strip()

    capt_raw = (request.args.get("captacion") or "").strip().lower()
    capt_raw = capt_raw.replace("tardía", "tardia")

    # normaliza campaña: campaña/campana -> campania (sin ñ)
    if "camp" in capt_raw:
        capt = "campania"
    elif capt_raw in ("temprana", "tardia"):
        capt = capt_raw
    else:
        return jsonify({"error": "Parámetros inválidos"}), 400

    if not month:
        return jsonify({"error": "Parámetros inválidos"}), 400

    r = supabase.rpc(
        "bot_conteo_captacion_periodo",
        {"p_month": month, "p_captacion": capt}
    ).execute()

    total = int(((r.data or [{}])[0] or {}).get("total", 0) or 0)
    return jsonify({"total": total})



@main_bp.get("/api/bot/top-mes-anio")
@require_bot_key
def bot_top_mes_anio():
    anio = request.args.get("anio", "").strip()
    if not anio.isdigit():
        return jsonify({"error": "Año inválido"}), 400

    r = supabase.rpc("bot_top_mes_anio", {"p_anio": int(anio)}).execute()
    if not r.data:
        return jsonify({"month": None, "total": 0})

    row = r.data[0] or {}
    return jsonify({"month": row.get("month"), "total": int(row.get("total", 0) or 0)})


@main_bp.get("/api/bot/insumo/categorias")
@require_bot_key
def bot_insumo_categorias():
    r = supabase.rpc("list_insumo_categorias", {"p_only_active": True}).execute()
    return jsonify({"data": r.data or []})


@main_bp.get("/api/bot/insumo/tipos")
@require_bot_key
def bot_insumo_tipos():
    categoria = (request.args.get("categoria") or "").strip().upper()
    q = request.args.get("q")
    estado = request.args.get("estado")
    exp_days = request.args.get("exp_days")
    excluir_caducados = request.args.get("excluir_caducados", "true").lower() != "false"

    payload = {
        "p_categoria": categoria,
        "p_q": q if q else None,
        "p_estado": True if estado is None else estado.lower() == "true",
        "p_exp_days": int(exp_days) if exp_days else None,
        "p_excluir_caducados": excluir_caducados,
    }

    r = supabase.rpc("list_insumo_tipos", payload).execute()
    return jsonify({"data": r.data or []})


@main_bp.get("/api/bot/insumo/lotes")
@require_bot_key
def bot_insumo_lotes():
    categoria = (request.args.get("categoria") or "").strip().upper()
    tipo = (request.args.get("tipo") or "").strip()
    estado = request.args.get("estado")

    if not categoria or not tipo:
        return jsonify({"error": "Falta categoría o tipo"}), 400

    payload = {
        "p_categoria": categoria,
        "p_nombre_tipo": tipo,
        "p_estado": None if estado is None else estado.lower() == "true",
    }

    r = supabase.rpc("get_insumo_lotes", payload).execute()
    return jsonify({"data": r.data or []})


@main_bp.get("/api/bot/insumo/biologicos-asociados")
@require_bot_key
def bot_insumo_biologicos_asociados():
    tipo = (request.args.get("tipo") or "").strip()
    if not tipo:
        return jsonify({"error": "Falta tipo de insumo"}), 400

    r = supabase.rpc(
        "get_biologicos_asociados",
        {"p_nombre_tipo_insumo": tipo}
    ).execute()

    return jsonify({"data": r.data or []})


@main_bp.get("/api/bot/biologico/detalle")
@require_bot_key
def bot_biologico_detalle():
    nombre = (request.args.get("nombre") or "").strip()
    if not nombre:
        return jsonify({"error": "Falta nombre"}), 400

    r = supabase.rpc("get_biologico_detalle", {"p_nombre_biologico": nombre}).execute()
    rows = r.data or []
    if not rows:
        return jsonify({"error": "No encontrado"}), 404

    return jsonify({"data": rows[0]})


@main_bp.get("/api/bot/pacientes/proxima-dosis-hoy")
@require_bot_key
def bot_pacientes_proxima_dosis_hoy():
    limit_ = request.args.get("limit", "").strip()
    limit_val = 50
    if limit_.isdigit():
        limit_val = max(1, min(200, int(limit_)))

    r = supabase.rpc("bot_pacientes_proxima_dosis_hoy", {"p_limit": limit_val}).execute()
    return jsonify({"data": r.data or []})


@main_bp.get("/api/bot/vacunacion/query")
@require_bot_key
def bot_vacunacion_query():
    qtype = (request.args.get("qtype") or "").strip()
    periodo = request.args.get("periodo")
    vacuna = request.args.get("vacuna")
    captacion = request.args.get("captacion")
    fecha = request.args.get("fecha")
    anio = request.args.get("anio")
    limit_ = request.args.get("limit")
    offset_ = request.args.get("offset")

    payload = {
        "p_qtype": qtype,
        "p_periodo": periodo,
        "p_vacuna": vacuna,
        "p_captacion": captacion,
        "p_fecha": fecha,  # date string ok
        "p_anio": int(anio) if (anio and str(anio).isdigit()) else None,
        "p_limit": int(limit_) if (limit_ and str(limit_).isdigit()) else 50,
        "p_offset": int(offset_) if (offset_ and str(offset_).isdigit()) else 0,
    }

    r = supabase.rpc("bot_vacunacion_query", payload).execute()
    return jsonify({"data": r.data, "meta": {"qtype": qtype, "params": payload}})
