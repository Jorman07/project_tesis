import time
import uuid
from typing import Any, Dict, List, Tuple

from app.services.carga_vacunacion_service import process_file_bytes

QR_TTL_SECONDS = 20 * 60  # 20 minutos
_QR_CACHE: Dict[int, Dict[str, Any]] = {}  # user_id -> payload


def _now() -> int:
    return int(time.time())


def cleanup_expired() -> None:
    now = _now()
    expired = []
    for uid, item in _QR_CACHE.items():
        if now - item.get("created_at", now) > QR_TTL_SECONDS:
            expired.append(uid)
    for uid in expired:
        _QR_CACHE.pop(uid, None)


def _extract_months_from_reportes(reportes: List[Dict[str, Any]]) -> List[str]:
    months = sorted({(r.get("periodo") or "").strip() for r in (reportes or [])})
    return [m for m in months if len(m) == 7 and m[4] == "-"]


def _group_alertas(alertas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    agg: Dict[Tuple[str, str], int] = {}
    for a in alertas or []:
        k = (a.get("tipo_alerta") or "SIN_TIPO", a.get("estado") or "PENDIENTE")
        agg[k] = agg.get(k, 0) + 1
    out = [{"tipo_alerta": k[0], "estado": k[1], "total": v} for k, v in agg.items()]
    out.sort(key=lambda x: x["total"], reverse=True)
    return out


def build_month_report_from_reportes(reportes: List[Dict[str, Any]], month: str) -> Dict[str, Any]:
    rep: Dict[str, Any] = {"tipo": "MENSUAL", "month": month}

    def _sum(tipo: str) -> int:
        s = 0
        for r in reportes:
            if r.get("tipo_reporte") == tipo and r.get("periodo") == month:
                s += int(r.get("valor") or 0)
        return s

    def _total_por_dia() -> List[Dict[str, Any]]:
        rows = []
        for r in reportes:
            if r.get("tipo_reporte") == "TOTAL_DIA" and r.get("periodo") == month:
                rows.append({"fecha": r.get("fecha"), "total": int(r.get("valor") or 0)})
        rows.sort(key=lambda x: x["fecha"] or "")
        return rows

    def _captacion_por_dia() -> List[Dict[str, Any]]:
        temp: Dict[str, int] = {}
        tard: Dict[str, int] = {}
        for r in reportes:
            if r.get("periodo") != month:
                continue
            f = r.get("fecha")
            if r.get("tipo_reporte") == "TOTAL_DIA_CAPTACION_TEMPRANA":
                temp[f] = temp.get(f, 0) + int(r.get("valor") or 0)
            if r.get("tipo_reporte") == "TOTAL_DIA_CAPTACION_TARDIA":
                tard[f] = tard.get(f, 0) + int(r.get("valor") or 0)
        fechas = sorted({*temp.keys(), *tard.keys()})
        return [{"fecha": f, "temprana": temp.get(f, 0), "tardia": tard.get(f, 0)} for f in fechas]

    def _dosis_por_vacuna_mes() -> List[Dict[str, Any]]:
        m: Dict[str, int] = {}
        for r in reportes:
            if r.get("tipo_reporte") == "TOTAL_DIA_POR_VACUNA" and r.get("periodo") == month:
                vac = (r.get("vacuna") or "").strip()
                if not vac:
                    continue
                m[vac] = m.get(vac, 0) + int(r.get("valor") or 0)
        arr = [{"vacuna": k, "dosis_total": v} for k, v in m.items()]
        arr.sort(key=lambda x: x["dosis_total"], reverse=True)
        return arr

    def _personas_por_vacuna_mes() -> List[Dict[str, Any]]:
        m: Dict[str, int] = {}
        has_month = False
        for r in reportes:
            if r.get("tipo_reporte") == "PERSONAS_UNICAS_POR_VACUNA_MES" and r.get("periodo") == month:
                has_month = True
                vac = (r.get("vacuna") or "").strip()
                if not vac:
                    continue
                m[vac] = m.get(vac, 0) + int(r.get("valor") or 0)

        if not has_month:
            for r in reportes:
                if r.get("tipo_reporte") == "PERSONAS_UNICAS_POR_VACUNA_DIA" and r.get("periodo") == month:
                    vac = (r.get("vacuna") or "").strip()
                    if not vac:
                        continue
                    m[vac] = m.get(vac, 0) + int(r.get("valor") or 0)

        arr = [{"vacuna": k, "personas_total": v} for k, v in m.items()]
        arr.sort(key=lambda x: x["personas_total"], reverse=True)
        return arr

    rep["total_mensual"] = _sum("TOTAL_MES")
    rep["personas_total"] = _sum("PERSONAS_UNICAS_MES")
    rep["captacion_temprana"] = _sum("TOTAL_DIA_CAPTACION_TEMPRANA")
    rep["captacion_tardia"] = _sum("TOTAL_DIA_CAPTACION_TARDIA")
    rep["total_por_dia"] = _total_por_dia()
    rep["captacion_por_dia"] = _captacion_por_dia()
    rep["dosis_por_vacuna"] = _dosis_por_vacuna_mes()
    rep["personas_por_vacuna"] = _personas_por_vacuna_mes()
    return rep


def process_in_memory(user_id: int, filename: str, content: bytes) -> Dict[str, Any]:
    """
    Procesa el archivo en memoria (sin BD), construye reportes por cada mes detectado.
    Retorna:
      - months: ['YYYY-MM',...]
      - reportes_por_mes: { 'YYYY-MM': {reporte mensual}, ... }
      - selected_month: primer mes
    """
    cleanup_expired()

    registros, alertas, reportes, metrics = process_file_bytes(-1, filename, content)

    months = _extract_months_from_reportes(reportes)
    if not months:
        return {"ok": False, "message": "No se detectaron meses en el archivo."}

    reportes_por_mes = {m: build_month_report_from_reportes(reportes, m) for m in months}
    selected_month = months[0]

    alertas_resumen = _group_alertas(alertas)

    session_key = str(uuid.uuid4())
    _QR_CACHE[user_id] = {
        "created_at": _now(),
        "session_key": session_key,
        "registros": registros,
        "metrics": metrics,
        "alertas_resumen": alertas_resumen,
        "months": months,
        "reportes_por_mes": reportes_por_mes,
        "meta": {"filename": filename}
    }

    return {
        "ok": True,
        "session_key": session_key,
        "metrics": metrics,
        "months": months,
        "selected_month": selected_month,
        "reportes_por_mes": reportes_por_mes,
        "alertas": alertas_resumen,
        "meta": {"filename": filename}
    }


def get_cached_registros_page(
    user_id: int,
    session_key: str,
    page: int = 1,
    page_size: int = 25,
    month: str = "",
    estado: str = "",
    vacuna: str = "",
    captacion: str = "",
    cedula: str = "",
    fecha: str = "",
    nombre: str = ""
) -> Dict[str, Any]:
    cleanup_expired()

    item = _QR_CACHE.get(user_id)
    if not item:
        return {"ok": False, "message": "No hay una consulta activa. Sube y procesa un archivo."}

    if not session_key or session_key != item.get("session_key"):
        return {"ok": False, "message": "Sesión inválida o expirada."}

    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 25)))

    month = (month or "").strip()
    estado = (estado or "").strip().upper()
    vacuna = (vacuna or "").strip().upper()
    captacion = (captacion or "").strip().upper()
    cedula = (cedula or "").strip()
    fecha = (fecha or "").strip()
    nombre = (nombre or "").strip().upper()

    regs: List[Dict[str, Any]] = item.get("registros") or []

    def match(r: Dict[str, Any]) -> bool:
        fv = (r.get("fecha_vacunacion") or "").strip()

        if month:
            if not (len(fv) >= 7 and fv[:7] == month):
                return False

        if estado and (r.get("estado_registro") or "").upper() != estado:
            return False

        if vacuna and (r.get("vacuna") or "").upper() != vacuna:
            return False

        if fecha and fv != fecha:
            return False

        if captacion:
            da = r.get("datos_archivo") or {}
            cap = (da.get("_captacion") or "").upper()
            if cap != captacion:
                return False

        if cedula and cedula not in (r.get("numero_identificacion") or ""):
            return False

        if nombre:
            full = " ".join([
                (r.get("primer_nombre") or ""),
                (r.get("segundo_nombre") or ""),
                (r.get("apellido_paterno") or ""),
                (r.get("apellido_materno") or "")
            ]).upper()
            if nombre not in full:
                return False

        return True

    filtered = [r for r in regs if match(r)]
    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = start + page_size
    slice_items = filtered[start:end]

    out_items = []
    for r in slice_items:
        da = r.get("datos_archivo") or {}
        out_items.append({
            "numero_identificacion": r.get("numero_identificacion"),
            "vacuna": r.get("vacuna"),
            "dosis": r.get("dosis"),
            "esquema": r.get("esquema"),
            "fecha_vacunacion": r.get("fecha_vacunacion"),
            "estado_registro": r.get("estado_registro"),
            "_captacion": da.get("_captacion"),
            "primer_nombre": r.get("primer_nombre"),
            "segundo_nombre": r.get("segundo_nombre"),
            "apellido_paterno": r.get("apellido_paterno"),
            "apellido_materno": r.get("apellido_materno"),
            "hash_fila": r.get("hash_fila")
        })

    return {
        "ok": True,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "items": out_items
    }
