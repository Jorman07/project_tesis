from datetime import date
from typing import Any, Dict, Optional, Tuple
import calendar

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import os
from reportlab.lib.utils import ImageReader




def month_to_first_day(ym: str) -> date:
    # ym = "YYYY-MM"
    y, m = map(int, ym.split("-"))
    return date(y, m, 1)

def month_to_last_day(ym: str) -> date:
    y, m = map(int, ym.split("-"))
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, last_day)

def calcular_unidades(categoria: str, packs: int, alcohol_cap_ml: int | None) -> float:
    categoria = categoria.upper().strip()

    if packs <= 0:
        return 0.0

    if categoria == "JERINGAS":
        return float(packs * 100)

    if categoria == "GUANTES":
        return float(packs * 100)

    if categoria == "ALGODON":
        return float(packs * 3)

    if categoria == "ALCOHOL":
        if not alcohol_cap_ml:
            return 0.0
        return float(packs * alcohol_cap_ml)

    return float(packs)



#### para chat bot PRASS#######

def paciente_from_datos(datos: dict, cedula: str):
    if not isinstance(datos, dict):
        datos = {}

    pn = (datos.get("primer_nombre") or "").strip()
    sn = (datos.get("segundo_nombre") or "").strip()
    ap = (datos.get("apellido_paterno") or "").strip()
    am = (datos.get("apellido_materno") or "").strip()

    nombres = " ".join([pn, sn]).strip() or "N/D"
    apellidos = " ".join([ap, am]).strip()
    full = (f"{nombres} {apellidos}".strip() if apellidos else nombres)

    ea = (datos.get("edad_ano") or "").strip()
    em = (datos.get("edad_mes") or "").strip()
    ed = (datos.get("edad_dia") or "").strip()

    # edad formateada bonita
    edad_parts = []
    if ea != "": edad_parts.append(f"{ea} año(s)")
    if em != "": edad_parts.append(f"{em} mes(es)")
    if ed != "": edad_parts.append(f"{ed} día(s)")
    edad_txt = " ".join(edad_parts).strip() or "N/D"

    grupo = (datos.get("grupo_de_riesgo") or "").strip() or "N/D"
    sexo = (datos.get("sexo") or "").strip() or "N/D"
    parroquia = (datos.get("residencia_parroquia") or "").strip() or "N/D"
    canton = (datos.get("residencia_canton") or "").strip() or "N/D"
    establecimiento = (datos.get("nombre_establecimiento_de_salud") or "").strip() or "N/D"

    return {
        "cedula": cedula,
        "nombres": full,
        "sexo": sexo,
        "edad": edad_txt,
        "grupo_riesgo": grupo,
        "parroquia": parroquia,
        "canton": canton,
        "establecimiento": establecimiento
    }



def pick_value(d: Any, key: str) -> Optional[Any]:
    """Obtiene d[key] con limpieza básica."""
    if not isinstance(d, dict):
        return None
    v = d.get(key)
    if isinstance(v, str):
        v = v.strip()
        return v if v != "" else None
    return v


def dato_normalizado(dato: str) -> str:
    return (dato or "").strip().lower().replace(" ", "_")


def edad_texto(datos: Any) -> str:
    ea = pick_value(datos, "edad_ano")
    em = pick_value(datos, "edad_mes")
    ed = pick_value(datos, "edad_dia")

    parts = []
    if ea is not None and str(ea).strip() != "":
        parts.append(f"{ea} año(s)")
    if em is not None and str(em).strip() != "":
        parts.append(f"{em} mes(es)")
    if ed is not None and str(ed).strip() != "":
        parts.append(f"{ed} día(s)")
    return " ".join(parts).strip() or "N/D"


def paciente_from_datos(datos: Any, cedula: str) -> Dict[str, Any]:
    """Arma un resumen del paciente desde datos_archivo."""
    if not isinstance(datos, dict):
        datos = {}

    pn = (datos.get("primer_nombre") or "").strip()
    sn = (datos.get("segundo_nombre") or "").strip()
    ap = (datos.get("apellido_paterno") or "").strip()
    am = (datos.get("apellido_materno") or "").strip()

    nombres = " ".join([pn, sn]).strip() or "N/D"
    apellidos = " ".join([ap, am]).strip()
    full = (f"{nombres} {apellidos}".strip() if apellidos else nombres)

    grupo = (datos.get("grupo_de_riesgo") or "").strip() or "N/D"
    sexo = (datos.get("sexo") or "").strip() or "N/D"
    parroquia = (datos.get("residencia_parroquia") or "").strip() or "N/D"
    canton = (datos.get("residencia_canton") or "").strip() or "N/D"
    establecimiento = (datos.get("nombre_establecimiento_de_salud") or "").strip() or "N/D"

    return {
        "cedula": cedula,
        "nombres": full,
        "sexo": sexo,
        "edad": edad_texto(datos),
        "grupo_riesgo": grupo,
        "parroquia": parroquia,
        "canton": canton,
        "establecimiento": establecimiento,
    }


