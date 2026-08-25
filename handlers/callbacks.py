"""
Callback query handler — handles all inline button clicks.

Principio: este módulo solo enruta callbacks a la capa de vistas (views.py).
Sin lógica de negocio. Sin imports locales dentro de funciones.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import (
    db, es_admin, es_owner,
    cache_resultados_get, cache_resultados_set,
)
from utils.formatters import _formato_lista_compacta
from utils.views import (
    mostrar_pendientes, mostrar_reportes, mostrar_contacto,
    mostrar_start, mostrar_ayuda, mostrar_estadisticas,
    mostrar_admins, mostrar_eliminar_admin, mostrar_confirmar_eliminar_admin,
    mostrar_mis_reportes, mostrar_lista_busqueda, mostrar_listanegra,
    mostrar_config, mostrar_editar_config,
)

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enrutar clicks de botones inline a la vista correspondiente."""
    query = update.callback_query
    await query.answer()

    data  = query.data
    admin = es_admin(query.from_user.id)
    owner = es_owner(query.from_user.id)

    # ── Navegación: Inicio ────────────────────────────────────────────────────
    if data == "cmd_inicio":
        nombre = query.from_user.first_name or "amigo"
        await mostrar_start(query.message, query.from_user.id, nombre, editar=True)
        return

    # ── Búsqueda paginada (pg_) ────────────────────────────────────────────────
    if data.startswith("pg_"):
        partes  = data.split("_", 2)
        pagina  = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 1
        chat_id = str(query.from_user.id)
        cache   = cache_resultados_get(chat_id)

        if not cache:
            await query.answer("⚠️ Sesión expirada. Busca de nuevo.", show_alert=True)
            return

        contactos  = cache.get('contactos') or []
        query_text = cache.get('query', '')

        if cache.get('tipo') == 'listar':
            por_pagina    = 10
            total         = cache.get('total', 0)
            offset        = (pagina - 1) * por_pagina
            contactos, _  = db.get_contactos_aprobados(limite=por_pagina, offset=offset)
            cache_resultados_set(chat_id, {**cache, 'contactos': contactos})

        await mostrar_lista_busqueda(
            query.message, contactos, query_text, chat_id,
            pagina=pagina, editar=True,
        )
        return

    # ── Lista negra paginada (ln_ y cmd_listanegra) ────────────────────────────
    if data == "cmd_listanegra":
        await mostrar_listanegra(query.message, pagina=1, editar=True)
        return

    if data.startswith("ln_"):
        pagina = int(data.replace("ln_", "")) if data.replace("ln_", "").isdigit() else 1
        await mostrar_listanegra(query.message, pagina=pagina, editar=True)
        return

    # ── Vistas del menú principal ──────────────────────────────────────────────
    if data == "cmd_ayuda":
        await mostrar_ayuda(query.message, query.from_user.id, editar=True)
        return

    if data == "cmd_misreportes":
        await mostrar_mis_reportes(query.message, str(query.from_user.id), editar=True)
        return

    if data == "cmd_agregar":
        # Manejado por get_agregar_handler en conversations.py
        return

    if data == "noop":
        return  # Botón decorativo — sin acción

    # ── Vistas admin ───────────────────────────────────────────────────────────
    if data in ("cmd_pendientes", "cmd_reportes"):
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        if data == "cmd_pendientes":
            pagina = context.user_data.get('pend_pagina', 0)
            await mostrar_pendientes(query.message, context, query.from_user.id,
                                     pagina=pagina, editar=True)
        else:
            await mostrar_reportes(query.message, editar=True)
        return

    if data == "cmd_estadisticas":
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        await mostrar_estadisticas(query.message, editar=True)
        return

    if data == "cmd_exportar":
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        await query.edit_message_text(
            "📤 *Exportar base de datos*\n\n"
            "Usa:\n• `/exportar csv` — formato CSV\n• `/exportar json` — formato JSON",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Inicio", callback_data="cmd_inicio")
            ]]),
        )
        return

    # ── Vistas owner ───────────────────────────────────────────────────────────
    if data == "cmd_admins":
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        await mostrar_admins(query.message, editar=True)
        return

    if data == "cmd_admin_registrar":
        # Manejado por get_registrar_admin_handler en conversations.py
        # Este branch no debería ejecutarse, pero por seguridad
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
        return

    if data == "cmd_admin_eliminar":
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        await mostrar_eliminar_admin(query.message, editar=True)
        return

    if data.startswith("del_admin_"):
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        email = data[10:]  # quitar "del_admin_"
        await mostrar_confirmar_eliminar_admin(query.message, email, editar=True)
        return

    if data.startswith("confirmar_del_admin_"):
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        email     = data[20:]  # quitar "confirmar_del_admin_"
        resultado = db.desactivar_admin(email)
        if resultado.get("error"):
            await query.edit_message_text(
                f"❌ Error: {resultado['error']}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver", callback_data="cmd_admins")
                ]]),
            )
        else:
            await query.edit_message_text(
                f"✅ Admin <code>{email}</code> desactivado.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Ver admins", callback_data="cmd_admins"),
                    InlineKeyboardButton("🏠 Inicio",     callback_data="cmd_inicio"),
                ]]),
            )
        return

    if data == "cmd_config":
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        await mostrar_config(query.message, pagina=0, editar=True)
        return

    if data.startswith("cfg_pg_"):
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        pagina = int(data.replace("cfg_pg_", ""))
        await mostrar_config(query.message, pagina=pagina, editar=True)
        return

    if data.startswith("cfg_sel_"):
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        partes = data.split("_")   # cfg_sel_{pagina}_{indice}
        pagina = int(partes[2])
        indice = int(partes[3])
        await mostrar_config(query.message, pagina=pagina, seleccion=indice, editar=True)
        return

    # ── Ver detalle de contacto ────────────────────────────────────────────────
    if data.startswith("ver_"):
        cid8     = data[4:]
        contacto = db.buscar_por_id_o_telefono(cid8)
        if not contacto:
            await query.answer("❌ Contacto no encontrado", show_alert=True)
            return
        await mostrar_contacto(query.message, contacto, es_admin=admin, editar=True)
        return

    # ── Acciones sobre contactos ───────────────────────────────────────────────
    if data.startswith("reportar_"):
        cid8     = data[9:]
        contacto = db.buscar_por_id_o_telefono(cid8)
        if not contacto:
            await query.answer("❌ No encontrado", show_alert=True)
            return
        context.user_data['reportar_id'] = contacto['id']
        await query.edit_message_text(
            f"⚠️ *Reportar:* {contacto['nombre']} {contacto['apellido']}\n"
            f"📱 `{contacto['telefono']}`\n\nEscribe el motivo:",
            parse_mode="Markdown",
        )
        return

    if data.startswith("avalar_"):
        cid8     = data[7:]
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
            msg = "⚠️ Ya avalaste este contacto" if "duplicate" in str(e).lower() else f"❌ Error: {e}"
            await query.answer(msg, show_alert=True)
        return

    if data == "cancelar":
        await query.edit_message_text("❌ Operación cancelada.")
        return

    if data.startswith("reclamo_"):
        if not admin:
            await query.edit_message_text("🔒 Solo el administrador.")
            return
        partes     = data.split("_")
        accion     = partes[1]
        reclamo_id = partes[2]
        try:
            estado = "aceptado" if accion == "aceptar" else "rechazado"
            db.client.table("reclamos").update({"estado": estado}).ilike("id", f"{reclamo_id}%").execute()
            await query.edit_message_text(f"{'✅ Reclamo aceptado' if accion == 'aceptar' else '❌ Reclamo rechazado'}")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
        return

    # ── Acciones admin sobre contactos ─────────────────────────────────────────
    if not admin:
        await query.edit_message_text("🔒 Solo el administrador.")
        return

    if data.startswith("aprobar_"):
        cid8      = data[8:]
        resultado = db.aprobar_contacto(cid8, aprobado_por=str(query.from_user.id))
        if resultado.get("error"):
            await query.edit_message_text(f"❌ Error: {resultado['error']}")
        else:
            c = resultado.get("data", {})
            await query.edit_message_text(
                f"✅ *Aprobado:* {c.get('nombre','')} {c.get('apellido','')}",
                parse_mode="Markdown",
            )
            if c.get("creado_por") and c.get("creado_desde") == "telegram":
                try:
                    await query.bot.send_message(
                        chat_id=c["creado_por"],
                        text=f"✅ Tu contacto *{c['nombre']} {c['apellido']}* fue aprobado!",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
        return

    if data.startswith("rechazar_"):
        context.user_data['rechazar_id'] = data[9:]
        await query.edit_message_text("❌ Escribe el motivo de rechazo:")
        return

    if data.startswith(("eliminar_", "confirmar_del_")):
        prefijo  = "eliminar_" if data.startswith("eliminar_") else "confirmar_del_"
        cid8     = data[len(prefijo):]
        contacto = db.buscar_por_id_o_telefono(cid8)
        if contacto:
            db.client.table("contactos").update(
                {"deleted_at": datetime.utcnow().isoformat()}
            ).eq("id", contacto["id"]).execute()
            await query.edit_message_text(
                f"🗑 *Eliminado:* {contacto['nombre']} {contacto['apellido']}",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("❌ No encontrado.")
        return

    if data.startswith("cfg_edit_"):
        clave = data[9:]
        if not owner:
            await query.answer("🔒 Solo el owner puede editar configuración", show_alert=True)
            return
        pagina = context.user_data.get('pend_pagina', 0)
        # Guardar estado para que handle_texto_admin sepa qué editar
        context.user_data['cfg_edit_clave']  = clave
        context.user_data['cfg_edit_pagina'] = pagina
        await mostrar_editar_config(query.message, clave, pagina=pagina, editar=True)
        return

    if data.startswith("pend_pg_"):
        nueva_pag = int(data[8:])
        await mostrar_pendientes(
            query.message, context, query.from_user.id,
            pagina=nueva_pag, editar=True,
        )
        return

    if data.startswith(("aval_aprobar_", "aval_rechazar_")):
        accion         = "aprobado" if data.startswith("aval_aprobar_") else "rechazado"
        aval_id_prefix = data.replace("aval_aprobar_", "").replace("aval_rechazar_", "")
        try:
            resp = db.client.table("avales").select("id").ilike("id", f"{aval_id_prefix}%").limit(1).execute()
            if not resp.data:
                await query.edit_message_text("❌ Aval no encontrado.")
                return
            result = db.client.rpc("resolver_aval", {
                "p_aval_id":      resp.data[0]["id"],
                "p_estado":       accion,
                "p_revisado_por": str(query.from_user.id),
            }).execute()
            ok    = result.data.get("ok") if result.data else False
            emoji = "✅" if accion == "aprobado" else "❌"
            if ok:
                await query.edit_message_text(f"{emoji} Aval {accion}.")
            else:
                error = result.data.get("error", "desconocido") if result.data else "sin respuesta"
                await query.edit_message_text(f"❌ Error: {error}")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
        return

    if data.startswith("desestimar_rep_") or data.startswith("verificar_rep_"):
        rid8   = data.replace("desestimar_rep_", "").replace("verificar_rep_", "")
        accion = "resuelto" if data.startswith("desestimar_") else "revisado"
        try:
            db.client.table("reportes").update({"estado": accion}).ilike("id", f"{rid8}%").execute()
            label = "Desestimado" if accion == "resuelto" else "Verificado"
            await query.edit_message_text(f"✅ Reporte {label}.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
        return
