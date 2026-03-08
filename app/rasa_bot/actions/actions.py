import os
import re
import json
import logging
import requests
import unicodedata
from datetime import date, timedelta
from requests.exceptions import Timeout, RequestException
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


FLASK_BOT_BASE_URL = os.getenv("FLASK_BOT_BASE_URL", "").rstrip("/")
BOT_KEY = os.getenv("BOT_KEY", "")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("FLASK_BOT_BASE_URL:", FLASK_BOT_BASE_URL, flush=True)
print("BOT_KEY cargada en actions:", bool(BOT_KEY), flush=True)

# ------------------------- timeouts y sesión HTTP -------------------------

# connect timeout , read timeout
# TIMEOUTS OPTIMIZADOS PARA RENDER

HTTP_TIMEOUT_FAST = (3.05, 12)      # consultas rápidas
HTTP_TIMEOUT_DEFAULT = (3.05, 30)   # consultas normales
HTTP_TIMEOUT_MULTI = (3.05, 25)     # varias consultas encadenadas
HTTP_TIMEOUT_SLOW = (3.05, 45)      # reportes pesados / cold start


_session = requests.Session()


# ------------------------- helpers base -------------------------

def _headers():
    h = {}
    if BOT_KEY:
        h["X-BOT-KEY"] = BOT_KEY
    return h


def _strip_accents(s: str) -> str:
    s = s or ""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _canon(s: str) -> str:
    s = _strip_accents(s or "")
    s = s.upper().strip()
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def wants_context_reuse(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False

    if len(t.split()) <= 3:
        return True

    markers = [
        "mismo", "misma", "del mismo", "del mismo paciente",
        "ahora", "y en", "y para", "y el", "y la", "y los", "y las",
        "tambien", "también", "igual", "ese", "esa", "eso", "a ese", "a esa",
        "del paciente", "del mismo", "y ", "y de",
        "ahi", "ahí",
        "mismo periodo",
        "ese periodo",
        "ese mes",
    ]
    return any(m in t for m in markers)


def latest_entities(tracker: Tracker, entity_name: str):
    ents = tracker.latest_message.get("entities") or []
    out = []
    for e in ents:
        if e.get("entity") == entity_name:
            v = e.get("value")
            if v is not None and str(v).strip() != "":
                out.append(v)
    return out


def latest_entity(tracker: Tracker, entity_name: str):
    vs = latest_entities(tracker, entity_name)
    return vs[0] if vs else None


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}


def _api_get(path: str, params=None, timeout=HTTP_TIMEOUT_DEFAULT):
    """
    Wrapper HTTP para cortar antes, capturar errores y devolver un resultado uniforme.
    """
    url = f"{FLASK_BOT_BASE_URL}/{path.lstrip('/')}"
    try:
        r = _session.get(url, params=params or {}, headers=_headers(), timeout=timeout)
        data = _safe_json(r) if "application/json" in (r.headers.get("content-type") or "") else {}
        return {
            "ok": 200 <= r.status_code < 300,
            "status": r.status_code,
            "json": data,
            "text": r.text[:500] if hasattr(r, "text") else "",
            "error": None,
        }
    except Timeout as e:
        logger.warning("Timeout GET %s params=%s error=%s", url, params, e)
        return {
            "ok": False,
            "status": None,
            "json": {},
            "text": "",
            "error": "timeout",
        }
    except RequestException as e:
        logger.warning("HTTP error GET %s params=%s error=%s", url, params, e)
        return {
            "ok": False,
            "status": None,
            "json": {},
            "text": "",
            "error": "request",
        }
    except Exception as e:
        logger.exception("Unexpected error GET %s params=%s error=%s", url, params, e)
        return {
            "ok": False,
            "status": None,
            "json": {},
            "text": "",
            "error": "unexpected",
        }


def _is_timeout(res) -> bool:
    return res.get("error") == "timeout"


MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "setiembre": "09",
    "octubre": "10", "noviembre": "11", "diciembre": "12"
}


def norm_month(raw: str):
    if not raw:
        return None
    s = raw.strip().lower()
    if re.match(r"^\d{4}-\d{2}$", s):
        return s
    m = re.search(
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+(?:del\s+)?(\d{4})",
        s
    )
    if m:
        return f"{m.group(2)}-{MESES[m.group(1)]}"
    return None


def norm_date(raw: str):
    if not raw:
        return None
    s = raw.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}"
    return None


# ------------------------- paciente campos -------------------------

CAMPOS_PACIENTE_MAP = {
    "NOMBRE": "nombres",
    "NOMBRES": "nombres",
    "APELLIDO": "apellidos",
    "APELLIDOS": "apellidos",
    "PARROQUIA": "parroquia",
    "CANTON": "canton",
    "CANTÓN": "canton",
    "CAPTACION": "captacion",
    "CAPTACIÓN": "captacion",
    "ESTABLECIMIENTO": "establecimiento",
    "EDAD": "edad",
    "PROXIMA DOSIS": "proxima_dosis",
    "PRÓXIMA DOSIS": "proxima_dosis",
    "DOSIS PENDIENTE": "proxima_dosis",
    "SEXO": "sexo",
    "ULTIMA VACUNACION": "ultima_vacunacion",
    "ÚLTIMA VACUNACION": "ultima_vacunacion",
    "ULTIMA VACUNACIÓN": "ultima_vacunacion",
    "ÚLTIMA VACUNACIÓN": "ultima_vacunacion",
}


