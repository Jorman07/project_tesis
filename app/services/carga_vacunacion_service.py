import hashlib
import json
import re
from datetime import date
from app.services.prass_parser import parse_any_prass_file, try_parse_date

# -----------------------------
# Alias CANON de columnas
# -----------------------------
ALIASES = {
    "fecha_vacunacion": [
        "fecha_vacunacion", "fecha_vacunacion_vacunador", "fecha_vacunacion_vacunador_2",
        "fecha_de_vacunacion", "fecha_de_vacunacion_2"
    ],
    "fecha_proxima_dosis": [
        "fecha_proxima_dosis", "fecha_proxima_dosis_2",
        "fecha_de_proxima_dosis", "fecha_de_proxima_dosis_2"
    ],
    "vacuna": ["vacuna", "vacuna_parroquia", "vacuna_parroquia_2"],
    "dosis": ["dosis", "dosis_parroquia", "dosis_parroquia_2"],
    "esquema": ["esquema", "esquema_parroquia", "esquema_parroquia_2"],
    "lote": ["lote", "lote_parroquia", "lote_parroquia_2"],
    "tipo_identificacion": ["tipo_identificacion", "tipo_identificacion_2", "tipo_de_identificacion", "tipo_de_identificacion_2"],
    "numero_identificacion": ["numero_identificacion", "numero_identificacion_2", "numero_de_identificacion", "numero_de_identificacion_2"],
    "apellido_paterno": ["apellido_paterno", "apellido_paterno_2"],
    "apellido_materno": ["apellido_materno", "apellido_materno_2"],
    "primer_nombre": ["primer_nombre", "primer_nombre_2"],
    "segundo_nombre": ["segundo_nombre", "segundo_nombre_2"],
    "sexo": ["sexo", "sexo_nombre", "sexo_nombre_2", "genero", "genero_2"],
    "grupo_riesgo": ["grupo_de_riesgo", "grupo_de_riesgo_dosis", "grupo_de_riesgo_dosis_2"],
    "origen_datos": ["origen_datos", "origen_datos_dosis", "origen_datos_dosis_2"],
    "nacionalidad": ["nacionalidad", "nacionalidad_pais", "nacionalidad_pais_2", "nacionalidad_pais_3", "nacionalidad_pais_4", "nacionalidad_parroquia"],
    "pueblo": ["pueblo", "pueblo_pais", "pueblo_pais_2"],
}

def pick(row_dict, keys):
    for k in keys:
        v = row_dict.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""