# Constante a nivel de módulo 
PACIENTE_DATO_MAP: Dict[str, Tuple[str, str]] = {
    # Identidad / demografía
    "primer_nombre": ("primer_nombre", "datos_archivo"),
    "segundo_nombre": ("segundo_nombre", "datos_archivo"),
    "apellido_paterno": ("apellido_paterno", "datos_archivo"),
    "apellido_materno": ("apellido_materno", "datos_archivo"),
    "sexo": ("sexo", "datos_archivo"),
    "etnia": ("etnia", "datos_archivo"),
    "nacionalidad": ("nacionalidad_pais", "datos_archivo"),
    "tipo_identificacion": ("tipo_identificacion", "datos_archivo"),

    # Edad (si pides edad compuesta, se maneja aparte)
    "edad_ano": ("edad_ano", "datos_archivo"),
    "edad_mes": ("edad_mes", "datos_archivo"),
    "edad_dia": ("edad_dia", "datos_archivo"),

    # Ubicación
    "provincia": ("residencia_provincia", "datos_archivo"),
    "canton": ("residencia_canton", "datos_archivo"),
    "parroquia": ("residencia_parroquia", "datos_archivo"),

    # Vacunación / registro
    "vacuna_raw": ("_vacuna_raw", "datos_archivo"),
    "vacuna_canon": ("_vacuna_canon", "datos_archivo"),
    "vacuna_variante": ("_vacuna_variante", "datos_archivo"),
    "captacion": ("_captacion", "datos_archivo"),
    "esquema": ("esquema", "datos_archivo"),
    "dosis": ("dosis", "datos_archivo"),
    "lote": ("lote", "datos_archivo"),
    "fecha_vacunacion": ("fecha_vacunacion", "datos_archivo"),
    "proxima_dosis": ("fecha_proxima_dosis", "datos_archivo"),
    "grupo_riesgo": ("grupo_de_riesgo", "datos_archivo"),

    # Personal / establecimiento
    "vacunador": ("nombre_vacuandor", "datos_archivo"),
    "profesional_registra": ("nombre_profesional_que_registra", "datos_archivo"),
    "establecimiento": ("nombre_establecimiento_de_salud", "datos_archivo"),
    "punto_vacunacion": ("punto_de_vacunacion", "datos_archivo"),

    # Metadatos
    "origen_datos": ("origen_datos", "datos_archivo"),
    "tipo_registro": ("tipo_de_registro", "datos_archivo"),
}



##### para pdf prass #########


def pick_first(d: dict, keys: list):
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip()
            if v != "":
                return v
        else:
            return v
    return None