def norm_campo_paciente(raw: str):
    if not raw:
        return None
    key = _canon(raw)
    key = re.sub(r"[_\-]+", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    if key in CAMPOS_PACIENTE_MAP:
        return CAMPOS_PACIENTE_MAP[key]
    for k, v in CAMPOS_PACIENTE_MAP.items():
        if k in key:
            return v
    return None


def extract_campos(tracker: Tracker):
    ents = latest_entities(tracker, "campo_paciente")
    out = []
    seen = set()
    for c in ents:
        cc = norm_campo_paciente(c)
        if cc and cc not in seen:
            seen.add(cc)
            out.append(cc)
    return out


# ------------------------- biologico campos -------------------------

def norm_campo_biologico(raw: str):
    if not raw:
        return None
    s = _canon(raw)
    campo_map = {
        "VIA": "via",
        "ANGULO": "angulo",
        "DESCRIPCION": "descripcion",
        "DOSIS POR FRASCO": "dosis_por_frasco",
        "DOSIS ADMINISTRADA": "dosis_administrada",
        "LOTE": "lote",
        "CADUCIDAD": "fecha_caducidad",
        "FECHA DE CADUCIDAD": "fecha_caducidad",
        "CAJAS": "cajas",
        "FRASCOS": "frascos",
        "FRASCOS POR CAJA": "frascos_por_caja",
    }
    if s in campo_map:
        return campo_map[s]
    for k, v in campo_map.items():
        if k in s:
            return v
    return None


# ------------------------- acciones -------------------------

class ActionReporteMensual(Action):
    def name(self) -> str:
        return "action_reporte_mensual"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        text = tracker.latest_message.get("text") or ""

        periodo_ent = latest_entity(tracker, "periodo")
        month = norm_month(periodo_ent) if periodo_ent else None
        if not month:
            month = norm_month(text)

        if not month:
            dispatcher.utter_message("Indícame el mes como YYYY-MM o diciembre 2025.")
            return []

        res = _api_get("/api/bot/reporte-mensual", {"month": month}, timeout=HTTP_TIMEOUT_SLOW)

        if _is_timeout(res):
            dispatcher.utter_message("La consulta del reporte tardó demasiado. Intenta nuevamente en unos segundos.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el reporte mensual en este momento.")
            return []

        data = (res["json"].get("data") or {})
        total = data.get("total_mensual", 0)
        top = data.get("dosis_por_vacuna") or []

        lines = [f"**Resumen mensual — {month}**", "", f"• Total de dosis registradas: **{total}**"]
        if isinstance(top, list) and top:
            lines.append("")
            lines.append("**Vacunas con mayor aplicación**")
            for i, it in enumerate(top[:3], start=1):
                lines.append(f"{i}. {it.get('vacuna','N/D')}: **{it.get('dosis_total', 0)}**")

        dispatcher.utter_message("\n".join(lines))
        return [SlotSet("last_periodo", month)]


class ActionPacienteHistorial(Action):
    def name(self) -> str:
        return "action_paciente_historial"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        text = tracker.latest_message.get("text") or ""
        ced_ent = latest_entity(tracker, "cedula")
        cedula = (ced_ent or tracker.get_slot("cedula") or "").strip()
        if not cedula:
            m = re.search(r"\b\d{10}\b", text)
            cedula = m.group(0) if m else ""

        if not cedula:
            dispatcher.utter_message("Indícame la **cédula**. Ej: “historial 0967894387”.")
            return []

        res = _api_get("/api/bot/historial-paciente", {"cedula": cedula}, timeout=HTTP_TIMEOUT_SLOW)

        if _is_timeout(res):
            dispatcher.utter_message("El historial tardó demasiado en responder. Intenta nuevamente.")
            return []

        if res["status"] == 404:
            dispatcher.utter_message("No se encontraron registros para esa cédula.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el historial en este momento.")
            return []

        j = res["json"] or {}
        p = j.get("paciente") or {"cedula": cedula, "nombres": "N/D", "edad": "N/D", "grupo_riesgo": "N/D"}
        rows = j.get("rows") or []

        lines = [
            "**Paciente encontrado**",
            f"• Cédula: **{p.get('cedula', 'N/D')}**",
            f"• Nombres: **{p.get('nombres', 'N/D')}**",
            f"• Sexo: **{p.get('sexo', 'N/D')}**",
            f"• Edad: **{p.get('edad', 'N/D')}**",
            f"• Grupo de riesgo: **{p.get('grupo_riesgo', 'N/D')}**",
            f"• Parroquia: **{p.get('parroquia', 'N/D')}**",
            f"• Establecimiento: **{p.get('establecimiento', 'N/D')}**",
            "",
            "**Historial (más reciente)**"
        ]

        last = list(reversed(rows))[:10]
        for i, row in enumerate(last, start=1):
            fecha = row.get("fecha_vacunacion") or "N/D"
            vac = row.get("vacuna_canon") or "N/D"
            raw = row.get("vacuna_raw")
            raw_txt = f" (raw: {raw})" if raw and raw != vac else ""
            lines.append(
                f"{i}. {fecha} — {vac}{raw_txt} | Dosis: {row.get('dosis', 'N/D')} | "
                f"Esquema: {row.get('esquema', 'N/D')} | Estado: {row.get('estado_registro', 'N/D')}"
            )

        dispatcher.utter_message("\n".join(lines))
        return [SlotSet("last_cedula", cedula), SlotSet("cedula", cedula)]


class ActionPacienteDato(Action):
    def name(self) -> str:
        return "action_paciente_dato"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        text = tracker.latest_message.get("text") or ""

        ced_ent = latest_entity(tracker, "cedula")
        cedula = (ced_ent or tracker.get_slot("cedula") or "").strip()

        if not cedula and wants_context_reuse(text):
            cedula = (tracker.get_slot("last_cedula") or "").strip()

        if not cedula:
            dispatcher.utter_message("Indícame la **cédula**. Ej: “parroquia del paciente 0967894387”.")
            return []

        campo_ent = latest_entity(tracker, "campo_paciente")
        campo = norm_campo_paciente(campo_ent) if campo_ent else None
        if not campo:
            campo = norm_campo_paciente(text)

        if not campo:
            dispatcher.utter_message(
                "¿Qué dato necesitas del paciente?\n"
                "Puedo: **parroquia, cantón, edad, captación, establecimiento, próxima dosis**."
            )
            return []

        res = _api_get("/api/bot/paciente-dato", {"cedula": cedula, "dato": campo}, timeout=HTTP_TIMEOUT_DEFAULT)
        j = res["json"]

        if _is_timeout(res):
            dispatcher.utter_message("Ese dato tardó demasiado en responder. Intenta nuevamente.")
            return []

        if res["status"] == 404:
            dispatcher.utter_message("No se encontraron registros para esa cédula.")
            return []

        if not res["ok"]:
            if j.get("error") == "Dato no permitido":
                dispatcher.utter_message("Dato no permitido. Prueba con: parroquia, cantón, edad, captación, establecimiento, próxima dosis.")
                return []
            dispatcher.utter_message("No pude obtener ese dato en este momento.")
            return []

        valor = j.get("valor")
        fv = j.get("fecha_vacunacion", "N/D")

        labels = {
            "parroquia": "Parroquia",
            "canton": "Cantón",
            "edad": "Edad",
            "captacion": "Captación",
            "establecimiento": "Establecimiento",
            "proxima_dosis": "Próxima dosis",
            "nombres": "Nombres",
            "apellidos": "Apellidos",
            "sexo": "Sexo",
            "ultima_vacunacion": "Última vacunación",
        }
        campo_label = labels.get(campo, campo)

        if valor is None or str(valor).strip() == "":
            dispatcher.utter_message(f"No se encontró **{campo_label}** para el paciente. (Última vacunación: {fv})")
            return [SlotSet("last_cedula", cedula), SlotSet("cedula", cedula)]

        dispatcher.utter_message(
            f"**Dato del paciente**\n• Cédula: **{cedula}**\n• {campo_label}: **{valor}**\n• Última vacunación: **{fv}**"
        )
        return [SlotSet("last_cedula", cedula), SlotSet("cedula", cedula)]


class ActionContarVacunaDia(Action):
    def name(self) -> str:
        return "action_contar_vacuna_dia"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        text = tracker.latest_message.get("text") or ""

        vac_ent = latest_entity(tracker, "vacuna")
        vacuna = (vac_ent or "").strip()
        if not vacuna:
            dispatcher.utter_message("Ejemplo: “cuántos se vacunaron con Influenza el 2025-12-10”.")
            return []

        fecha_ent = latest_entity(tracker, "fecha")
        fecha = norm_date(fecha_ent) if fecha_ent else None
        if not fecha:
            fecha = norm_date(text)

        if not fecha:
            dispatcher.utter_message("Ejemplo: “cuántos se vacunaron con Influenza el 2025-12-10”.")
            return []

        res = _api_get("/api/bot/contar-vacuna-dia", {"vacuna": vacuna, "fecha": fecha}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("La consulta tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude contar en este momento.")
            return []

        total = (res["json"] or {}).get("total", 0)

        dispatcher.utter_message(
            f"**Conteo de vacunación — {fecha}**\n• Vacuna: **{vacuna}**\n• Total de registros: **{total}**"
        )
        return [SlotSet("last_vacuna", vacuna)]


class ActionContarVacunaMes(Action):
    def name(self) -> str:
        return "action_contar_vacuna_mes"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        text = tracker.latest_message.get("text") or ""

        per_ent = latest_entity(tracker, "periodo")
        month = norm_month(per_ent) if per_ent else None
        if not month:
            month = norm_month(text)
        if not month and wants_context_reuse(text):
            month = norm_month(tracker.get_slot("last_periodo") or "")

        vac_ent = latest_entity(tracker, "vacuna")
        vacuna_in = (vac_ent or "").strip()
        if not vacuna_in:
            m = re.search(r"(?:dosis\s+de|vacunados\s+con|vacuna\s+)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s]+?)\s+(?:en|del)\s+", text, flags=re.IGNORECASE)
            vacuna_in = (m.group(1).strip() if m else "")

        if not vacuna_in and wants_context_reuse(text):
            vacuna_in = (tracker.get_slot("last_vacuna") or "").strip()

        if not month or not vacuna_in:
            dispatcher.utter_message(
                "Para contar por mes necesito **vacuna** y **periodo**.\n"
                "Ejemplo: “cuántas dosis de HB adulto en enero 2026”."
            )
            return []

        alias = {
            "HB": "HEPATITIS B",
            "HEPATITISB": "HEPATITIS B",
            "HB ADULTO": "HB ADULTO",
            "HEPATITIS B ADULTO": "HB ADULTO",
            "HEPATITIS B": "HEPATITIS B",
        }
        vcanon = _canon(vacuna_in)
        if vcanon in alias:
            vacuna_in = alias[vcanon]

        res = _api_get("/api/bot/reporte-mensual", {"month": month}, timeout=HTTP_TIMEOUT_SLOW)

        if _is_timeout(res):
            dispatcher.utter_message("El reporte mensual tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el reporte mensual en este momento.")
            return []

        data = (res["json"].get("data") or {})
        total_mes = int(data.get("total_mensual", 0) or 0)
        lista = data.get("dosis_por_vacuna") or []

        if not isinstance(lista, list) or not lista:
            dispatcher.utter_message(f"No hay datos de dosis por vacuna para **{month}**.")
            return []

        txt = _canon(text)
        vin = _canon(vacuna_in)
        if "INFLUENZA" in vin:
            if "PEDIATR" in vin or "PEDIATR" in txt or "NIÑ" in txt or "INFANT" in txt:
                vacuna_in = "INFLUENZA PEDIATRICA"
            elif "ADUL" in vin or "ADUL" in txt:
                vacuna_in = "INFLUENZA ADULTO"

        target = _canon(vacuna_in)

        def matches(vrow: str) -> bool:
            v = _canon(vrow)

            if "INFLUENZA" in target:
                if "PEDIATR" in target and "ADUL" in v:
                    return False
                if "ADUL" in target and "PEDIATR" in v:
                    return False

            if v == target:
                return True

            if len(target) >= 6 and (target in v or v in target):
                return True

            if target in ("HB", "HEPATITIS B") and ("HB" in v or "HEPATITIS B" in v):
                return True

            return False

        found = None
        for it in lista:
            vrow = it.get("vacuna") or ""
            if matches(vrow):
                found = it
                break

        if not found:
            sugerencias = [(it.get("vacuna") or "N/D") for it in lista[:8]]
            dispatcher.utter_message(
                "No encontré esa vacuna exactamente en el reporte mensual.\n"
                "Prueba con uno de estos nombres:\n• " + "\n• ".join(sugerencias)
            )
            return []

        dosis = int(found.get("dosis_total", 0) or 0)

        rank = None
        for i, it in enumerate(lista, start=1):
            if (it.get("vacuna") or "") == (found.get("vacuna") or ""):
                rank = i
                break

        pct = (dosis / total_mes * 100.0) if total_mes > 0 else 0.0
        vacuna_out = found.get("vacuna") or vacuna_in

        lines = [
            f"**Conteo mensual — {month}**",
            f"• Vacuna: **{vacuna_out}**",
            f"• Dosis aplicadas en el mes: **{dosis}**",
        ]
        if rank is not None:
            lines.append(f"• Ranking del mes: **#{rank}**")
        lines.append(f"• Porcentaje del total mensual: **{pct:.1f}%**")

        dispatcher.utter_message("\n".join(lines))
        return [SlotSet("last_vacuna", vacuna_out), SlotSet("last_periodo", month)]


class ActionInfoGeneral(Action):
    def name(self) -> str:
        return "action_info_general"

    def run(self, dispatcher, tracker, domain):
        txt = (tracker.latest_message.get("text") or "").lower()

        if "captación" in txt or "captacion" in txt:
            dispatcher.utter_message("**Captación**: clasifica registros según oportunidad (temprana/tardía) según reglas del sistema.")
            return []
        if "esquema" in txt:
            dispatcher.utter_message("**Esquema**: etiqueta operativa de la dosis (p. ej., campaña/temprana/tardía) según lo registrado.")
            return []
        if "canon" in txt:
            dispatcher.utter_message("**Vacuna canon**: nombre normalizado para agrupar variantes de escritura.")
            return []
        if "raw" in txt:
            dispatcher.utter_message("**Vacuna raw**: nombre original antes de normalizar.")
            return []

        dispatcher.utter_message("Puedo explicarte: **captación, esquema, estado del registro, vacuna canon, vacuna raw**. ¿Cuál necesitas?")
        return []


class ActionTopVacunaPeriodo(Action):
    def name(self) -> str:
        return "action_top_vacuna_periodo"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""

        per_ent = latest_entity(tracker, "periodo")
        month = norm_month(per_ent) if per_ent else None
        if not month:
            month = norm_month(text)

        if not month and wants_context_reuse(text):
            month = norm_month(tracker.get_slot("last_periodo") or "")

        if not month:
            dispatcher.utter_message("Indícame el periodo. Ej: “octubre 2025” o “2025-10”.")
            return []

        res = _api_get("/api/bot/reporte-mensual", {"month": month}, timeout=HTTP_TIMEOUT_SLOW)

        if _is_timeout(res):
            dispatcher.utter_message("La consulta del top de vacunas tardó demasiado.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el top de vacunas en este momento.")
            return []

        data = (res["json"].get("data") or {})
        lista = data.get("dosis_por_vacuna") or []
        if not lista:
            dispatcher.utter_message(f"No hay datos de dosis por vacuna para **{month}**.")
            return []

        top1 = lista[0]
        dispatcher.utter_message(
            f"**Vacuna con más dosis — {month}**\n"
            f"• Vacuna: **{top1.get('vacuna', 'N/D')}**\n"
            f"• Dosis: **{int(top1.get('dosis_total', 0) or 0)}**"
        )
        return [SlotSet("last_periodo", month)]


class ActionPacienteInfoPersonal(Action):
    def name(self) -> str:
        return "action_paciente_info_personal"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""
        ced_ent = latest_entity(tracker, "cedula")
        cedula = (ced_ent or tracker.get_slot("cedula") or "").strip()
        if not cedula and wants_context_reuse(text):
            cedula = (tracker.get_slot("last_cedula") or "").strip()

        if not cedula:
            dispatcher.utter_message("Indícame la **cédula** del paciente.")
            return []

        res = _api_get("/api/bot/historial-paciente", {"cedula": cedula}, timeout=HTTP_TIMEOUT_SLOW)

        if _is_timeout(res):
            dispatcher.utter_message("La información del paciente tardó demasiado en responder.")
            return []

        if res["status"] == 404:
            dispatcher.utter_message("No se encontraron registros para esa cédula.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener la información del paciente en este momento.")
            return []

        j = res["json"] or {}
        p = j.get("paciente") or {}
        dispatcher.utter_message(
            "**Información del paciente**\n"
            f"• Cédula: **{p.get('cedula', cedula)}**\n"
            f"• Nombres: **{p.get('nombres', 'N/D')}**\n"
            f"• Sexo: **{p.get('sexo', 'N/D')}**\n"
            f"• Edad: **{p.get('edad', 'N/D')}**\n"
            f"• Grupo de riesgo: **{p.get('grupo_riesgo', 'N/D')}**\n"
            f"• Parroquia: **{p.get('parroquia', 'N/D')}**\n"
            f"• Establecimiento: **{p.get('establecimiento', 'N/D')}**"
        )
        return [SlotSet("last_cedula", cedula), SlotSet("cedula", cedula)]


class ActionPacienteDatoMultiple(Action):
    def name(self) -> str:
        return "action_paciente_dato_multiple"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""
        ced_ent = latest_entity(tracker, "cedula")
        cedula = (ced_ent or tracker.get_slot("cedula") or "").strip()
        if not cedula and wants_context_reuse(text):
            cedula = (tracker.get_slot("last_cedula") or "").strip()

        campos = extract_campos(tracker)

        if not cedula:
            dispatcher.utter_message("Indícame la **cédula**. Ej: “parroquia y edad del paciente 0967…”.")
            return []
        if not campos:
            dispatcher.utter_message("¿Qué datos necesitas? Ej: “parroquia, edad y próxima dosis del paciente 0967…”.")
            return []

        labels = {
            "parroquia": "Parroquia",
            "canton": "Cantón",
            "edad": "Edad",
            "captacion": "Captación",
            "establecimiento": "Establecimiento",
            "proxima_dosis": "Próxima dosis",
        }

        resultados = []
        hubo_timeout = False

        for campo in campos:
            res = _api_get("/api/bot/paciente-dato", {"cedula": cedula, "dato": campo}, timeout=HTTP_TIMEOUT_MULTI)
            if _is_timeout(res):
                hubo_timeout = True
                resultados.append((labels.get(campo, campo), "N/D"))
                continue

            j = res["json"]
            valor = j.get("valor") if res["ok"] else None
            resultados.append((labels.get(campo, campo), valor if valor not in [None, ""] else "N/D"))

        lines = [f"**Datos del paciente — {cedula}**"]
        for k, v in resultados:
            lines.append(f"• {k}: **{v}**")

        if hubo_timeout:
            lines.append("")
            lines.append("_Algunos campos tardaron demasiado en responder._")

        dispatcher.utter_message("\n".join(lines))
        return [SlotSet("last_cedula", cedula), SlotSet("cedula", cedula)]


class ActionConteoCaptacionPeriodo(Action):
    def name(self) -> str:
        return "action_conteo_captacion_periodo"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""

        per_ent = latest_entity(tracker, "periodo")
        month = norm_month(per_ent) if per_ent else None
        if not month:
            month = norm_month(text)
        if not month and wants_context_reuse(text):
            month = norm_month(tracker.get_slot("last_periodo") or "")

        capt_ent = latest_entity(tracker, "captacion")
        capt_raw = (capt_ent or "").strip().lower().replace("tardía", "tardia")

        low = text.lower()
        if not capt_raw:
            if "camp" in low:
                capt_raw = "campania"
            elif "tempr" in low:
                capt_raw = "temprana"
            elif "tardi" in low:
                capt_raw = "tardia"

        if "camp" in capt_raw:
            capt = "campania"
        elif capt_raw in ("temprana", "tardia"):
            capt = capt_raw
        else:
            capt = ""

        if not month or not capt:
            dispatcher.utter_message(
                "Necesito **captación** (temprana/tardía) o **campaña**, y el **periodo**.\n"
                "Ejemplos:\n"
                "• captación temprana en septiembre 2025\n"
                "• campaña en septiembre 2025"
            )
            return []

        res = _api_get("/api/bot/conteo-captacion-periodo", {"month": month, "captacion": capt}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("El conteo tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el conteo en este momento.")
            return []

        total = int((res["json"] or {}).get("total", 0) or 0)

        if capt == "campania":
            dispatcher.utter_message(
                f"**Conteo por esquema — {month}**\n"
                f"• Esquema: **Campaña**\n"
                f"• Total de dosis: **{total}**"
            )
        else:
            cap_label = "tardía" if capt == "tardia" else "temprana"
            dispatcher.utter_message(
                f"**Conteo por captación — {month}**\n"
                f"• Captación: **{cap_label}**\n"
                f"• Total de dosis: **{total}**"
            )

        return [SlotSet("last_periodo", month)]


class ActionConteoTotalDia(Action):
    def name(self) -> str:
        return "action_conteo_total_dia"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""
        fecha_ent = latest_entity(tracker, "fecha")
        fecha = norm_date(fecha_ent) if fecha_ent else None
        if not fecha:
            fecha = norm_date(text)

        if not fecha:
            dispatcher.utter_message("Indícame la fecha. Ej: “17/09/2025”.")
            return []

        res = _api_get("/api/bot/conteo-total-dia", {"fecha": fecha}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("El total del día tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el total del día en este momento.")
            return []

        total = (res["json"] or {}).get("total", 0)
        dispatcher.utter_message(f"**Vacunados del día — {fecha}**\n• Total de registros: **{total}**")
        return []


class ActionTopMesAnio(Action):
    def name(self) -> str:
        return "action_top_mes_anio"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""
        anio_ent = latest_entity(tracker, "anio")
        anio = (anio_ent or "").strip()
        if not anio:
            m = re.search(r"\b(19|20)\d{2}\b", text)
            anio = m.group(0) if m else ""

        if not anio or not anio.isdigit():
            dispatcher.utter_message("Indícame el año. Ej: “¿qué mes tuvo más dosis en 2025?”")
            return []

        res = _api_get("/api/bot/top-mes-anio", {"anio": anio}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("La consulta del año tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el mes con más dosis en este momento.")
            return []

        j = res["json"] or {}
        month = j.get("month")
        total = j.get("total", 0)

        if not month:
            dispatcher.utter_message(f"No hay datos para el año **{anio}**.")
            return []

        dispatcher.utter_message(
            f"**Mes con más dosis — {anio}**\n"
            f"• Mes: **{month}**\n"
            f"• Total de dosis: **{total}**"
        )
        return []


class ActionDatosPersonales(Action):
    def name(self) -> str:
        return "action_datos_personales"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(
            "Puedo consultar datos del sistema para inmunización. "
            "Si deseas, dime si necesitas: **campos almacenados** o **uso/protección de datos**."
        )
        return []


class ActionDefaultFallback(Action):
    def name(self) -> str:
        return "action_default_fallback"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(
            "No estoy seguro de haber entendido. "
            "Prueba con: “reporte 2025-12”, “historial 0967894387”, "
            "“cuántas dosis de SRP en septiembre 2025”."
        )
        return []


class ActionAyudaContextual(Action):
    def name(self) -> str:
        return "action_ayuda_contextual"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(
            "Dime qué necesitas:\n"
            "• Reporte mensual: “reporte 2025-12”\n"
            "• Conteo por vacuna/mes: “HB adulto en enero 2026”\n"
            "• Total del día: “cuántos vacunados el 17/09/2025”\n"
            "• Historial: “historial 0967…”"
        )
        return []


class ActionInsumoCategorias(Action):
    def name(self) -> str:
        return "action_insumo_categorias"

    def run(self, dispatcher, tracker, domain):
        res = _api_get("/api/bot/insumo/categorias", timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("Las categorías tardaron demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener las categorías en este momento.")
            return []

        rows = (res["json"].get("data") or [])
        cats = [x.get("categoria") for x in rows if x.get("categoria")]
        if not cats:
            dispatcher.utter_message("No hay categorías disponibles.")
            return []

        dispatcher.utter_message("**Categorías de insumos**\n• " + "\n• ".join(cats))
        return []


def detect_insumo_categoria_from_text(text: str):
    t = _canon(text)
    for c in ("ALCOHOL", "ALGODON", "GUANTES", "JERINGAS"):
        if c in t:
            return c
    return None


class ActionInsumoStockTipo(Action):
    def name(self) -> str:
        return "action_insumo_stock_tipo"

    def run(self, dispatcher, tracker, domain):
        text = (tracker.latest_message.get("text") or "")
        text_l = text.lower()

        cat_ent = latest_entity(tracker, "insumo_categoria")
        tipo_ent = latest_entity(tracker, "insumo_tipo")

        cat = _canon(cat_ent) if cat_ent else ""
        tipo = (tipo_ent or "").strip()

        if not cat:
            cat = detect_insumo_categoria_from_text(text) or ""

        last_cat = _canon(tracker.get_slot("last_insumo_categoria") or "")
        last_tipo = (tracker.get_slot("last_insumo_tipo") or "").strip()

        if not cat and wants_context_reuse(text):
            cat = last_cat

        if not tipo:
            m_ml = re.search(r"\b(\d{2,4})\s*ml\b", text_l)
            if m_ml:
                tipo = f"{m_ml.group(1)}ml"

        if not tipo and wants_context_reuse(text):
            if cat and last_cat and cat == last_cat:
                tipo = last_tipo

        res = _api_get("/api/bot/insumo/tipos", {"categoria": cat or "", "q": tipo or ""}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("La consulta de stock tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el stock de insumos en este momento.")
            return []

        rows = (res["json"].get("data") or [])
        if not rows:
            if cat:
                res2 = _api_get("/api/bot/insumo/tipos", {"categoria": cat, "q": ""}, timeout=HTTP_TIMEOUT_MULTI)
                rows2 = (res2["json"].get("data") or []) if res2["ok"] else []
                if rows2:
                    tops = rows2[:6]
                    lista = "\n".join([f"• {x.get('nombre_tipo', 'N/D')}" for x in tops])
                    dispatcher.utter_message(
                        f"Tengo varios tipos para **{cat}**. Indica cuál necesitas:\n{lista}"
                    )
                    return [SlotSet("last_insumo_categoria", cat), SlotSet("last_insumo_tipo", None)]
            dispatcher.utter_message("No encontré resultados con esos datos. Prueba indicando categoría y/o el tipo exacto.")
            return []

        if not tipo and cat and last_cat and cat != last_cat:
            tops = rows[:6]
            lista = "\n".join([f"• {x.get('nombre_tipo', 'N/D')}" for x in tops])
            dispatcher.utter_message(f"Para **{cat}** necesito el tipo. Opciones:\n{lista}")
            return [SlotSet("last_insumo_categoria", cat), SlotSet("last_insumo_tipo", None)]

        top = rows[0]
        if tipo:
            tipo_norm = tipo.strip().lower()
            exact = next(
                (x for x in rows if str(x.get("nombre_tipo", "")).strip().lower() == tipo_norm),
                None
            )
            if exact:
                top = exact

        dispatcher.utter_message(
            f"**Stock de insumo**\n"
            f"• Categoría: **{top.get('categoria', 'N/D')}**\n"
            f"• Tipo: **{top.get('nombre_tipo', 'N/D')}**\n"
            f"• Packs: **{top.get('total_packs', 0)}**\n"
            f"• Unidades: **{top.get('total_unidades', 0)}**"
        )

        return [
            SlotSet("last_insumo_categoria", top.get("categoria")),
            SlotSet("last_insumo_tipo", top.get("nombre_tipo")),
        ]


class ActionInsumoLotesTipo(Action):
    def name(self) -> str:
        return "action_insumo_lotes_tipo"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""

        cat_ent = latest_entity(tracker, "insumo_categoria")
        tipo_ent = latest_entity(tracker, "insumo_tipo")

        cat = _canon(cat_ent) if cat_ent else ""
        tipo = (tipo_ent or "").strip()

        if not cat:
            cat = detect_insumo_categoria_from_text(text) or ""
        if not cat and wants_context_reuse(text):
            cat = _canon(tracker.get_slot("last_insumo_categoria") or "")
        if not tipo and wants_context_reuse(text):
            tipo = (tracker.get_slot("last_insumo_tipo") or "").strip()

        if not tipo and not cat:
            dispatcher.utter_message("Indícame el tipo o la categoría. Ej: “lotes de 23G x 1\" 0.5ml”.")
            return []

        res = _api_get("/api/bot/insumo/lotes", {"categoria": cat or "", "tipo": tipo or ""}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("La consulta de lotes tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener los lotes en este momento.")
            return []

        rows = res["json"].get("data") or []
        if not rows:
            dispatcher.utter_message("No se encontraron lotes para ese insumo.")
            return []

        lines = ["**Lotes del insumo**"]
        for it in rows[:10]:
            lines.append(
                f"• Lote: **{it.get('lote', 'N/D')}** | Packs: {it.get('packs', 'N/D')} | Unidades: {it.get('unidades', 'N/D')} | "
                f"Fab: {it.get('fecha_fabricacion', 'N/D')} | Cad: {it.get('fecha_caducidad', 'N/D')} | Estado: {it.get('estado', 'N/D')}"
            )
        dispatcher.utter_message("\n".join(lines))
        return []


class ActionInsumoPorCaducar(Action):
    def name(self) -> str:
        return "action_insumo_por_caducar"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""

        exp_ent = latest_entity(tracker, "exp_days")
        exp = exp_ent if exp_ent is not None else tracker.get_slot("exp_days")
        cat_ent = latest_entity(tracker, "insumo_categoria")
        cat = _canon(cat_ent) if cat_ent else detect_insumo_categoria_from_text(text) or ""

        if not cat and wants_context_reuse(text):
            cat = _canon(tracker.get_slot("last_insumo_categoria") or "")

        if not exp:
            dispatcher.utter_message(response="utter_insumo_pedir_categoria")
            dispatcher.utter_message("Indícame en cuántos días. Ej: “insumos por caducar en 30 días”.")
            return []

        res = _api_get(
            "/api/bot/insumo/tipos",
            {"categoria": cat or "", "exp_days": int(float(exp)), "excluir_caducados": "false"},
            timeout=HTTP_TIMEOUT_DEFAULT
        )

        if _is_timeout(res):
            dispatcher.utter_message("La consulta de caducidad tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude consultar caducidad en este momento.")
            return []

        rows = res["json"].get("data") or []
        if not rows:
            dispatcher.utter_message("No encontré insumos por caducar en ese rango.")
            return []

        lines = [f"**Insumos por caducar en {int(float(exp))} días**"]
        for it in rows[:10]:
            lines.append(f"• {it.get('nombre_tipo', 'N/D')} | Packs: {it.get('total_packs', 0)} | Unidades: {it.get('total_unidades', 0)}")
        dispatcher.utter_message("\n".join(lines))
        return [SlotSet("last_insumo_categoria", cat or None)]


class ActionInsumoBiologicosAsociados(Action):
    def name(self) -> str:
        return "action_insumo_biologicos_asociados"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""
        tipo_ent = latest_entity(tracker, "insumo_tipo")
        tipo = (tipo_ent or "").strip()

        if not tipo and wants_context_reuse(text):
            tipo = (tracker.get_slot("last_insumo_tipo") or "").strip()

        if not tipo:
            dispatcher.utter_message("Indícame el tipo de insumo. Ej: “biológicos asociados a 23G x 1\" 0.5ml”.")
            return []

        res = _api_get("/api/bot/insumo/biologicos-asociados", {"tipo": tipo}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("La consulta de biológicos asociados tardó demasiado.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener los biológicos asociados en este momento.")
            return []

        rows = res["json"].get("data") or []
        if not rows:
            dispatcher.utter_message("No encontré biológicos asociados a ese tipo.")
            return []

        lines = [f"**Biológicos asociados — {tipo}**"]
        for b in rows[:10]:
            lines.append(
                f"• **{b.get('nombre_biologico', 'N/D')}** | Vía: {b.get('via', 'N/D')} | Ángulo: {b.get('angulo', 'N/D')} | "
                f"Dosis/frasco: {b.get('dosis_por_frasco', 'N/D')} | Dosis admin.: {b.get('dosis_administrada', 'N/D')}"
            )
        dispatcher.utter_message("\n".join(lines))
        return []


class ActionBiologicoDetalle(Action):
    def name(self) -> str:
        return "action_biologico_detalle"

    def run(self, dispatcher, tracker, domain):
        text = tracker.latest_message.get("text") or ""

        bio_ent = latest_entity(tracker, "biologico")
        bio = (bio_ent or "").strip()

        if not bio and wants_context_reuse(text):
            bio = (tracker.get_slot("last_biologico") or "").strip()

        campo_ent = latest_entity(tracker, "campo_biologico")
        campo = norm_campo_biologico(campo_ent) if campo_ent else None
        if not campo:
            campo = norm_campo_biologico(text)

        if not bio:
            dispatcher.utter_message("Indícame el nombre del biológico. Ej: “vía de HEXAVALENTE”.")
            return []

        res = _api_get("/api/bot/biologico/detalle", {"nombre": bio}, timeout=HTTP_TIMEOUT_DEFAULT)

        if _is_timeout(res):
            dispatcher.utter_message("El detalle del biológico tardó demasiado en responder.")
            return []

        if res["status"] == 404:
            dispatcher.utter_message("No encontré ese biológico en el sistema (o está inactivo).")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude obtener el detalle del biológico en este momento.")
            return []

        data = (res["json"].get("data") or {})
        nombre = data.get("nombre_biologico", bio)

        if not campo:
            lines = [
                f"**Biológico — {nombre}**",
                f"• Vía: **{data.get('via', 'N/D')}** | Ángulo: **{data.get('angulo', 'N/D')}**",
                f"• Dosis/frasco: **{data.get('dosis_por_frasco', 'N/D')}** | Dosis admin.: **{data.get('dosis_administrada', 'N/D')}**",
                f"• Lote: **{data.get('lote', 'N/D')}** | Caducidad: **{data.get('fecha_caducidad', 'N/D')}**",
                f"• Cajas: **{data.get('cajas', 'N/D')}** | Frascos: **{data.get('frascos', 'N/D')}** | Frascos/caja: **{data.get('frascos_por_caja', 'N/D')}**",
                f"• Descripción: {data.get('descripcion', 'N/D')}",
            ]
            dispatcher.utter_message("\n".join(lines))
            return [SlotSet("last_biologico", nombre)]

        val = data.get(campo, "N/D")
        dispatcher.utter_message(f"**Biológico — {nombre}**\n• {campo}: **{val}**")
        return [SlotSet("last_biologico", nombre)]


class ActionPacientesProximaDosisHoy(Action):
    def name(self) -> str:
        return "action_pacientes_proxima_dosis_hoy"

    def run(self, dispatcher, tracker, domain):
        sid = (getattr(tracker, "sender_id", None) or "0")
        v = (sum(ord(c) for c in str(sid)) % 3) + 1

        if v == 1:
            ack = "Listo."
            tail = "¿Quieres que lo filtre por biológico o que muestre más resultados?"
        elif v == 2:
            ack = "Hecho."
            tail = "¿Deseas ver más registros o filtrar por biológico?"
        else:
            ack = "De acuerdo."
            tail = "¿Te muestro más pacientes o prefieres filtrar por biológico?"

        res = _api_get("/api/bot/pacientes/proxima-dosis-hoy", {"limit": 80}, timeout=HTTP_TIMEOUT_SLOW)

        if _is_timeout(res):
            dispatcher.utter_message("La agenda de próximas dosis tardó demasiado en responder.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude consultar la agenda de próximas dosis en este momento.")
            return []

        rows = (res["json"].get("data") or [])
        if not rows:
            dispatcher.utter_message(f"{ack} Hoy no hay pacientes registrados con **próxima dosis** programada.")
            return []

        n = len(rows)
        lines = [ack, f"Para hoy encontré **{n}** paciente(s) con **próxima dosis**:", ""]

        for i, it in enumerate(rows[:25], start=1):
            ced = it.get("numero_identificacion", "N/D")
            nom = it.get("nombres", "N/D")
            bio = it.get("vacuna", "N/D")
            dosis = it.get("dosis", "N/D")
            fv = it.get("fecha_ultima_vacunacion", "N/D")

            lines.append(
                f"{i}. **{nom}** — {ced}\n"
                f"   • Biológico programado: **{bio}** | Dosis: **{dosis}** | Última: {fv}"
            )

        if n > 25:
            lines.append("")
            lines.append(tail)

        dispatcher.utter_message("\n".join(lines))
        return []


class ActionTryVacunacionQuery(Action):
    def name(self) -> str:
        return "action_try_vacunacion_query"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        text = (tracker.latest_message.get("text") or "").strip()
        low = text.lower()

        periodo = norm_month(latest_entity(tracker, "periodo") or "") or norm_month(text)
        fecha = norm_date(latest_entity(tracker, "fecha") or "") or norm_date(text)

        if not fecha:
            if "hoy" in low:
                fecha = date.today().isoformat()
            elif "ayer" in low:
                fecha = (date.today() - timedelta(days=1)).isoformat()

        vacuna = (latest_entity(tracker, "vacuna") or "").strip()
        anio = None
        anio_ent = latest_entity(tracker, "anio")
        if anio_ent and str(anio_ent).isdigit():
            anio = int(anio_ent)
        else:
            m = re.search(r"\b(19|20)\d{2}\b", text)
            anio = int(m.group(0)) if m else None

        if wants_context_reuse(text):
            if not periodo:
                periodo = norm_month(tracker.get_slot("last_periodo") or "")
            if not vacuna:
                vacuna = (tracker.get_slot("last_vacuna") or "").strip()

        capt_ent = latest_entity(tracker, "captacion")
        capt = (capt_ent or "").strip().lower().replace("tardía", "tardia")
        if not capt:
            if "tempr" in low:
                capt = "temprana"
            elif "tardi" in low:
                capt = "tardia"

        limit = 10
        mtop = re.search(r"\btop\s*(\d{1,2})\b", low)
        if mtop:
            limit = max(1, min(50, int(mtop.group(1))))

        qtype = None
        if (("próxima dosis" in low) or ("proxima dosis" in low) or ("pendientes" in low)) and ("hoy" in low):
            qtype = "proxima_dosis_hoy"
        if not qtype and (("mes con más" in low) or ("mes con mas" in low) or ("mes más" in low) or ("mes mas" in low)):
            if anio:
                qtype = "top_mes_anio"
        if not qtype and periodo and (("captación" in low) or ("captacion" in low) or ("capatcion" in low) or bool(capt)):
            qtype = "captacion_mes"
        if not qtype and periodo and (("top" in low) or ("ranking" in low) or ("más aplic" in low) or ("mas aplic" in low) or ("mayor" in low and ("vacuna" in low or "vacunas" in low))):
            qtype = "top_vacunas_mes"
        if not qtype and vacuna and fecha:
            qtype = "vacuna_dia"
        if not qtype and vacuna and periodo:
            qtype = "vacuna_mes"
        if not qtype and fecha:
            qtype = "total_dia"
        if not qtype and periodo:
            qtype = "total_mes"

        if not qtype:
            dispatcher.utter_message(
                "No estoy seguro de qué consulta deseas.\n"
                "Prueba con:\n"
                "• “vacunación del día 2025-09-17”\n"
                "• “vacunación en 2025-09”\n"
                "• “SRP en septiembre 2025”\n"
                "• “top vacunas septiembre 2025”\n"
                "• “mes con más dosis en 2025”"
            )
            return []

        if qtype in ("total_mes", "top_vacunas_mes", "captacion_mes") and not periodo:
            dispatcher.utter_message(response="utter_pedir_periodo")
            return []
        if qtype in ("total_dia", "vacuna_dia") and not fecha:
            dispatcher.utter_message("Me falta la **fecha**. Ej: “17/09/2025” o “2025-09-17”.")
            return []
        if qtype in ("vacuna_mes", "vacuna_dia") and not vacuna:
            dispatcher.utter_message("Me falta la **vacuna**. Ej: “SRP en septiembre 2025”.")
            return []
        if qtype == "top_mes_anio" and not anio:
            dispatcher.utter_message("Me falta el **año**. Ej: “mes con más dosis en 2025”.")
            return []

        params = {"qtype": qtype}
        if periodo:
            params["periodo"] = periodo
        if fecha:
            params["fecha"] = fecha
        if vacuna:
            params["vacuna"] = vacuna
        if capt and qtype == "captacion_mes":
            params["captacion"] = capt
        if anio:
            params["anio"] = str(anio)
        if qtype == "top_vacunas_mes":
            params["limit"] = str(limit)

        res = _api_get("/api/bot/vacunacion/query", params, timeout=HTTP_TIMEOUT_SLOW)

        if _is_timeout(res):
            dispatcher.utter_message("No pude consultar en este momento porque la respuesta tardó demasiado.")
            return []

        if not res["ok"]:
            dispatcher.utter_message("No pude consultar en este momento.")
            return []

        j = res["json"] or {}
        data = j.get("data")

        if qtype in ("total_dia", "total_mes", "vacuna_dia", "vacuna_mes"):
            total = int((data or {}).get("total", 0) or 0)

            if qtype == "total_dia":
                titulo = f"Vacunados del día — {fecha}"
                detalle = f"• Total de registros: **{total}**"
            elif qtype == "total_mes":
                titulo = f"Vacunación del mes — {periodo}"
                detalle = f"• Total de registros: **{total}**"
            elif qtype == "vacuna_dia":
                titulo = f"Vacunación por vacuna — {fecha}"
                detalle = f"• Vacuna: **{vacuna}**\n• Total de registros: **{total}**"
            else:
                titulo = f"Vacunación por vacuna — {periodo}"
                detalle = f"• Vacuna: **{vacuna}**\n• Total de registros: **{total}**"

            dispatcher.utter_message(f"**{titulo}**\n{detalle}")
            return [SlotSet("last_vacuna", vacuna or None), SlotSet("last_periodo", periodo or None)]

        if qtype == "top_vacunas_mes":
            items = (data or {}).get("items") or []
            if not items:
                dispatcher.utter_message(f"No hay datos de top vacunas para **{periodo}**.")
                return []

            lines = [f"**Top vacunas — {periodo}**"]
            for i, it in enumerate(items[:limit], start=1):
                lines.append(f"{i}. {it.get('vacuna', 'N/D')}: **{it.get('total', 0)}**")
            dispatcher.utter_message("\n".join(lines))
            return [SlotSet("last_periodo", periodo)]

        if qtype == "captacion_mes":
            items = (data or {}).get("items") or []
            if not items:
                dispatcher.utter_message(f"No hay datos de captación para **{periodo}**.")
                return []

            lines = [f"**Captación — {periodo}**"]
            for it in items[:10]:
                cap_name = it.get("captacion") or "N/D"
                lines.append(f"• {cap_name}: **{it.get('total', 0)}**")
            dispatcher.utter_message("\n".join(lines))
            return [SlotSet("last_periodo", periodo)]

        if qtype == "top_mes_anio":
            if not isinstance(data, dict) or not data.get("month"):
                dispatcher.utter_message(f"No hay datos para el año **{anio}**.")
                return []
            dispatcher.utter_message(
                f"**Mes con más dosis — {anio}**\n"
                f"• Mes: **{data.get('month')}**\n"
                f"• Total de dosis: **{data.get('total', 0)}**"
            )
            return []

        if qtype == "proxima_dosis_hoy":
            items = (data or {}).get("items") or []
            if not items:
                dispatcher.utter_message("Hoy no hay pacientes registrados con **próxima dosis** programada.")
                return []

            lines = [f"Encontré **{len(items)}** paciente(s) con **próxima dosis para hoy**:", ""]
            for i, it in enumerate(items[:25], start=1):
                nom = it.get("nombres", "N/D")
                ced = it.get("numero_identificacion", "N/D")
                bio = it.get("vacuna", "N/D")
                dosis = it.get("dosis", "N/D")
                fv = it.get("fecha_ultima_vacunacion", "N/D")
                lines.append(f"{i}. **{nom}** — {ced}\n   • Biológico: **{bio}** | Dosis: **{dosis}** | Última: {fv}")
            dispatcher.utter_message("\n".join(lines))
            return []

        dispatcher.utter_message("No pude interpretar el resultado de la consulta.")
        return []