def normalize_text(x: str) -> str:
    return " ".join((x or "").strip().split())

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def month_from_date(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"

def build_row_dict(headers, row):
    return {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}

# -----------------------------
# Captación desde ESQUEMA
# -----------------------------
def captacion_from_esquema(esq: str) -> str:
    s = normalize_text(esq).upper().strip()
    if not s:
        return "DESCONOCIDO"

    # 1) CAMPAÑA (acepta CAMPANA / CAMPAÑA / CAMP)
    if "CAMP" in s:
        return "CAMPANIA"

    # 2) TEMPRANA / TARDIA (aunque NO aparezca la palabra CAPTACION)
    if "TEMPRAN" in s:
        return "TEMPRANA"
    if "TARD" in s:
        return "TARDIA"

    # 3) Si menciona CAPTACION pero no indica tipo
    if "CAPTACION" in s or "CAPTACIÓN" in s:
        return "CAPTACION_OTRO"

    # 4) No se pudo clasificar
    return "NO_CAPTACION"


# -----------------------------
# Normalización de vacuna (CANON + VARIANTE)
# -----------------------------
def normalize_vacuna(v: str) -> tuple[str, str]:
    raw = (v or "").strip()
    if not raw:
        return ("", "")

    s = raw.upper()
    s = re.sub(r"\s+", " ", s).strip()

    # COVID / SPIKEVAX
    if "SPIKEVAX" in s or "COVID" in s:
        if "SPIKEVAX" in s:
            return ("COVID", "COVID_SPIKEVAX")
        return ("COVID", "COVID")

    # INFLUENZA / INFLUENCIA
    if "INFLUENZ" in s or "INFLUENCI" in s:
        if "1 A" in s or "2A" in s or "MESES" in s or "DIAS" in s:
            return ("INFLUENZA PEDIATRICA", "INFLUENZA_MENOR")
        if "A 11" in s or "meses" in s or "dias" in s:
            return ("INFLUENZA PEDIATRICA", "INFLUENZA_MENOR")
        if " 3 A" in s or "5 A" in s:
            return ("INFLUENZA ADULTO", "INFLUENZA_ADULTO")
        if "MAYOR" in s or "" in s:
            return ("INFLUENZA ADULTO", "INFLUENZA_ADULTO")
        return ("INFLUENZA", "INFLUENZA")

    # Fiebre amarilla
    if "FIEBRE AMARILLA" in s or s == "FA" or s.startswith("FA "):
        if "COMPLET" in s:
            return ("FA", "FA_COMPLETO")
        return ("FA", "FA")

    # SRP
    if s.startswith("SRP") or "SARAMP" in s or "RUBE" in s or "PAROTID" in s:
        if "SEGUNDA" in s or "2" in s:
            return ("SRP", "SRP_SEGUNDA")
        return ("SRP", "SRP")

    # Neumococo
    if "NEUMOCOCO" in s:
        if "13" in s:
            return ("NEUMOCOCO13", "NEUMOCOCO13")
        return ("NEUMOCOCO", "NEUMOCOCO")

    if "ROTAVIRUS" in s:
        return ("ROTAVIRUS", "ROTAVIRUS")

    if "VARICELA" in s:
        return ("VARICELA", "VARICELA")

    if s == "BCG" or s.startswith("BCG "):
        return ("BCG", "BCG")

    # Polio
    if "BOPV" in s or s == "BOPV" or " OPV" in s or s.endswith(" OPV"):
        return ("BOPV", "BOPV")
    if "FIPV" in s or "IPV" in s:
        return ("FIPV", "FIPV")

    # Pentavalente / Hexavalente
    if "PENTAVALENTE" in s:
        return ("PENTAVALENTE", "PENTAVALENTE")
    if "HEXAVALENTE" in s or s.startswith("HEXA"):
        return ("HEXAVALENTE", "HEXAVALENTE")

    # Hepatitis B (HB)
    if s.startswith("HB") or "HEPATITIS B" in s:
        #  HB CERO como variante pediátrica
        if "CERO" in s:
            return ("HB PEDIATRICA", "HB PEDIATRICA")
        if "PEDI" in s:
            if "20" in s and "D" in s:
                return ("HB PEDIATRICA", "HB PEDIATRICA_20D")
            return ("HB PEDIATRICA", "HBPEDIATRICA")
        if "ADUL" in s:
            return ("HB ADULTO", "HB ADULTO")
        return ("HB", "HB")

    # VPH / HPV
    if s == "VPH" or s == "HPV" or "PAPILOMA" in s:
        return ("VPH", "VPH")

    # DT / dT / TDAP / DPT
    if "TDAP" in s:
        return ("TDAP", "TDAP")
    if s.startswith("DPT") or s.startswith("DTP"):
        return ("DPT", "DPT")
    if "DT ADUL" in s or s == "DT":
        return ("DT", "DT_ADULTO" if "ADUL" in s else "DT")
    if s.startswith("DT "):
        return ("DT", "DT")

    # Antirrábica
    if "RAB" in s:
        return ("ANTIRRABICA", "ANTIRRABICA")

    # fallback
    canon = re.sub(r"[^A-Z0-9]+", "_", s).strip("_")
    return (canon, canon)

# -----------------------------
# Pipeline Fase 2
# -----------------------------
def process_file_bytes(id_archivo: int, filename: str, content: bytes):
    parsed = parse_any_prass_file(filename, content)
    headers = parsed["headers_normalizados"]
    rows = parsed["rows"]

    registros = []
    alertas = []

    seen_event = {}  # hash_evento -> hash_fila

    validas = 0
    invalidas = 0
    conflictos = 0

    # Reportes (solo VALIDOS)
    rep_total_mes = {}                 # periodo -> total eventos
    rep_vacuna_mes = {}                # (periodo, vacuna) -> total eventos
    rep_total_dia = {}                 # (periodo, fecha_iso) -> total eventos
    rep_vacuna_dia = {}                # (periodo, fecha_iso, vacuna) -> total eventos

    # Captación por día
    rep_captacion_temprana_dia = {}    # (periodo, fecha_iso) -> total
    rep_captacion_tardia_dia = {}      # (periodo, fecha_iso) -> total

    # Personas únicas (solo VALIDOS)
    persons_mes = {}                   # periodo -> set(cedula)
    persons_mes_vac = {}               # (periodo, vacuna) -> set(cedula)
    persons_dia = {}                   # fecha_iso -> set(cedula)
    persons_dia_vac = {}               # (fecha_iso, vacuna) -> set(cedula)

    # vacunas que pueden venir sin dosis sin invalidar
    ALLOW_NO_DOSIS = {"INFLUENZA", "COVID", "INFLUENZA ADULTO", "INFLUENZA PEDIATRICA"}

    for r in rows:
        d = build_row_dict(headers, r)

        # CANON columnas
        fecha_vac_raw = pick(d, ALIASES["fecha_vacunacion"])
        fecha_vac = try_parse_date(fecha_vac_raw)

        vacuna_raw = normalize_text(pick(d, ALIASES["vacuna"]))
        vacuna_canon, vacuna_variante = normalize_vacuna(vacuna_raw)

        dosis = normalize_text(pick(d, ALIASES["dosis"]))
        esquema = normalize_text(pick(d, ALIASES["esquema"]))
        captacion = captacion_from_esquema(esquema)

        tipo_id = normalize_text(pick(d, ALIASES["tipo_identificacion"])).upper()
        num_id = normalize_text(pick(d, ALIASES["numero_identificacion"]))

        ap_pat = normalize_text(pick(d, ALIASES["apellido_paterno"])).upper()
        ap_mat = normalize_text(pick(d, ALIASES["apellido_materno"])).upper()
        pnom = normalize_text(pick(d, ALIASES["primer_nombre"])).upper()
        snom = normalize_text(pick(d, ALIASES["segundo_nombre"])).upper()

        sexo = normalize_text(pick(d, ALIASES["sexo"])).upper()
        lote = normalize_text(pick(d, ALIASES["lote"]))
        origen_datos = normalize_text(pick(d, ALIASES["origen_datos"]))
        grupo_riesgo = normalize_text(pick(d, ALIASES["grupo_riesgo"]))

        fecha_prox = try_parse_date(pick(d, ALIASES["fecha_proxima_dosis"]))
        nacionalidad = normalize_text(pick(d, ALIASES["nacionalidad"])).upper()
        pueblo = normalize_text(pick(d, ALIASES["pueblo"])).upper()

        estado = "VALIDO"
        errores = []

        # Validaciones críticas
        if not num_id:
            estado = "INVALIDO"; errores.append("numero_identificacion_vacio")
        if not vacuna_canon:
            estado = "INVALIDO"; errores.append("vacuna_vacia")
        if not fecha_vac:
            estado = "INVALIDO"; errores.append("fecha_vacunacion_invalida")

        # Dosis obligatoria salvo influenza/covid
        if vacuna_canon not in ALLOW_NO_DOSIS and not dosis:
            estado = "INVALIDO"; errores.append("dosis_vacia_no_permitida")

        # Periodo
        periodo = month_from_date(fecha_vac) if fecha_vac else ""

        # hash_evento (sin lote)
        clave_dosis = dosis if dosis else (esquema or "")
        event_key = f"{num_id}|{vacuna_canon}|{clave_dosis}|{fecha_vac.isoformat() if fecha_vac else ''}"
        hash_evento = sha256_text(event_key)

        # JSON completo (raw + canon + captación)
        datos_archivo = dict(d)
        datos_archivo["_vacuna_raw"] = vacuna_raw
        datos_archivo["_vacuna_canon"] = vacuna_canon
        datos_archivo["_vacuna_variante"] = vacuna_variante
        datos_archivo["_canon_fecha_vacunacion"] = fecha_vac.isoformat() if fecha_vac else ""
        datos_archivo["_captacion"] = captacion

        hash_fila = sha256_text(json.dumps(datos_archivo, sort_keys=True, ensure_ascii=False))

        # Conflictos (mismo evento, distinta fila)
        if hash_evento in seen_event and seen_event[hash_evento] != hash_fila:
            estado = "CONFLICTO"
            conflictos += 1
            alertas.append({
                "tipo_alerta": "CONFLICTO_EVENTO",
                "detalle": f"Conflicto {num_id} {vacuna_canon} {fecha_vac_raw}",
                "id_archivo": str(id_archivo),
                "estado": "PENDIENTE",
                "id_registro": None,

                # NUEVO: entidad
                "tipo_entidad": "REGISTRO",
                "entidad_id": None,
                "entidad_clave": hash_fila,

                "registro_json": datos_archivo,
                "hash_fila": hash_fila,
                "numero_identificacion": num_id,
                "vacuna": vacuna_canon,
                "fecha_vacunacion": fecha_vac.isoformat() if fecha_vac else ""
            })
        else:
            seen_event[hash_evento] = hash_fila

        # Alertas por nacionalidad/pueblo (no invalida)
        if nacionalidad and nacionalidad != "SIN DATOS" and not pueblo:
            alertas.append({
                "tipo_alerta": "NACIONALIDAD_SIN_PUEBLO",
                "detalle": f"{num_id} {vacuna_canon} {fecha_vac_raw}",
                "id_archivo": str(id_archivo),
                "estado": "PENDIENTE",
                "id_registro": None,

                #  NUEVO: entidad
                "tipo_entidad": "REGISTRO",
                "entidad_id": None,
                "entidad_clave": hash_fila,

                "registro_json": datos_archivo,
                "hash_fila": hash_fila,
                "numero_identificacion": num_id,
                "vacuna": vacuna_canon,
                "fecha_vacunacion": fecha_vac.isoformat() if fecha_vac else ""
            })

        # Invalidos
        if estado == "INVALIDO":
            invalidas += 1
            alertas.append({
                "tipo_alerta": "REGISTRO_INVALIDO",
                "detalle": f"{'|'.join(errores)} :: {num_id} {vacuna_canon} {fecha_vac_raw}",
                "id_archivo": str(id_archivo),
                "estado": "PENDIENTE",
                "id_registro": None,

                # NUEVO: entidad
                "tipo_entidad": "REGISTRO",
                "entidad_id": None,
                "entidad_clave": hash_fila,

                "registro_json": datos_archivo,
                "hash_fila": hash_fila,
                "numero_identificacion": num_id,
                "vacuna": vacuna_canon,
                "fecha_vacunacion": fecha_vac.isoformat() if fecha_vac else ""
            })
        elif estado == "VALIDO":
            validas += 1

        # Registro (se inserta también CONFLICTO/INVALIDO como estado)
        registros.append({
            "id_archivo": str(id_archivo),
            "periodo": periodo,
            "estado_registro": estado,
            "hash_evento": hash_evento,
            "hash_fila": hash_fila,

            "tipo_identificacion": tipo_id,
            "numero_identificacion": num_id,
            "apellido_paterno": ap_pat,
            "apellido_materno": ap_mat,
            "primer_nombre": pnom,
            "segundo_nombre": snom,
            "sexo": sexo,

            "vacuna": vacuna_canon,  # CANON en columna
            "dosis": dosis,
            "esquema": esquema,

            "fecha_vacunacion": fecha_vac.isoformat() if fecha_vac else "",
            "fecha_proxima_dosis": fecha_prox.isoformat() if fecha_prox else "",

            "grupo_riesgo": grupo_riesgo,
            "origen_datos": origen_datos,
            "lote": lote,

            "datos_archivo": datos_archivo
        })

        # Reportes/personas SOLO para validos con fecha
        if estado == "VALIDO" and fecha_vac:
            di = fecha_vac.isoformat()

            rep_total_mes[periodo] = rep_total_mes.get(periodo, 0) + 1
            rep_vacuna_mes[(periodo, vacuna_canon)] = rep_vacuna_mes.get((periodo, vacuna_canon), 0) + 1
            rep_total_dia[(periodo, di)] = rep_total_dia.get((periodo, di), 0) + 1
            rep_vacuna_dia[(periodo, di, vacuna_canon)] = rep_vacuna_dia.get((periodo, di, vacuna_canon), 0) + 1

            # captación por día desde esquema
            if captacion == "TEMPRANA":
                rep_captacion_temprana_dia[(periodo, di)] = rep_captacion_temprana_dia.get((periodo, di), 0) + 1
            elif captacion == "TARDIA":
                rep_captacion_tardia_dia[(periodo, di)] = rep_captacion_tardia_dia.get((periodo, di), 0) + 1

            if num_id:
                persons_mes.setdefault(periodo, set()).add(num_id)
                persons_mes_vac.setdefault((periodo, vacuna_canon), set()).add(num_id)
                persons_dia.setdefault(di, set()).add(num_id)
                persons_dia_vac.setdefault((di, vacuna_canon), set()).add(num_id)

    # Construcción reportes agregados
    reportes = []

    # Totales eventos (dosis)
    for periodo, v in rep_total_mes.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "TOTAL_MES", "fecha": "", "vacuna": "", "valor": v, "id_archivo": str(id_archivo)})

    for (periodo, vacuna), v in rep_vacuna_mes.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "TOTAL_POR_VACUNA_MES", "fecha": "", "vacuna": vacuna, "valor": v, "id_archivo": str(id_archivo)})

    for (periodo, di), v in rep_total_dia.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "TOTAL_DIA", "fecha": di, "vacuna": "", "valor": v, "id_archivo": str(id_archivo)})

    for (periodo, di, vacuna), v in rep_vacuna_dia.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "TOTAL_DIA_POR_VACUNA", "fecha": di, "vacuna": vacuna, "valor": v, "id_archivo": str(id_archivo)})

    # Captación por día (temprana/tardía)
    for (periodo, di), v in rep_captacion_temprana_dia.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "TOTAL_DIA_CAPTACION_TEMPRANA", "fecha": di, "vacuna": "", "valor": v, "id_archivo": str(id_archivo)})

    for (periodo, di), v in rep_captacion_tardia_dia.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "TOTAL_DIA_CAPTACION_TARDIA", "fecha": di, "vacuna": "", "valor": v, "id_archivo": str(id_archivo)})

    # Personas únicas (mes)
    for periodo, sset in persons_mes.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "PERSONAS_UNICAS_MES", "fecha": "", "vacuna": "", "valor": len(sset), "id_archivo": str(id_archivo)})

    for (periodo, vacuna), sset in persons_mes_vac.items():
        reportes.append({"periodo": periodo, "tipo_reporte": "PERSONAS_UNICAS_POR_VACUNA_MES", "fecha": "", "vacuna": vacuna, "valor": len(sset), "id_archivo": str(id_archivo)})

    # Personas únicas (día)
    for di, sset in persons_dia.items():
        reportes.append({"periodo": di[:7], "tipo_reporte": "PERSONAS_UNICAS_DIA", "fecha": di, "vacuna": "", "valor": len(sset), "id_archivo": str(id_archivo)})

    for (di, vacuna), sset in persons_dia_vac.items():
        reportes.append({"periodo": di[:7], "tipo_reporte": "PERSONAS_UNICAS_POR_VACUNA_DIA", "fecha": di, "vacuna": vacuna, "valor": len(sset), "id_archivo": str(id_archivo)})

    return registros, alertas, reportes, {"validas": validas, "invalidas": invalidas, "conflictos": conflictos}
