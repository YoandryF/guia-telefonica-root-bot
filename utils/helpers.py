"""
Shared state and helper functions for the bot.
"""

import os
import logging
from dotenv import load_dotenv
from supabase_service import SupabaseService
from utils.formatters import _formato_lista_compacta

load_dotenv()

# Logging
logger = logging.getLogger(__name__)

# Shared configuration
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

# Shared Supabase service instance
db = SupabaseService()

# Cache simple de resultados de búsqueda por chat_id
_cache_resultados: dict = {}


def es_admin(chat_id: int) -> bool:
    """Verificar si un chat_id es administrador o owner"""
    if str(chat_id) == str(ADMIN_CHAT_ID):
        return True
    try:
        response = db.client.table("admins").select("id").eq("chat_id_telegram", str(chat_id)).eq("activo", True).execute()
        return len(response.data) > 0
    except Exception:
        return False


def es_owner(chat_id: int) -> bool:
    """Verificar si es el owner (solo uno)"""
    return str(chat_id) == str(ADMIN_CHAT_ID)


def paginar_contactos(contactos: list, pagina: int, por_pagina: int = 10) -> tuple:
    """Paginar lista de contactos"""
    total_paginas = max(1, (len(contactos) + por_pagina - 1) // por_pagina)
    pagina = max(1, min(pagina, total_paginas))
    inicio = (pagina - 1) * por_pagina
    fin = inicio + por_pagina
    return contactos[inicio:fin], pagina, total_paginas


async def _mostrar_lista(update_or_query, context, contactos: list, pagina: int, query_texto: str = "", editar: bool = False):
    """Mostrar lista paginada. Puede enviar nuevo mensaje o editar existente."""
    por_pagina = 10
    total = len(contactos)
    total_pags = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = max(1, min(pagina, total_pags))
    inicio = (pagina - 1) * por_pagina
    items = contactos[inicio:inicio + por_pagina]
    inicio_num = inicio + 1

    texto, markup = _formato_lista_compacta(items, inicio_num, total, pagina, total_pags, query_texto)

    if editar:
        await update_or_query.edit_message_text(texto, parse_mode="Markdown", reply_markup=markup)
    else:
        msg = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
        await msg.reply_text(texto, parse_mode="Markdown", reply_markup=markup)
