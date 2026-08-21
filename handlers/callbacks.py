"""
Callback query handler — handles all inline button clicks.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import db, es_admin, _cache_resultados, _mostrar_lista
from utils.formatters import _formato_lista_compacta, formatear_contacto, teclado_contacto

logger = logging.getLogger(__name__)


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
        cache = _cache_resultados.get(chat_id)

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
        cache = _cache_resultados.get(chat_id)
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
        por_pagina = 10
        contactos, total = db.get_contactos_aprobados(limite=por_pagina, offset=0)
        if not contactos:
            await query.edit_message_text("📭 No hay contactos aprobados aún.")
            return
        chat_id = str(query.from_user.id)
        _cache_resultados[chat_id] = {'tipo': 'listar', 'total': total, 'por_pagina': por_pagina}
        total_pags = max(1, (total + por_pagina - 1) // por_pagina)
        texto, markup = _formato_lista_compacta(contactos, 1, total, 1, total_pags, '')
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=markup)
        return

    elif data == "cmd_agregar":
        await query.edit_message_text(
            "✏️ Para registrar un contacto usa:\n\n"
            "`/agregar Nombre, Apellido, Teléfono`\n\n"
            "Ejemplo: `/agregar Juan, Pérez, 55551234`",
            parse_mode="Markdown",
        )
        return

    elif data == "cmd_categorias":
        cats = db.get_categorias()
        if not cats:
            await query.edit_message_text("📂 No hay categorías configuradas.")
            return
        texto = "📂 *Categorías disponibles:*\n\n"
        for cat in cats:
            texto += f"  {cat.get('icono', '📋')} {cat['nombre']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown")
        return

    elif data == "cmd_miscontactos":
        chat_id = str(query.from_user.id)
        contactos = db.get_contactos_por_creador(chat_id)
        if not contactos:
            await query.edit_message_text("📭 No has registrado contactos aún.\n\nUsa /agregar para registrar uno.")
            return
        texto = f"📌 *Tus contactos ({len(contactos)}):*\n\n"
        for c in contactos:
            emoji = {"aprobado": "✅", "pendiente": "⏳", "rechazado": "❌"}.get(c["estado"], "❓")
            texto += f"{emoji} *{c['nombre']} {c['apellido']}* — `{c['telefono']}`\n"
        await query.edit_message_text(texto, parse_mode="Markdown")
        return

    elif data == "cmd_ayuda":
        await query.edit_message_text(
            "📖 *Cómo usar la Guía Telefónica:*\n\n"
            "🔍 Escribe el nombre o número directamente\n"
            "📋 /listar — ver todos\n"
            "➕ /agregar — registrar contacto\n"
            "📌 /miscontactos — mis registros\n"
            "⚠️ /reportar — reportar número\n"
            "👍 /avalar — avalar contacto\n"
            "📂 /categorias — ver categorías\n"
            "🚫 /listanegra — contactos reportados\n",
            parse_mode="Markdown",
        )
        return

    elif data in ("cmd_pendientes", "cmd_reportes"):
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        cmd = "pendientes" if data == "cmd_pendientes" else "reportes"
        await query.edit_message_text(f"Usa /{cmd} para ver la lista.")
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
        await query.edit_message_text(detalle, parse_mode="Markdown", reply_markup=markup)
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

    elif data == "pend_prev":
        context.user_data['pend_pagina'] = max(0, context.user_data.get('pend_pagina', 0) - 1)
        await query.edit_message_text(f"⬅️ Usa /pendientes para ver página {context.user_data['pend_pagina']+1}")

    elif data == "pend_next":
        context.user_data['pend_pagina'] = context.user_data.get('pend_pagina', 0) + 1
        await query.edit_message_text(f"➡️ Usa /pendientes para ver página {context.user_data['pend_pagina']+1}")

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
