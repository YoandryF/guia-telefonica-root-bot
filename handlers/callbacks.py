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
    mostrar_config, mostrar_editar_config, mostrar_configurar_canal,
)

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enrutar clicks de botones inline a la vista correspondiente."""
    query = update.callback_query
    data  = query.data
    admin = es_admin(query.from_user.id)
    owner = es_owner(query.from_user.id)

    # answer() silencioso por defecto — quita el spinner del botón sin mostrar toast
    # Las ramas que necesitan feedback lo sobreescriben con su propio answer()
    await query.answer()

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

    if data == "canal_ev_menu":
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        try:
            await mostrar_configurar_canal(query.message, context.bot, editar=True)
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error al cargar canal de evidencias: {e}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Inicio", callback_data="cmd_inicio")
                ]]),
            )
        return

    if data.startswith("canal_ev_sel_"):
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        # Selección directa de un grupo conocido — validar permisos y guardar
        chat_id_sel = data[13:]  # quitar "canal_ev_sel_"
        await query.edit_message_text(
            f"⏳ Verificando permisos en el grupo...",
        )
        try:
            chat = await context.bot.get_chat(chat_id_sel)
            # Enviar mensaje de prueba para verificar permisos reales
            msg_prueba = await context.bot.send_message(
                chat_id = chat_id_sel,
                text    = "🔧 Verificación de permisos — este mensaje se borrará automáticamente.",
            )
            await context.bot.delete_message(chat_id=chat_id_sel, message_id=msg_prueba.message_id)
            # Permisos OK — guardar
            db.set_canal_evidencias(chat_id_sel)
            await mostrar_configurar_canal(query.message, context.bot, editar=True)
        except Exception as e:
            error_str = str(e).lower()
            if "not enough rights" in error_str or "forbidden" in error_str:
                motivo = "El bot no tiene permisos para enviar mensajes."
            elif "not a member" in error_str or "kicked" in error_str:
                motivo = "El bot ya no es miembro de ese grupo."
            else:
                motivo = str(e)
            await query.edit_message_text(
                f"❌ <b>No se pudo vincular</b>\n\n⚠️ {motivo}\n\n"
                f"Verifica los permisos del bot en el grupo e intenta de nuevo.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver", callback_data="canal_ev_menu")
                ]]),
            )
        return

    if data == "canal_ev_vincular":
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        context.user_data['esperando_canal_id'] = True
        await query.edit_message_text(
            "📢 <b>Vincular canal de evidencias</b>\n\n"
            "Escribe el <b>ID o @username</b> del canal:\n\n"
            "<i>Ejemplos: -1001234567890  o  @mi_canal_privado</i>\n\n"
            "⚠️ El bot debe ser admin del canal antes de vincularlo.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancelar", callback_data="canal_ev_cancelar")
            ]]),
        )
        return

    if data == "canal_ev_cancelar":
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        context.user_data.pop('esperando_canal_id', None)
        await mostrar_configurar_canal(query.message, context.bot, editar=True)
        return

    if data == "canal_ev_desvincular":
        if not owner:
            await query.answer("🔒 Solo el owner", show_alert=True)
            return
        db.set_canal_evidencias("")
        await mostrar_configurar_canal(query.message, context.bot, editar=True)
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
        tel_id   = data[9:]
        contacto = db.buscar_por_id_o_telefono(tel_id)
        if not contacto:
            await query.answer("❌ No encontrado", show_alert=True)
            return
        nombre = f"{contacto['nombre']} {contacto['apellido']}"
        # Flujo inline — motivos como botones, sin necesitar texto
        await query.edit_message_text(
            f"⚠️ *Reportar contacto*\n\n"
            f"👤 {nombre}\n"
            f"📱 `{contacto['telefono']}`\n\n"
            f"Selecciona el motivo:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Número incorrecto", callback_data=f"rep_mot_{tel_id}_numero_incorrecto")],
                [InlineKeyboardButton("❌ No existe",          callback_data=f"rep_mot_{tel_id}_no_existe")],
                [InlineKeyboardButton("📢 Spam",               callback_data=f"rep_mot_{tel_id}_spam")],
                [InlineKeyboardButton("🔄 Duplicado",          callback_data=f"rep_mot_{tel_id}_duplicado")],
                [InlineKeyboardButton("⚠️ Estafa / Fraude",   callback_data=f"rep_mot_{tel_id}_otro")],
                [InlineKeyboardButton("🔙 Volver",             callback_data=f"ver_{tel_id}")],
            ]),
        )
        return

    if data.startswith("rep_mot_"):
        # formato: rep_mot_{telefono}_{motivo}
        partes  = data[8:].rsplit("_", 1)
        tel_id  = partes[0]
        motivo  = partes[1] if len(partes) > 1 else "otro"
        contacto = db.buscar_por_id_o_telefono(tel_id)
        if not contacto:
            await query.answer("❌ No encontrado", show_alert=True)
            return
        resultado = db.reportar_contacto(
            contacto_id   = contacto['id'],
            motivo        = motivo,
            descripcion   = None,
            reportado_por = str(query.from_user.id),
        )
        if resultado.get("error"):
            await query.answer(f"❌ {resultado['error']}", show_alert=True)
        else:
            # Notificar al admin
            from utils.helpers import ADMIN_CHAT_ID
            if ADMIN_CHAT_ID:
                try:
                    nombre = f"{contacto['nombre']} {contacto['apellido']}"
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=(
                            f"🚨 *Nuevo reporte*\n\n"
                            f"👤 {nombre} (`{contacto['telefono']}`)\n"
                            f"⚠️ Motivo: {motivo}\n"
                            f"Por: @{query.from_user.username or query.from_user.first_name}"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
            # Volver a la ficha con confirmación
            await query.edit_message_text(
                f"✅ *Reporte enviado*\n\n"
                f"Gracias por informar. El administrador lo revisará pronto.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Ver contacto", callback_data=f"ver_{tel_id}"),
                    InlineKeyboardButton("🏠 Inicio",       callback_data="cmd_inicio"),
                ]]),
            )
        return

    if data.startswith("avalar_"):
        tel_id   = data[7:]
        contacto = db.buscar_por_id_o_telefono(tel_id)
        if not contacto:
            await query.answer("❌ No encontrado", show_alert=True)
            return
        try:
            db.client.table("avales").insert({
                "contacto_id": contacto["id"],
                "avalado_por": str(query.from_user.id),
            }).execute()
            nombre = f"{contacto['nombre']} {contacto['apellido']}"
            await query.edit_message_text(
                f"👍 *Aval enviado*\n\n"
                f"👤 {nombre}\n"
                f"📱 `{contacto['telefono']}`\n\n"
                f"_Pendiente de revisión por el administrador._",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Ver contacto", callback_data=f"ver_{tel_id}"),
                    InlineKeyboardButton("🏠 Inicio",       callback_data="cmd_inicio"),
                ]]),
            )
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
        await query.edit_message_text("⏳ Aprobando contacto...")
        cid8      = data[8:]
        resultado = db.aprobar_contacto(cid8, aprobado_por=str(query.from_user.id))
        if resultado.get("error"):
            await query.edit_message_text(
                f"❌ Error: {resultado['error']}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Ver pendientes", callback_data="cmd_pendientes"),
                    InlineKeyboardButton("🏠 Inicio",         callback_data="cmd_inicio"),
                ]]),
            )
        else:
            c = resultado.get("data", {})
            if c.get("creado_por") and c.get("creado_desde") == "telegram":
                try:
                    await context.bot.send_message(
                        chat_id=c["creado_por"],
                        text=f"✅ Tu contacto *{c['nombre']} {c['apellido']}* fue aprobado!",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
            # Volver a pendientes actualizados
            await mostrar_pendientes(query.message, context, query.from_user.id,
                                     pagina=0, editar=True)
        return

    if data.startswith("rechazar_"):
        context.user_data['rechazar_id'] = data[9:]
        await query.edit_message_text(
            "❌ Escribe el motivo de rechazo:\n\n"
            "<i>(o toca Cancelar para volver)</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Cancelar", callback_data="cmd_pendientes"),
            ]]),
        )
        return

    if data.startswith(("eliminar_", "confirmar_del_")):
        await query.answer("⏳ Eliminando...")
        prefijo  = "eliminar_" if data.startswith("eliminar_") else "confirmar_del_"
        cid8     = data[len(prefijo):]
        contacto = db.buscar_por_id_o_telefono(cid8)
        if contacto:
            await query.edit_message_text("⏳ Eliminando contacto...")
            db.client.table("contactos").update(
                {"deleted_at": datetime.utcnow().isoformat()}
            ).eq("id", contacto["id"]).execute()
            await mostrar_pendientes(query.message, context, query.from_user.id,
                                     pagina=0, editar=True)
        else:
            await query.edit_message_text(
                "❌ No encontrado.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Ver pendientes", callback_data="cmd_pendientes"),
                    InlineKeyboardButton("🏠 Inicio",         callback_data="cmd_inicio"),
                ]]),
            )
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

    if data.startswith("ver_ev_"):
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        rid8 = data[7:]
        try:
            resp = db.client.table("reportes").select(
                "evidencia_file_id, evidencia_msg_id, evidencia_chat_id, "
                "motivo, descripcion, contactos(nombre, apellido, telefono)"
            ).ilike("id", f"{rid8}%").limit(1).execute()
            if not resp.data:
                await query.answer("❌ Reporte no encontrado", show_alert=True)
                return
            r = resp.data[0]
            file_id = r.get("evidencia_file_id")
            if not file_id:
                await query.answer("📎 Este reporte no tiene evidencia adjunta", show_alert=True)
                return
            c      = r.get("contactos") or {}
            nombre = f"{c.get('nombre','?')} {c.get('apellido','')}"
            # Enviar la foto al admin en un mensaje nuevo (no editar — es una foto)
            await context.bot.send_photo(
                chat_id = query.from_user.id,
                photo   = file_id,
                caption = (
                    f"📎 *Evidencia del reporte*\n\n"
                    f"👤 {nombre} — `{c.get('telefono','')}`\n"
                    f"⚠️ {r.get('motivo','')}\n"
                    + (f"💬 {r.get('descripcion','')}" if r.get('descripcion') else "")
                ),
                parse_mode="Markdown",
            )
            await query.answer("📎 Evidencia enviada a tu chat", show_alert=False)
        except Exception as e:
            await query.answer(f"❌ Error: {e}", show_alert=True)
        return
