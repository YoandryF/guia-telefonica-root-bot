"""
Callback query handler — handles all inline button clicks.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import db, es_admin, _mostrar_lista, cache_resultados_get, cache_resultados_set
from utils.formatters import _formato_lista_compacta, formatear_contacto, teclado_contacto

logger = logging.getLogger(__name__)


async def _mostrar_pendientes(message, context, user_id: int, editar: bool = False):
    """Muestra pendientes directamente sobre un mensaje — usado desde botón y comando."""
    contactos = db.get_contactos_pendientes()
    if not contactos:
        txt = "✅ No hay contactos pendientes."
        if editar:
            await message.edit_text(txt)
        else:
            await message.reply_text(txt)
        return

    total   = len(contactos)
    por_pag = 5
    pagina  = context.user_data.get('pend_pagina', 0)
    inicio  = pagina * por_pag
    lote    = contactos[inicio:inicio + por_pag]

    cache_resultados_set(str(user_id) + '_pend', {'contactos': contactos, 'filtro': None})

    texto = f"⏳ *Pendientes ({inicio+1}–{min(inicio+por_pag, total)} de {total})*\n\n"
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
            InlineKeyboardButton("❌", callback_data=f"rechazar_{cid8}"),
            InlineKeyboardButton("🗑", callback_data=f"confirmar_del_{cid8}"),
        ])
    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"pend_pg_{pagina-1}"))
    if inicio + por_pag < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"pend_pg_{pagina+1}"))
    if nav:
        botones.append(nav)

    markup = InlineKeyboardMarkup(botones)
    if editar:
        await message.edit_text(texto, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)


async def _mostrar_reportes(message, context, editar: bool = False):
    """Muestra reportes pendientes directamente — usado desde botón y comando."""
    lista = db.get_reportes_pendientes()
    if not lista:
        txt = "✅ No hay reportes pendientes."
        if editar:
            await message.edit_text(txt)
        else:
            await message.reply_text(txt)
        return

    texto = f"🚨 *Reportes pendientes ({len(lista)}):*\n\n"
    botones = []
    for r in lista[:10]:
        contacto = r.get("contactos", {})
        nombre   = f"{contacto.get('nombre', '')} {contacto.get('apellido', '')}"
        texto += (
            f"👤 {nombre} — `{contacto.get('telefono', '')}`\n"
            f"⚠️ {r['motivo']}"
            + (f" — {r.get('descripcion','')[:40]}" if r.get('descripcion') else "")
            + f"\n\n"
        )
        cid8 = r['id'][:8]
        botones.append([
            InlineKeyboardButton(f"✅ Aprobar — {contacto.get('telefono','')}", callback_data=f"aprobar_rep_{cid8}"),
            InlineKeyboardButton("🗑 Desestimar", callback_data=f"desestimar_rep_{cid8}"),
        ])

    markup = InlineKeyboardMarkup(botones) if botones else None
    if editar:
        await message.edit_text(texto, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejar clicks en botones inline"""
    query = update.callback_query
    await query.answer()

    data = query.data
    admin = es_admin(query.from_user.id)

    # Callbacks PÚBLICOS (sin guard de admin)
    if data.startswith("pg_"):
        partes = data.split("_", 2)
        pagina = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 1
        chat_id = str(query.from_user.id)
        cache = cache_resultados_get(chat_id)

        if cache and cache.get('tipo') == 'listar':
            # Paginación real desde Supabase — total ya en cache, no hace segunda query
            por_pagina = 10
            total = cache.get('total', 0)
            offset = (pagina - 1) * por_pagina
            contactos, _ = db.get_contactos_aprobados(limite=por_pagina, offset=offset)
            total_pags = max(1, (total + por_pagina - 1) // por_pagina)
            texto, markup = _formato_lista_compacta(contactos, offset + 1, total, pagina, total_pags, '')
            await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=markup)
        elif cache and 'contactos' in cache:
            # Búsqueda — cache local
            await _mostrar_lista(query, context, cache['contactos'], pagina, query_texto=cache.get('query', ''), editar=True)
        else:
            await query.answer("⚠️ Sesión expirada. Busca de nuevo.", show_alert=True)
        return

    elif data.startswith("ln_"):
        # Paginación lista negra
        pagina = int(data.replace("ln_", "")) if data.replace("ln_", "").isdigit() else 1
        chat_id = str(query.from_user.id)
        cache = cache_resultados_get(chat_id)
        total = cache.get('total', 0) if cache and cache.get('tipo') == 'listanegra' else db.contar_contactos_con_reportes()
        por_pagina = 10
        offset = (pagina - 1) * por_pagina
        total_pags = max(1, (total + por_pagina - 1) // por_pagina)
        reportados = db.get_contactos_con_reportes(limite=por_pagina, offset=offset)
        inicio_num = offset + 1

        texto = f"⚠️ *Lista Negra — {total} contactos*\n\n"
        for i, c in enumerate(reportados, inicio_num):
            nombre = f"{c['nombre']} {c['apellido']}"
            if len(nombre) > 22:
                nombre = nombre[:20] + "…"
            estado = "🔴 Verificado" if c.get('verificado') else "🟡 Reportado"
            texto += f"*{i}.* {nombre.upper()}\n   📱 `{c['telefono']}` — {estado}\n\n"
        texto += f"📊 Mostrando {inicio_num}-{inicio_num + len(reportados) - 1} de *{total}*\n"
        texto += "_Escribe el número para ver detalles completos_"

        botones = []
        fila = []
        if pagina > 1:
            fila.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"ln_{pagina - 1}"))
        if pagina < total_pags:
            fila.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"ln_{pagina + 1}"))
        if fila:
            botones.append(fila)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones) if botones else None)
        return

    elif data == "cmd_listar":
        # Eliminado — la lista ya no está disponible como función pública
        await query.answer("Escribe directamente para buscar.", show_alert=False)
        return

    elif data == "cmd_agregar":
        await query.edit_message_text(
            "✏️ *Registrar un nuevo contacto*\n\n"
            "Escribe /agregar para iniciar paso a paso\n\n"
            "El proceso te pedirá:\n"
            "1. Nombre\n"
            "2. Apellido\n"
            "3. Teléfono\n"
            "4. Provincia\n"
            "5. Municipio\n\n"
            "_El contacto quedará pendiente de aprobación._",
            parse_mode="Markdown",
        )
        return

    elif data == "cmd_ayuda":
        await query.edit_message_text(
            "📖 *Cómo usar la Guía Telefónica*\n\n"
            "Escribe directamente en el chat:\n"
            "• Un *número de teléfono* para buscarlo\n"
            "• Un *nombre* para buscar personas\n\n"
            "Botones disponibles al ver un contacto:\n"
            "• 📲 Abrir en Telegram o WhatsApp\n"
            "• ⚠️ Reportar si es sospechoso\n"
            "• 👍 Avalar si es confiable\n\n"
            "➕ Usa /agregar para registrar un contacto nuevo.",
            parse_mode="Markdown",
        )
        return

    elif data == "cmd_misreportes":
        chat_id_str = str(query.from_user.id)
        try:
            resp = db.client.table("reportes").select(
                "id, motivo, fecha_reporte, contactos(nombre, apellido, telefono)"
            ).eq("reportado_por", chat_id_str).order("fecha_reporte", desc=True).limit(10).execute()
            if not resp.data:
                await query.edit_message_text("📭 No has enviado reportes aún.")
                return
            texto = f"📌 *Tus reportes ({len(resp.data)}):*\n\n"
            for r in resp.data:
                c     = r.get('contactos') or {}
                fecha = (r.get('fecha_reporte') or '')[:10]
                texto += f"⚠️ {c.get('nombre','')} {c.get('apellido','')} — `{c.get('telefono','')}`\n"
                texto += f"   Motivo: {r['motivo']} — {fecha}\n\n"
            await query.edit_message_text(texto, parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
        return

    elif data in ("cmd_pendientes", "cmd_reportes"):
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        if data == "cmd_pendientes":
            await _mostrar_pendientes(query.message, context, query.from_user.id, editar=True)
        else:
            await _mostrar_reportes(query.message, context, editar=True)
        return

    # Ver detalle de un contacto desde la lista (botón "Ver")
    elif data.startswith("ver_"):
        cid8 = data.replace("ver_", "")
        contacto = db.buscar_por_id_o_telefono(cid8)
        if not contacto:
            await query.answer("❌ Contacto no encontrado", show_alert=True)
            return
        detalle = formatear_contacto(contacto, mostrar_id=admin, db=db)
        markup  = teclado_contacto(contacto, es_admin=admin)
        await query.edit_message_text(detalle, parse_mode="MarkdownV2", reply_markup=markup)
        return

    # Reportar desde botón en detalle de contacto
    elif data.startswith("reportar_"):
        cid8 = data.replace("reportar_", "")
        contacto = db.buscar_por_id_o_telefono(cid8)
        if not contacto:
            await query.answer("❌ No encontrado", show_alert=True)
            return
        context.user_data['reportar_id'] = contacto['id']
        await query.edit_message_text(
            f"⚠️ *Reportar contacto:* {contacto['nombre']} {contacto['apellido']}\n"
            f"📱 `{contacto['telefono']}`\n\n"
            "Escribe el motivo del reporte:",
            parse_mode="Markdown",
        )
        return

    # Avalar desde botón en detalle de contacto
    elif data.startswith("avalar_"):
        cid8 = data.replace("avalar_", "")
        contacto = db.buscar_por_id_o_telefono(cid8)
        if not contacto:
            await query.answer("❌ No encontrado", show_alert=True)
            return
        try:
            db.client.table("avales").insert({
                "contacto_id": contacto["id"],
                "avalado_por": str(query.from_user.id),
            }).execute()
            await query.answer("👍 Aval enviado — pendiente de revisión", show_alert=True)
        except Exception as e:
            if "duplicate" in str(e).lower():
                await query.answer("⚠️ Ya avalaste este contacto", show_alert=True)
            else:
                await query.answer(f"❌ Error: {e}", show_alert=True)
        return

    elif data == "cancelar":
        await query.edit_message_text("❌ Operación cancelada.")
        return

    elif data.startswith("reclamo_"):
        if not admin:
            await query.edit_message_text("🔒 Solo el administrador.")
            return
        partes = data.split("_")
        accion = partes[1]  # aceptar o rechazar
        reclamo_id = partes[2]
        try:
            estado = "aceptado" if accion == "aceptar" else "rechazado"
            db.client.table("reclamos").update({"estado": estado}).ilike("id", f"{reclamo_id}%").execute()
            await query.edit_message_text(f"{'✅ Reclamo aceptado' if accion == 'aceptar' else '❌ Reclamo rechazado'}")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
        return

    # A partir de aquí: solo admins
    if not admin:
        await query.edit_message_text("🔒 Solo el administrador.")
        return

    if data.startswith("aprobar_"):
        contacto_id = data.replace("aprobar_", "")
        resultado = db.aprobar_contacto(contacto_id, aprobado_por=str(query.from_user.id))
        if resultado.get("error"):
            await query.edit_message_text(f"❌ Error: {resultado['error']}")
        else:
            contacto = resultado.get("data", {})
            await query.edit_message_text(f"✅ *Aprobado:* {contacto.get('nombre', '')} {contacto.get('apellido', '')}", parse_mode="Markdown")
            # Notificar al creador
            if contacto.get("creado_por") and contacto.get("creado_desde") == "telegram":
                try:
                    await query.bot.send_message(chat_id=contacto["creado_por"], text=f"✅ Tu contacto *{contacto['nombre']} {contacto['apellido']}* fue aprobado!", parse_mode="Markdown")
                except Exception:
                    pass

    elif data.startswith("rechazar_"):
        contacto_id = data.replace("rechazar_", "")
        context.user_data['rechazar_id'] = contacto_id
        await query.edit_message_text("❌ Escribe el motivo de rechazo (envía un mensaje):")

    elif data.startswith("eliminar_"):
        contacto_id = data.replace("eliminar_", "")
        contacto = db.buscar_por_id_o_telefono(contacto_id)
        if contacto:
            db.client.table("contactos").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", contacto["id"]).execute()
            await query.edit_message_text(f"🗑 *Eliminado:* {contacto['nombre']} {contacto['apellido']}", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ No encontrado.")

    elif data.startswith("confirmar_del_"):
        contacto_id = data.replace("confirmar_del_", "")
        contacto = db.buscar_por_id_o_telefono(contacto_id)
        if contacto:
            db.client.table("contactos").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", contacto["id"]).execute()
            await query.edit_message_text(f"🗑 *Eliminado:* {contacto['nombre']} {contacto['apellido']}", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ No encontrado.")

    elif data.startswith("cfg_edit_"):
        clave = data.replace("cfg_edit_", "")
        context.user_data['cfg_edit_clave'] = clave
        await query.edit_message_text(f"✏️ Escribe el nuevo valor para `{clave}`:", parse_mode="Markdown")

    elif data.startswith("pend_pg_"):
        # Paginación de pendientes — navegar a página específica
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        nueva_pag = int(data.replace("pend_pg_", ""))
        context.user_data['pend_pagina'] = nueva_pag
        # Reconstruir la lista desde cache
        from utils.helpers import cache_resultados_get
        cached = cache_resultados_get(str(query.from_user.id) + '_pend')
        if not cached:
            await query.answer("⚠️ Sesión expirada. Usa /pendientes de nuevo.", show_alert=True)
            return
        contactos = cached['contactos']
        filtro    = cached.get('filtro')
        total     = len(contactos)
        por_pag   = 5
        pagina    = max(0, min(nueva_pag, (total-1)//por_pag))
        inicio    = pagina * por_pag
        lote      = contactos[inicio:inicio + por_pag]

        texto = f"⏳ *Pendientes ({inicio+1}–{min(inicio+por_pag, total)} de {total})*\n"
        if filtro:
            texto += f"_Filtro: \"{filtro}\"_\n"
        texto += "\n"
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
            nav.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"pend_pg_{pagina-1}"))
        if inicio + por_pag < total:
            nav.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"pend_pg_{pagina+1}"))
        if nav:
            botones.append(nav)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones))
        return

    elif data in ("pend_prev", "pend_next"):
        # Legacy — ya no se usa, ignorar silenciosamente
        await query.answer("Usa /pendientes para navegar.", show_alert=False)
        return

    elif data.startswith("aval_aprobar_") or data.startswith("aval_rechazar_"):
        if not admin:
            await query.edit_message_text("🔒 Solo el administrador.")
            return
        accion = "aprobado" if data.startswith("aval_aprobar_") else "rechazado"
        aval_id_prefix = data.replace("aval_aprobar_", "").replace("aval_rechazar_", "")
        try:
            # Buscar el UUID completo por prefijo
            resp = db.client.table("avales").select("id").ilike("id", f"{aval_id_prefix}%").limit(1).execute()
            if not resp.data:
                await query.edit_message_text("❌ Aval no encontrado.")
                return
            aval_uuid = resp.data[0]["id"]
            # Usar RPC SECURITY DEFINER para bypasear RLS
            result = db.client.rpc("resolver_aval", {
                "p_aval_id":      aval_uuid,
                "p_estado":       accion,
                "p_revisado_por": str(query.from_user.id),
            }).execute()
            ok = result.data.get("ok") if result.data else False
            emoji = "✅" if accion == "aprobado" else "❌"
            if ok:
                await query.edit_message_text(f"{emoji} Aval {accion}.")
            else:
                error = result.data.get("error", "desconocido") if result.data else "sin respuesta"
                await query.edit_message_text(f"❌ Error: {error}")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
