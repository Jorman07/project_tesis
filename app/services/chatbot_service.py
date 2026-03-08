import os
import requests
import re
import time
from app.services.supabase_client import supabase

RASA_URL = os.getenv("RASA_URL", "http://127.0.0.1:5005")


# ---------------------------
# Helpers normalización
# ---------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().upper())

def _contains_norm(hay: str, needle: str) -> bool:
    return _norm(needle) in _norm(hay)

# ---------------------------
# Cache simple en memoria (TTL)
# ---------------------------
_CATALOG_CACHE = {
    "ts": 0.0,
    "ttl": 300.0,  # 5 min
    "categorias": [],     # ["JERINGAS", ...]
    "tipos_by_cat": {},   # {"JERINGAS": ["23G x 1\" 0.5ml", ...]}
}




class ChatbotService:
    #========= RASA INTERACTION =========
    @staticmethod
    def ask_rasa(message: str, session_id: str) -> str:
        payload = {"sender": session_id, "message": message}
        url = f"{RASA_URL}/webhooks/rest/webhook"

        t0 = time.time()
        try:
            r = requests.post(url, json=payload, timeout=(3.05, 45))
            dt = round(time.time() - t0, 3)

            print("ASK_RASA status:", r.status_code, "time:", dt, "seg", flush=True)

            r.raise_for_status()

            data = r.json()
            print("ASK_RASA raw:", data, flush=True)

            if not isinstance(data, list):
                print("ASK_RASA unexpected payload type", type(data), flush=True)
                return ""

            parts = [m.get("text") for m in data if isinstance(m, dict) and m.get("text")]
            reply = "\n".join(parts).strip()

            print("ASK_RASA reply:", reply if reply else "<EMPTY>", flush=True)
            return reply

        except Exception as e:
            dt = round(time.time() - t0, 3)
            print("ASK_RASA ERROR:", str(e), "time:", dt, "seg", flush=True)
            raise

    @staticmethod
    def start_conversation(id_usuario: int, metadata: dict | None = None) -> int:
        meta = metadata or {}
        r = supabase.rpc("chat_start_conversation", {
            "p_id_usuario": id_usuario,
            "p_metadata": meta
        }).execute()

        # la RPC devuelve el bigint directamente o como fila, depende del cliente;
        # este manejo te cubre ambos casos.
        if isinstance(r.data, int):
            return int(r.data)
        if isinstance(r.data, list) and r.data:
            # a veces viene [{"id": 123}] o [{"chat_start_conversation": 123}]
            row = r.data[0] or {}
            for v in row.values():
                if str(v).isdigit():
                    return int(v)
        raise RuntimeError("No se pudo crear conversación (chat_start_conversation).")

    @staticmethod
    def log_message(
        conversation_id: int,
        id_usuario: int,
        role: str,
        text: str,
        source: str | None = None,
        intent: str | None = None,
        intent_confidence: float | None = None,
        entities: list | None = None,
        action_name: str | None = None,
        error: dict | None = None,
    ) -> int:
        r = supabase.rpc("chat_log_message", {
            "p_conversation_id": int(conversation_id),
            "p_id_usuario": int(id_usuario),
            "p_role": role,
            "p_text": text,
            "p_intent": intent,
            "p_intent_confidence": intent_confidence,
            "p_entities": entities or [],
            "p_action_name": action_name,
            "p_source": source,
            "p_error": error or {}
        }).execute()

        # igual: puede venir int o lista
        if isinstance(r.data, int):
            return int(r.data)
        if isinstance(r.data, list) and r.data:
            row = r.data[0] or {}
            for v in row.values():
                if str(v).isdigit():
                    return int(v)
        return 0  # no bloquees el chat si falla log
    
    # ========= CHAT MEMORY (RPC) =========
    @staticmethod
    def memory_upsert(id_usuario: int, key: str, value: dict):
        # RPC: chat_memory_upsert(p_id_usuario bigint, p_key text, p_value jsonb)
        supabase.rpc("chat_memory_upsert", {
            "p_id_usuario": int(id_usuario),
            "p_key": key,
            "p_value": value
        }).execute()

    @staticmethod
    def memory_get_many(id_usuario: int, keys: list[str]) -> dict:
        # si aún no tienes una RPC para leer memory, crea una.
        # Por ahora, lectura directa NO (RLS). Lo ideal: RPC security definer.
        # Te dejo una opción rápida: usa una RPC "chat_memory_get_many".
        r = supabase.rpc("chat_memory_get_many", {
            "p_id_usuario": int(id_usuario),
            "p_keys": keys
        }).execute()
        rows = r.data or []
        out = {}
        for row in rows:
            out[row.get("key")] = row.get("value")
        return out

    # ========= CATALOGO INSUMOS =========
    @staticmethod
    def _refresh_insumo_catalog_if_needed():
        now = time.time()
        if (now - _CATALOG_CACHE["ts"]) < _CATALOG_CACHE["ttl"] and _CATALOG_CACHE["categorias"]:
            return

        # 1) categorias activas
        rc = supabase.rpc("list_insumo_categorias", {"p_only_active": True}).execute()
        categorias = [ (x.get("categoria") or "").strip() for x in (rc.data or []) ]
        categorias = [c for c in categorias if c]

        # 2) tipos por categoria (solo activos, excluir caducados)
        tipos_by_cat = {}
        for cat in categorias:
            rt = supabase.rpc("list_insumo_tipos", {
                "p_categoria": cat,
                "p_q": None,
                "p_estado": True,
                "p_exp_days": None,
                "p_excluir_caducados": True
            }).execute()
            tipos = [ (x.get("nombre_tipo") or "").strip() for x in (rt.data or []) ]
            tipos_by_cat[cat] = [t for t in tipos if t]

        _CATALOG_CACHE["ts"] = now
        _CATALOG_CACHE["categorias"] = categorias
        _CATALOG_CACHE["tipos_by_cat"] = tipos_by_cat

    @staticmethod
    def detect_insumo_from_text(text: str) -> dict:
        """
        Devuelve:
          {
            "categoria": "JERINGAS" | None,
            "nombre_tipo": "23G x 1\" 0.5ml" | None
          }
        """
        ChatbotService._refresh_insumo_catalog_if_needed()
        t = _norm(text)

        # detectar categoría por keyword
        cat_hit = None
        for cat in _CATALOG_CACHE["categorias"]:
            if _contains_norm(t, cat):
                cat_hit = cat
                break

        # detectar tipo: buscamos match por "contiene" dentro de los tipos conocidos
        tipo_hit = None
        # si detectamos categoría, buscamos en esa
        cats_to_search = [cat_hit] if cat_hit else _CATALOG_CACHE["categorias"]

        for cat in cats_to_search:
            for tipo in _CATALOG_CACHE["tipos_by_cat"].get(cat, []):
                # match tolerante: contiene el tipo completo o una parte significativa
                if _contains_norm(t, tipo):
                    cat_hit = cat
                    tipo_hit = tipo
                    return {"categoria": cat_hit, "nombre_tipo": tipo_hit}

        # match “light”: si el texto trae "0.5ML" o "1ML" o "PRECARGADA", intenta aproximar en JERINGAS
        if not tipo_hit:
            # heurística simple para tu dataset de jeringas
            if "JERING" in t or "ML" in t or "PRECARG" in t or "G X" in t:
                for tipo in _CATALOG_CACHE["tipos_by_cat"].get("JERINGAS", []):
                    if ("PRECARG" in t and "PRECARG" in _norm(tipo)) or ("0.5ML" in t and "0.5ML" in _norm(tipo)) or ("1ML" in t and "1ML" in _norm(tipo)):
                        cat_hit = cat_hit or "JERINGAS"
                        tipo_hit = tipo
                        break

        return {"categoria": cat_hit, "nombre_tipo": tipo_hit}

    # ========= MEMORIA DESDE TEXTO =========
    @staticmethod
    def update_memory_from_text(id_usuario: int, message: str):
        """
        Guarda lo necesario para inventario (insumos) y deja listo para biológicos.
        """
        det = ChatbotService.detect_insumo_from_text(message)

        if det.get("categoria"):
            ChatbotService.memory_upsert(id_usuario, "ultimo_insumo_categoria", {"categoria": det["categoria"]})

        if det.get("nombre_tipo"):
            ChatbotService.memory_upsert(
                id_usuario,
                "ultimo_insumo_tipo",
                {"categoria": det.get("categoria"), "nombre_tipo": det["nombre_tipo"]}
            )

        # Hooks futuros (biológicos/insumos)
        # - si el mensaje menciona "biologico" o un nombre de biologico, guardar ultimo_biologico
        # - si el usuario selecciona un lote, guardar ultimo_lote_insumo

    # ========= ENRIQUECER MENSAJE =========
    @staticmethod
    def enrich_message_with_memory(id_usuario: int, message: str) -> str:
        """
        Completa mensajes incompletos para inventario:
          - "y los lotes?" -> agrega tipo/categoria si falta
          - "stock?" -> agrega tipo/categoria si falta
          - "biologicos asociados?" -> agrega tipo/categoria si falta
        """
        low = (message or "").lower()

        # solo aplica si el usuario habla de inventario/insumos
        wants_lotes = any(k in low for k in ["lote", "lotes"])
        wants_stock = any(k in low for k in ["stock", "existencia", "disponible", "inventario"])
        wants_asoc = any(k in low for k in ["asociad", "biologic", "para que vacuna", "para qué vacuna"])

        if not (wants_lotes or wants_stock or wants_asoc):
            return message

        # si ya viene una categoría/tipo en el mensaje, no toques
        det = ChatbotService.detect_insumo_from_text(message)
        if det.get("nombre_tipo") or det.get("categoria"):
            return message

        mem = ChatbotService.memory_get_many(id_usuario, ["ultimo_insumo_tipo", "ultimo_insumo_categoria"])
        last_tipo = mem.get("ultimo_insumo_tipo") or {}
        last_cat = mem.get("ultimo_insumo_categoria") or {}

        categoria = (last_tipo.get("categoria") or last_cat.get("categoria") or "").strip()
        nombre_tipo = (last_tipo.get("nombre_tipo") or "").strip()

        # si no tenemos memoria, no inventamos
        if not categoria and not nombre_tipo:
            return message

        # reescritura “suave” para que Rasa/tu router lo entienda
        suffix = []
        if categoria:
            suffix.append(f"categoria {categoria}")
        if nombre_tipo:
            suffix.append(f"tipo {nombre_tipo}")

        return message.strip() + " (" + ", ".join(suffix) + ")"


 # ---------- memoria (RPC) ----------
    @staticmethod
    def memory_upsert(id_usuario: int, key: str, value: dict):
        supabase.rpc("chat_memory_upsert", {
            "p_id_usuario": int(id_usuario),
            "p_key": key,
            "p_value": value
        }).execute()

    @staticmethod
    def memory_get_many(id_usuario: int, keys: list[str]) -> dict:
        r = supabase.rpc("chat_memory_get_many", {
            "p_id_usuario": int(id_usuario),
            "p_keys": keys
        }).execute()
        out = {}
        for row in (r.data or []):
            out[row.get("key")] = row.get("value")
        return out

    # ---------- catálogo insumos ----------
    @staticmethod
    def _refresh_insumo_catalog_if_needed():
        now = time.time()
        if (now - _CATALOG_CACHE["ts"]) < _CATALOG_CACHE["ttl"] and _CATALOG_CACHE["categorias"]:
            return

        rc = supabase.rpc("list_insumo_categorias", {"p_only_active": True}).execute()
        categorias = [ (x.get("categoria") or "").strip() for x in (rc.data or []) ]
        categorias = [c for c in categorias if c]

        tipos_by_cat = {}
        for cat in categorias:
            rt = supabase.rpc("list_insumo_tipos", {
                "p_categoria": cat,
                "p_q": None,
                "p_estado": True,
                "p_exp_days": None,
                "p_excluir_caducados": True
            }).execute()
            tipos = [ (x.get("nombre_tipo") or "").strip() for x in (rt.data or []) ]
            tipos_by_cat[cat] = [t for t in tipos if t]

        _CATALOG_CACHE["ts"] = now
        _CATALOG_CACHE["categorias"] = categorias
        _CATALOG_CACHE["tipos_by_cat"] = tipos_by_cat

    @staticmethod
    def detect_insumo_from_text(text: str) -> dict:
        ChatbotService._refresh_insumo_catalog_if_needed()
        t = _norm(text)

        cat_hit = None
        for cat in _CATALOG_CACHE["categorias"]:
            if _contains_norm(t, cat):
                cat_hit = cat
                break

        # busca tipo exacto primero
        cats_to_search = [cat_hit] if cat_hit else _CATALOG_CACHE["categorias"]
        for cat in cats_to_search:
            for tipo in _CATALOG_CACHE["tipos_by_cat"].get(cat, []):
                if _contains_norm(t, tipo):
                    return {"categoria": cat, "nombre_tipo": tipo}

        # heurística simple para JERINGAS (si el usuario escribe parcial)
        if ("JERING" in t) or ("ML" in t) or ("PRECARG" in t) or ("G X" in t) or ("GX" in t):
            for tipo in _CATALOG_CACHE["tipos_by_cat"].get("JERINGAS", []):
                nt = _norm(tipo)
                if ("PRECARG" in t and "PRECARG" in nt) or ("0.5ML" in t and "0.5ML" in nt) or ("1ML" in t and "1ML" in nt):
                    return {"categoria": "JERINGAS", "nombre_tipo": tipo}

        return {"categoria": cat_hit, "nombre_tipo": None}

    # ---------- 1) guardar memoria desde texto del usuario ----------
    @staticmethod
    def update_memory_from_text(id_usuario: int, message: str):
        msg = message or ""

        # A) detectar insumo (categoria/tipo)
        det = ChatbotService.detect_insumo_from_text(msg)
        if det.get("categoria"):
            ChatbotService.memory_upsert(id_usuario, "ultimo_insumo_categoria", {"categoria": det["categoria"]})
        if det.get("nombre_tipo"):
            ChatbotService.memory_upsert(
                id_usuario,
                "ultimo_insumo_tipo",
                {"categoria": det.get("categoria"), "nombre_tipo": det["nombre_tipo"]}
            )

        # B) detectar lote si lo menciona el usuario
        m_lote = re.search(r"\b(lote)\s*[:#]?\s*([A-Za-z0-9\-_.\/]+)\b", msg, flags=re.I)
        if m_lote:
            lote = m_lote.group(2).strip()
            ChatbotService.memory_upsert(id_usuario, "ultimo_lote_insumo", {
                "lote": lote,
                "categoria": det.get("categoria"),
                "nombre_tipo": det.get("nombre_tipo")
            })

        # C) detectar “por caducar en N días”
        m_days = re.search(r"\b(\d{1,3})\s*(d[ií]as|dias)\b", msg, flags=re.I)
        if m_days and ("caduc" in msg.lower() or "vencer" in msg.lower()):
            exp_days = int(m_days.group(1))
            ChatbotService.memory_upsert(id_usuario, "ultimo_insumo_exp_days", {"exp_days": exp_days, "excluir_caducados": False})

        # D) detectar biológico si el usuario lo nombra explícitamente
        # (sirve para “vía del biológico BCG”)
        m_bio = re.search(r"\bbiol[oó]gico\s+([A-Za-z0-9ÁÉÍÓÚÜÑ\-_. ]{2,40})", msg, flags=re.I)
        if m_bio:
            nombre = m_bio.group(1).strip()
            if nombre:
                ChatbotService.memory_upsert(id_usuario, "ultimo_biologico", {"nombre_biologico": nombre})

    # ---------- 2) enriquecer mensaje incompleto usando memoria ----------
    @staticmethod
    def enrich_message_with_memory(id_usuario: int, message: str) -> str:
        low = (message or "").lower()

        wants_lotes = any(k in low for k in ["lote", "lotes", "caducidad", "caduca", "fabricacion", "fabricación"])
        wants_stock = any(k in low for k in ["stock", "existencia", "inventario", "disponible", "unidades", "packs", "paquetes", "cajas"])
        wants_asoc = any(k in low for k in ["asociad", "para que", "para qué", "biologic", "vacun"])

        # solo si parece consulta de inventario/insumo
        if not (wants_lotes or wants_stock or wants_asoc):
            return message

        # si el usuario ya puso categoria/tipo, no tocar
        det = ChatbotService.detect_insumo_from_text(message)
        if det.get("nombre_tipo") or det.get("categoria"):
            return message

        mem = ChatbotService.memory_get_many(id_usuario, ["ultimo_insumo_tipo", "ultimo_insumo_categoria"])
        last_tipo = mem.get("ultimo_insumo_tipo") or {}
        last_cat = mem.get("ultimo_insumo_categoria") or {}

        categoria = (last_tipo.get("categoria") or last_cat.get("categoria") or "").strip()
        nombre_tipo = (last_tipo.get("nombre_tipo") or "").strip()

        if not categoria and not nombre_tipo:
            return message

        # agrega contexto sin cambiar el mensaje original
        parts = []
        if categoria:
            parts.append(f"categoria {categoria}")
        if nombre_tipo:
            parts.append(f"tipo {nombre_tipo}")

        return message.strip() + " (" + ", ".join(parts) + ")"

    # ---------- 3) (clave) guardar memoria desde la respuesta del bot ----------
    @staticmethod
    def update_memory_from_bot_reply(id_usuario: int, reply: str):
        """
        Cuando el bot responde con biológicos asociados, normalmente vienen así:
        • **BCG** | Vía: ... | Ángulo: ...
        Extraemos nombres y guardamos:
          - ultimo_biologico
          - ultimos_biologicos_asociados
        """
        if not reply:
            return

        # extrae nombres en formato • **NOMBRE**
        names = re.findall(r"•\s*\*\*(.+?)\*\*", reply)
        names = [n.strip() for n in names if n.strip()]

        if names:
            ChatbotService.memory_upsert(id_usuario, "ultimos_biologicos_asociados", {"items": names[:20]})
            ChatbotService.memory_upsert(id_usuario, "ultimo_biologico", {"nombre_biologico": names[0]})