def build_prass_report_pdf(tipo: str, fecha: str, rep: dict, alertas_resumen: list, alertas_detalle: list) -> bytes:
   

    tipo = (tipo or "").upper().strip()
    rep = rep or {}
    alertas_resumen = alertas_resumen or []
    alertas_detalle = alertas_detalle or []

    # --------------------------
    # Indexar alertas por fecha (YYYY-MM-DD) y por mes (YYYY-MM)
    # --------------------------
    alerts_by_day = {}    # 'YYYY-MM-DD' -> [alertas...]
    alerts_by_month = {}  # 'YYYY-MM' -> [alertas...]

    for a in alertas_detalle:
        f = (a.get("fecha_vacunacion") or "").strip()
        if not f:
            continue
        alerts_by_day.setdefault(f, []).append(a)
        alerts_by_month.setdefault(f[:7], []).append(a)

    def alerts_for_key(key: str):
        if tipo == "ANUAL":
            return alerts_by_month.get(key, [])
        return alerts_by_day.get(key, [])

    def has_alert_for_key(key: str) -> bool:
        return len(alerts_for_key(key)) > 0

    # --------------------------
    # Helpers formato
    # --------------------------
    def fmt_ddmmyyyy(iso_yyyy_mm_dd: str) -> str:
        try:
            return datetime.strptime(iso_yyyy_mm_dd, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return iso_yyyy_mm_dd

    def fmt_mmyyyy(yyyy_mm: str) -> str:
        try:
            return datetime.strptime(yyyy_mm + "-01", "%Y-%m-%d").strftime("%m/%Y")
        except Exception:
            return yyyy_mm

    def sum_int(a, b) -> int:
        try:
            return int(a or 0) + int(b or 0)
        except Exception:
            return 0

    def safe_text(s: str, max_len=230) -> str:
        s = (s or "").strip()
        if len(s) <= max_len:
            return s
        return s[:max_len-3] + "..."

    #  DETALLE REAL DESDE TU registro_json
    def alert_detail_line(alert: dict) -> str:
        tipo_alerta = str(alert.get("tipo_alerta") or "")
        estado = str(alert.get("estado") or "")
        rj = alert.get("registro_json") or {}

        ced = (rj.get("numero_de_identificacion") or "").strip()
        p_nom = (rj.get("primer_nombre") or "").strip()
        s_nom = (rj.get("segundo_nombre") or "").strip()
        ape_pat = (rj.get("apellido_paterno") or "").strip()
        ape_mat = (rj.get("apellido_materno") or "").strip()

        vacuna = (rj.get("vacuna") or rj.get("_vacuna_canon") or "").strip()
        dosis = (rj.get("dosis") or "").strip()
        esquema = (rj.get("esquema") or "").strip()
        capt = (rj.get("_captacion") or "").strip()

        est = (rj.get("nombre_establecimiento_de_salud") or "").strip()
        prof = (rj.get("nombre_profesional_que_registra") or "").strip()

        nombre = " ".join([p_nom, s_nom, ape_pat, ape_mat]).strip()

        parts = []
        if tipo_alerta:
            parts.append(tipo_alerta)
        if estado:
            parts.append(f"({estado})")
        if ced:
            parts.append(f"Cédula: {ced}")
        if nombre:
            parts.append(f"Paciente: {nombre}")
        if vacuna:
            parts.append(f"Vacuna: {vacuna}")
        if dosis:
            parts.append(f"Dosis: {dosis}")
        if capt:
            parts.append(f"Captación: {capt}")
        if esquema:
            parts.append(f"Esquema: {esquema}")
        if est:
            parts.append(f"Estab.: {est}")
        if prof:
            parts.append(f"Registrador: {prof}")

        return safe_text(" • ".join(parts), 260)

    # --------------------------
    # RUTAS ABSOLUTAS (según tu estructura)
    # app/services/*.py  -> app/static/img/*.jpg
    # --------------------------
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))               # .../app/services
    STATIC_IMG_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "static", "img"))

    HEADER_PATH = os.path.join(STATIC_IMG_DIR, "header_msp.jpg")
    FOOTER_PATH = os.path.join(STATIC_IMG_DIR, "footer_msp.jpg")

    header_img = ImageReader(HEADER_PATH) if os.path.exists(HEADER_PATH) else None
    footer_img = ImageReader(FOOTER_PATH) if os.path.exists(FOOTER_PATH) else None

    # --------------------------
    # PDF setup (márgenes reservados)
    # --------------------------
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.0*cm,
        rightMargin=2.0*cm,
        topMargin=4.6*cm,     # espacio para header grande
        bottomMargin=3.0*cm   # espacio para footer grande
    )

    styles = getSampleStyleSheet()
    # "Arial" práctico en ReportLab: Helvetica
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=13.5, leading=16, spaceAfter=8)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, spaceAfter=6)
    TXT = ParagraphStyle("TXT", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=13)
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=12, textColor=colors.grey)

    story = []

    def make_table(data, col_widths, header=True):
        t = Table(data, colWidths=col_widths)
        st = [
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("GRID", (0,0), (-1,-1), 0.35, colors.black),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]
        if header:
            st += [
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("LINEBELOW", (0,0), (-1,0), 0.6, colors.black),
            ]
        t.setStyle(TableStyle(st))
        return t

    # --------------------------
    # Header/Footer en TODAS las páginas (más grande, casi todo el ancho)
    # --------------------------
    def draw_header_footer(canvas, _doc):
        canvas.saveState()
        page_w, page_h = A4

        # Ancho casi total de la hoja
        x = 0.7 * cm
        w_full = page_w - (2 * x)

        # ===== HEADER =====
        header_h = 3.8 * cm
        y_header = page_h - header_h - 0.25 * cm

        if header_img:
            canvas.drawImage(
                header_img,
                x, y_header,
                width=w_full,
                height=header_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto"
            )

        # Texto en DOS líneas, a la derecha y centrado verticalmente
        line1 = "Ministerio de Salud Pública Dirección"
        line2 = "Distrital 09D08 – Pascuales 2- Salud"

        canvas.setFont("Helvetica-Bold", 10.2)

        x_text = x + w_full - 0.9 * cm
        y_mid = y_header + (header_h / 2.0)

        canvas.drawRightString(x_text, y_mid + 0.22 * cm, line1)
        canvas.drawRightString(x_text, y_mid - 0.22 * cm, line2)

        # ===== FOOTER =====
        if footer_img:
            footer_h = 2.3 * cm
            y_footer = 0.15 * cm
            canvas.drawImage(
                footer_img,
                x, y_footer,
                width=w_full,
                height=footer_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto"
            )

        canvas.restoreState()




    # --------------------------
    # Encabezado tipo Word
    # --------------------------
    fecha_elab = datetime.now().strftime("%d-%m-%Y")

    if tipo == "MENSUAL":
        asunto = f"INFORME TÉCNICO: VALIDACIÓN Y JUSTIFICACIÓN DE DIFERENCIAS DE PRASS Y ENI CORRESPONDIENTE AL MES {fecha}"
    elif tipo == "ANUAL":
        asunto = f"INFORME TÉCNICO: VALIDACIÓN Y JUSTIFICACIÓN DE DIFERENCIAS DE PRASS Y ENI CORRESPONDIENTE AL AÑO {fecha}"
    else:
        asunto = f"INFORME TÉCNICO: VALIDACIÓN Y JUSTIFICACIÓN DE DIFERENCIAS DE PRASS Y ENI CORRESPONDIENTE AL DÍA {fecha}"

    story.append(Paragraph("DIRECCIÓN DISTRITAL 09D08", H2))
    story.append(Spacer(1, 6))

    story.append(make_table(
        [["Fecha de elaboración:", fecha_elab],
         ["Proceso/Unidad:", "Gestión Interna de Inmunizaciones"]],
        [5.2*cm, 10.8*cm],
        header=False
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>INFORME TÉCNICO</b>", H1))
    story.append(Paragraph(f"<b>Asunto:</b> {asunto}", TXT))
    story.append(Spacer(1, 12))

    # --------------------------
    # Antecedente + objetivos (texto completo)
    # --------------------------
    story.append(Paragraph("Antecedente:", H2))
    story.append(Paragraph(
        "El Programa Ampliado de Inmunizaciones (PAI), desde hace 27 años, ha participado activamente en la erradicación de algunas de las enfermedades inmunoprevenibles y en la prevención y control efectivo de otras, asegurando y garantizando el acceso universal a los servicios de inmunizaciones de todos los ecuatorianos en todos los niveles de salud, para lo cual se ha requerido desarrollar y mantener con mucho esfuerzo la aplicación de estrategias apoyadas en técnicas y conocimientos actualizados, las mismas que han tenido respaldo y aplicación de todos los miembros de los equipos de salud a nivel nacional.",
        TXT
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "el presente manual de normas técnico-administrativas, métodos y procedimientos de vacunación y vigilancia epidemiológica del programa ampliado de inmunizaciones (pai), ha sido actualizado tomando como base las políticas de salud vigentes, la observación del desempeño del los trabajadores de salud, las sugerencias y recomendaciones de las evaluaciones nacionales e internacionales del pai, los mandatos de los ministros de los países de la región de las américas y las orientaciones de la ops/oms.",
        TXT
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Deseo felicitar a todo el personal de salud por ser los protagonistas del cambio de calidad y eficiencia alcanzada por el PAI y pedirles su mayor esfuerzo para alcanzar la meta final de crear un país sano libre de enfermedades prevenibles por vacunación.",
        TXT
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("OBJETIVO GENERAL:", H2))
    story.append(Paragraph(
        "Notificar a las autoridades sobre los errores programático al registrar en el prass y que no coinciden con nuestro reporte ENI de acuerdo a lo ya reportado correspondiente a nuestra unidad operativa.",
        TXT
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("OBJETIVO ESPECIFICOS:", H2))
    story.append(Paragraph("• Disminuir errores programáticos al momento de subir datos.", TXT))
    story.append(Paragraph("• Corroborar datos en el sistema con la descarga.", TXT))
    story.append(Spacer(1, 12))

    # --------------------------
    # DESARROLLO (igual)
    # --------------------------
    story.append(Paragraph("Desarrollo:", H2))

    def add_block(label: str, total_dosis: int, key_for_alerts: str):
        story.append(Paragraph(f"<b>{label}</b>", TXT))
        story.append(Spacer(1, 2))

        if has_alert_for_key(key_for_alerts):
            story.append(Paragraph(
                f"Se evidencia un total de {int(total_dosis)} dosis entre captación temprana y tardía, con novedades.",
                TXT
            ))
            dets = alerts_for_key(key_for_alerts)
            for d in dets[:6]:
                story.append(Paragraph(f"• {alert_detail_line(d)}", SMALL))
        else:
            story.append(Paragraph(
                f"Se evidencia un total de {int(total_dosis)} dosis entre captación temprana y tardía, sin novedades.",
                TXT
            ))

        story.append(Spacer(1, 7))

    if tipo == "DIARIO":
        total = sum_int(rep.get("captacion_temprana"), rep.get("captacion_tardia"))
        add_block(fmt_ddmmyyyy(fecha), total, fecha)

    elif tipo == "MENSUAL":
        arr = rep.get("captacion_por_dia") or []
        if not arr:
            story.append(Paragraph("No se registran datos de captación para el periodo.", TXT))
            story.append(Spacer(1, 8))
        else:
            for x in arr:
                f = str(x.get("fecha") or "")
                tot = sum_int(x.get("temprana"), x.get("tardia"))
                add_block(fmt_ddmmyyyy(f), tot, f)

    else:  # ANUAL
        arr = rep.get("captacion_por_mes") or []
        if not arr:
            story.append(Paragraph("No se registran datos de captación para el periodo.", TXT))
            story.append(Spacer(1, 8))
        else:
            for x in arr:
                mes = str(x.get("mes") or "")
                tot = sum_int(x.get("temprana"), x.get("tardia"))
                add_block(fmt_mmyyyy(mes), tot, mes)

    story.append(Spacer(1, 10))

    # --------------------------
    # ALERTAS (resumen)
    # --------------------------
    story.append(Paragraph("Alertas del periodo:", H2))
    if not alertas_resumen:
        story.append(Paragraph("No se registran alertas en el periodo.", TXT))
    else:
        data = [["Tipo", "Estado", "Total"]]
        for a in alertas_resumen:
            data.append([str(a.get("tipo_alerta","")), str(a.get("estado","")), str(a.get("total",0))])
        t = make_table(data, [7.2*cm, 5.2*cm, 3.0*cm], header=True)
        t.setStyle(TableStyle([("ALIGN",(2,1),(2,-1),"RIGHT")]))
        story.append(t)

    story.append(Spacer(1, 12))

    # --------------------------
    # Resumen + tablas (igual)
    # --------------------------
    story.append(Paragraph("Resumen:", H2))

    if tipo == "ANUAL":
        kpis = [
            ["Año", fecha],
            ["Total dosis", str(int(rep.get("total_anual", 0) or 0))],
            ["Captación temprana", str(int(rep.get("captacion_temprana", 0) or 0))],
            ["Captación tardía", str(int(rep.get("captacion_tardia", 0) or 0))],
        ]
    elif tipo == "MENSUAL":
        kpis = [
            ["Mes", fecha],
            ["Total dosis", str(int(rep.get("total_mensual", 0) or 0))],
            ["Personas únicas", str(int(rep.get("personas_total", 0) or 0))],
            ["Captación temprana", str(int(rep.get("captacion_temprana", 0) or 0))],
            ["Captación tardía", str(int(rep.get("captacion_tardia", 0) or 0))],
        ]
    else:
        kpis = [
            ["Día", fmt_ddmmyyyy(fecha)],
            ["Total dosis", str(int(rep.get("total_diario", 0) or 0))],
            ["Personas únicas", str(int(rep.get("personas_total", 0) or 0))],
            ["Captación temprana", str(int(rep.get("captacion_temprana", 0) or 0))],
            ["Captación tardía", str(int(rep.get("captacion_tardia", 0) or 0))],
        ]

    story.append(make_table([["Indicador","Valor"]] + kpis, [8.0*cm, 7.0*cm], header=True))
    story.append(Spacer(1, 10))

    # Dosis por vacuna
    story.append(Paragraph("Dosis por vacuna:", H2))
    dosis = rep.get("dosis_por_vacuna") or []
    if not dosis:
        story.append(Paragraph("Sin datos.", TXT))
    else:
        dt = [["Vacuna","Dosis"]]
        for r in dosis[:60]:
            dt.append([str(r.get("vacuna","")), str(int(r.get("dosis_total",0) or 0))])
        t = make_table(dt, [12.0*cm, 3.0*cm], header=True)
        t.setStyle(TableStyle([("ALIGN",(1,1),(1,-1),"RIGHT")]))
        story.append(t)
    story.append(Spacer(1, 10))

    # Personas por vacuna
    story.append(Paragraph("Personas por vacuna:", H2))
    per = rep.get("personas_por_vacuna") or []
    if not per:
        story.append(Paragraph("Sin datos.", TXT))
    else:
        dt = [["Vacuna","Personas"]]
        for r in per[:60]:
            dt.append([str(r.get("vacuna","")), str(int(r.get("personas_total",0) or 0))])
        t = make_table(dt, [12.0*cm, 3.0*cm], header=True)
        t.setStyle(TableStyle([("ALIGN",(1,1),(1,-1),"RIGHT")]))
        story.append(t)

    story.append(Spacer(1, 12))

    # --------------------------
    # Nudos críticos + Conclusión (texto completo)
    # --------------------------
    story.append(Paragraph("Nudos críticos", H2))
    story.append(Paragraph("Como ya es de conocimiento siempre solemos tener un mal funcionamiento del sistema prass.", TXT))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "El sistema prass se encuentra inhabilitado por varias horas lo cual nos retrasa en nuestras labores, como lo es el no poder registrar las vacunas que se administran.",
        TXT
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Conclusión", H2))
    story.append(Paragraph(
        "Se observa que hay poca diferencia en sistema prass debido a la mala digitación y a la cantidad de perfiles que maneja el personal de salud que conlleva a la equivocación al registrar nuestra producción diaria dando como resultado este tipo de inconvenientes que es un descuadre con lo que reportamos y lo que digitamos.",
        TXT
    ))
    story.append(Spacer(1, 14))

    # --------------------------
    # Firmas (nombres reales TAL CUAL)
    # --------------------------


    story.append(Paragraph("Firmas de responsabilidad", H2))

    # Estilo para que el texto haga wrap y no se monte
    CELL = ParagraphStyle(
        "CELL",
        parent=TXT,
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        alignment=1,   # CENTER
    )

    CELL_B = ParagraphStyle(
        "CELL_B",
        parent=CELL,
        fontName="Helvetica-Bold",
    )

    # 4 columnas: [Etiqueta] [Nombre] [Cargo] [Firma]
    data = [
        ["", Paragraph("NOMBRE:", CELL_B), Paragraph("CARGO:", CELL_B), Paragraph("FIRMA:", CELL_B)],
        [
            Paragraph("Elaborado y<br/>Revisado por:", CELL_B),
            Paragraph("MSc. Yosely<br/>Holguín Reyes", CELL),
            Paragraph("Responsable de<br/>Vacunatorio", CELL_B),
            ""  # firma
        ],
        [
            Paragraph("Aprobado por:", CELL_B),
            Paragraph("Dra. Ruth<br/>Estupiñan Triviño", CELL),
            Paragraph("Administradora<br/>Técnica de Centro de<br/>Salud Flor de Bastión<br/>2", CELL_B),
            ""  # firma
        ],
    ]

    # Anchos (ajustados para que el cargo quepa sin montarse)
    col_widths = [3.2*cm, 4.0*cm, 6.0*cm, 4.8*cm]

    t = Table(data, colWidths=col_widths, rowHeights=[0.9*cm, 2.0*cm, 2.4*cm])

    t.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.8, colors.black),

        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",  (0,0), (-1,-1), "CENTER"),

        # padding para evitar que el texto toque bordes
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0), (-1,-1), 6),
        ("TOPPADDING",  (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),

        # header
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F3F4F6")),
    ]))

    story.append(t)



    # --------------------------
    # Build con header/footer en todas las páginas
    # --------------------------
    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf
