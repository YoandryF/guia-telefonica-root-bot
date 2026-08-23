"""
Shared state and helper functions for the bot.
"""

import os
import time
import logging
from dotenv import load_dotenv
from supabase_service import SupabaseService

load_dotenv()

logger       = logging.getLogger(__name__)
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
db            = SupabaseService()

# Cache de resultados de búsqueda: {chat_id: {'data': ..., 'ts': float}}
_cache_resultados: dict = {}
_CACHE_TTL = 600  # 10 minutos

# Cache de admins: {chat_id_str: (es_admin: bool, expires: float)}
_admin_cache: dict = {}
_ADMIN_TTL  = 300  # 5 minutos


def es_admin(chat_id: int) -> bool:
    """Verificar si un chat_id es admin. Resultado cacheado 5 minutos."""
    cid = str(chat_id)
    # Owner siempre es admin sin query
    if cid == str(ADMIN_CHAT_ID):
        return True
    ahora = time.time()
    cached = _admin_cache.get(cid)
    if cached and ahora < cached[1]:
        return cached[0]
    # Query a Supabase solo si el cache expiró
    try:
        resp = db.client.table("admins").select("id").eq("chat_id_telegram", cid).eq("activo", True).execute()
        resultado = len(resp.data) > 0
    except Exception:
        resultado = False
    _admin_cache[cid] = (resultado, ahora + _ADMIN_TTL)
    return resultado


def invalidar_cache_admin(chat_id: int) -> None:
    """Llamar cuando se agrega/elimina un admin para forzar revalidación."""
    _admin_cache.pop(str(chat_id), None)


def es_owner(chat_id: int) -> bool:
    return str(chat_id) == str(ADMIN_CHAT_ID)


def cache_resultados_get(chat_id: str) -> dict | None:
    """Obtener cache de búsqueda, None si expiró."""
    entry = _cache_resultados.get(chat_id)
    if not entry:
        return None
    if time.time() > entry['ts'] + _CACHE_TTL:
        del _cache_resultados[chat_id]
        return None
    return entry['data']


def cache_resultados_set(chat_id: str, data: dict) -> None:
    """Guardar resultado en cache con timestamp."""
    # Limpiar entradas viejas si hay demasiadas (> 500)
    if len(_cache_resultados) > 500:
        ahora = time.time()
        expirados = [k for k, v in _cache_resultados.items() if ahora > v['ts'] + _CACHE_TTL]
        for k in expirados:
            del _cache_resultados[k]
    _cache_resultados[chat_id] = {'data': data, 'ts': time.time()}


def paginar_contactos(contactos: list, pagina: int, por_pagina: int = 10) -> tuple:
    total_paginas = max(1, (len(contactos) + por_pagina - 1) // por_pagina)
    pagina = max(1, min(pagina, total_paginas))
    inicio = (pagina - 1) * por_pagina
    fin    = inicio + por_pagina
    return contactos[inicio:fin], pagina, total_paginas
