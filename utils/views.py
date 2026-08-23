"""
views.py — Capa de presentación compartida.

Contiene funciones que construyen y envían vistas completas
(texto + teclado + lógica de paginación) sin depender de ningún handler.

Principio: los handlers reciben el evento y delegan aquí.
Esta capa NO conoce a los handlers — solo conoce db, formatters y helpers.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes

from utils.helpers import db, cache_resultados_set
from utils.formatters import formatear_contacto, teclado_contacto, _formato_lista_compacta


# ── Contacto ──────────────────────────────────────────────────────────────────

async def mostrar_contacto(message: Message, contacto: dict, es_admin: bool = False,
                           editar: bool = False) -> None:
    """Muestra la ficha completa de un contacto con sus botones de acción.
    Resuelve info_reportes aquí para que formatear_contacto sea puro (sin BD)."""
    info_reportes = db.get_info_reportes(contacto['id'])
    texto  = formatear_contacto(contacto, info_reportes=info_reportes, mostrar_id=es_admin)
    markup = teclado_contacto(contacto, es_admin=es_admin)
    if editar:
        await message.edit_text(texto, parse_mode="MarkdownV2", reply_markup=markup)
    else:
        await message.reply_text(texto, parse_mode="MarkdownV2", reply_markup=markup)


# ── Pendientes ────────────────────────────────────────────────────────────────

async def mostrar_pendientes(message: Message, context: ContextTypes.DEFAULT_TYPE,
                             user_id: int, pagina: int = 0,
                             editar: bool = False) -> None:
    """Lista compacta de contactos pendientes con botones de aprobación."""
    contactos = db.get_contactos_pendientes()

    if not contactos:
        txt = "✅ No hay contactos pendientes."
        await (message.edit_text(txt) if editar else message.reply_text(txt))
        return

    POR_PAG = 5
    total   = len(contactos)
    pagina  = max(0, min(pagina, (total - 1) // POR_PAG))
    inicio  = pagina * POR_PAG
    lote    = contactos[inicio:inicio + POR_PAG]

    cache_resultados_set(str(user_id) + '_pend', {'contactos': contactos, 'filtro': None})
    context.user_data['pend_pagina'] = pagina

    texto = f"⏳ *Pendientes ({inicio+1}–{min(inicio+POR_PAG, total)} de {total})*\n\n"
    botones = []

    for c in lote:
        nombre = f"{c['nombre']} {c['apellido']}"
        prov   = c.get('provincia') or ''
        mun    = c.get('municipio') or ''
        ubi    = f" — {mun}, {prov}" if mun else (f" — {prov}" if prov else "")
        texto += f"👤 *{nombre}*\n📱 `{c['telefono']}`{ubi}\n\n"
        cid8   = c['id'][:8]
        botones.append([
            InlineKeyboardButton(f"✅ {c['telefono']}", callback_data=f"aprobar_{cid8}"),
            InlineKeyboardButton("❌",                  callback_data=f"rechazar_{cid8}"),
            InlineKeyboardButton("🗑",                  callback_data=f"confirmar_del_{cid8}"),
        ])

    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"pend_pg_{pagina-1}"))
    if inicio + POR_PAG < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"pend_pg_{pagina+1}"))
    if nav:
        botones.append(nav)

    markup = InlineKeyboardMarkup(botones)
    if editar:
        await message.edit_text(texto, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)


# ── Reportes ──────────────────────────────────────────────────────────────────

async def mostrar_reportes(message: Message, editar: bool = False) -> None:
    """Lista de reportes pendientes con botones de gestión."""
    lista = db.get_reportes_pendientes()

    if not lista:
        txt = "✅ No hay reportes pendientes."
        await (message.edit_text(txt) if editar else message.reply_text(txt))
        return

    texto   = f"🚨 *Reportes pendientes ({len(lista)}):*\n\n"
    botones = []

    for r in lista[:10]:
        contacto = r.get("contactos") or {}
        nombre   = f"{contacto.get('nombre','?')} {contacto.get('apellido','')}"
        desc     = r.get('descripcion') or ''
        texto += (
            f"👤 *{nombre}* — `{contacto.get('telefono','')}`\n"
            f"⚠️ {r['motivo']}"
            + (f": _{desc[:50]}_" if desc else "")
            + "\n\n"
        )
        cid8 = r['id'][:8]
        botones.append([
            InlineKeyboardButton("✅ Verificar",    callback_data=f"verificar_rep_{cid8}"),
            InlineKeyboardButton("🗑 Desestimar",   callback_data=f"desestimar_rep_{cid8}"),
        ])

    markup = InlineKeyboardMarkup(botones) if botones else None
    if editar:
        await message.edit_text(texto, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)


# ── Búsqueda ──────────────────────────────────────────────────────────────────

async def mostrar_ayuda(message, user_id: int, editar: bool = False) -> None:
    """Vista de ayuda — muestra sección admin si el usuario es admin."""
    from utils.helpers import es_admin as _es_admin

    mensaje = (
        "📖 *Guía de uso*\n\n"
        "*Formas de buscar:*\n\n"
        "> 1\\. Por número: `55551234`\n"
        "> 2\\. Por nombre: `Juan Pérez`\n"
        "> 3\\. Varios a la vez: `55551234 56789012`\n\n"
        "*Notas:*\n"
        "• No importan mayúsculas ni minúsculas\n"
        "• Los espacios en los números se ignoran\n\n"
        "*Para agregar un contacto:*\n"
        "> Toca ➕ Agregar contacto o escribe /agregar\n\n"
        "*Para reportar un número sospechoso:*\n"
        "> Busca el número y toca ⚠️ Reportar\n"
    )

    if _es_admin(user_id):
        mensaje += (
            "\n*Comandos admin:*\n"
            "> /pendientes — aprobar contactos nuevos\n"
            "> /reportes — gestionar reportes\n"
            "> /estadisticas — ver estadísticas\n"
            "> /exportar csv — exportar base de datos\n"
            "> /avales — avales pendientes\n"
            "> /reclamos — reclamos pendientes\n"
            "> /banear — banear reportador\n"
        )

    if editar:
        await message.edit_text(mensaje, parse_mode="MarkdownV2")
    else:
        await message.reply_text(mensaje, parse_mode="MarkdownV2")


async def mostrar_lista_busqueda(message: Message, contactos: list, query_texto: str,
                                  user_id: str, pagina: int = 1,
                                  editar: bool = False) -> None:
    """Lista paginada de resultados de búsqueda."""
    cache_resultados_set(user_id, {'contactos': contactos, 'query': query_texto})
    total      = len(contactos)
    total_pags = max(1, (total + 9) // 10)
    inicio     = (pagina - 1) * 10
    items      = contactos[inicio:inicio + 10]
    texto, markup = _formato_lista_compacta(items, inicio + 1, total, pagina, total_pags, query_texto)
    if editar:
        await message.edit_text(texto, parse_mode="MarkdownV2", reply_markup=markup)
    else:
        await message.reply_text(texto, parse_mode="MarkdownV2", reply_markup=markup)
