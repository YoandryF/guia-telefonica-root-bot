"""
Public command handlers — accessible by all users.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import db, ADMIN_CHAT_ID, es_admin, _mostrar_lista, cache_resultados_get, cache_resultados_set
from utils.formatters import formatear_contacto, _formato_lista_compacta, teclado_contacto

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida + verificación deep link"""
    user = update.effective_user
    db.registrar_usuario_telegram(
        chat_id=str(user.id),
        nombre_usuario=user.username,
        primer_nombre=user.first_name,
        ultimo_nombre=user.last_name,
    )

    # Verificación desde la app (deep link: /start verify_CODIGO)
    if context.args and len(context.args) > 0 and context.args[0].startswith("verify_"):
        codigo = context.args[0].replace("verify_", "").upper()
        try:
            result = db.client.rpc("verificar_codigo_telegram", {
                "p_codigo": codigo,
                "p_telegram_user_id": user.id,
                "p_telegram_username": user.username,
            }).execute()
            status = result.data if result.data else "ERROR"
            if status == "OK":
                await update.message.reply_text(
                    "✅ *¡Verificación exitosa!*\n\n"
                    "Ya puedes volver a la app. Tu cuenta de Telegram está vinculada.\n"
                    "Ahora puedes reportar, avalar y reclamar contactos.",
                    parse_mode="Markdown",
                )
            elif status == "CODIGO_INVALIDO":
                await update.message.reply_text(
                    "❌ Código inválido o expirado.\n"
                    "Vuelve a la app y genera un nuevo código.",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(f"⚠️ Error: {status}")
        except Exception as e:
            logger.error(f"Error verificación: {e}")
            await update.message.reply_text("❌ Error procesando verificación. Intenta de nuevo.")
        return

    # Invitación por referido (/start invitacion_GT_XXXXXXXX)
    if context.args and len(context.args) > 0 and context.args[0].startswith("invitacion_"):
        # El parámetro completo es "invitacion_GT_XXXXXXXX"
        # Extraer todo lo que viene después de "invitacion_"
        codigo_inv = context.args[0][len("invitacion_"):]
        try:
            result = db.client.rpc("registrar_referido", {
                "p_codigo":      codigo_inv,
                "p_referido_id": str(user.id),
            }).execute()
            res   = result.data if result.data else {}
            ok    = res.get("ok", False)
            error = res.get("error", "")
            if ok:
                logger.info(f"Referido registrado: {user.id} via código {codigo_inv}")
                # Notificar al usuario que llegó por invitación
                await update.message.reply_text(
                    "🎉 *¡Bienvenido!*\n\n"
                    "Llegaste a través de una invitación.\n"
                    "Tu registro como referido ha quedado guardado.\n\n"
                    "⬇️ Descarga la app para acceder a todas las funciones:\n"
                    "[Descargar APK](https://github.com/YoandryF/guia-telefonica-root-app/releases/latest)",
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                return  # no mostrar bienvenida genérica encima
            elif error == "YA_REFERIDO":
                logger.info(f"Usuario {user.id} ya era referido")
            elif error == "AUTOREFERIDO":
                logger.info(f"Usuario {user.id} intentó auto-referido")
            elif error == "CODIGO_INVALIDO":
                logger.warning(f"Código de invitación inválido: {codigo_inv}")
            # Para los casos de error silencioso, continuar al mensaje normal
        except Exception as e:
            logger.error(f"Error registrando referido: {e}")
        # Continuar al mensaje de bienvenida normal

    mensaje = (
        "👋 *Bienvenido a la Guía Telefónica ROOT*\n\n"
        "Escribe directamente en el chat para buscar:\n\n"
        "📱 Número de teléfono — _ej: 55551234_\n"
        "👤 Nombre o apellido — _ej: Juan Pérez_\n\n"
        "✅ Contactos verificados tienen badge verde\n"
        "⚠️ Contactos reportados se marcan visiblemente\n\n"
        "📲 *App Android disponible:*\n"
        "[⬇️ Descargar APK](https://github.com/YoandryF/guia-telefonica-root-app/releases/latest)\n\n"
        "_Base de datos colaborativa — tu aporte importa_ 🤝"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔍 Buscar", switch_inline_query_current_chat=""),
            InlineKeyboardButton("➕ Agregar contacto", callback_data="cmd_agregar"),
        ],
        [
            InlineKeyboardButton("📌 Mis reportes",     callback_data="cmd_misreportes"),
            InlineKeyboardButton("❓ Ayuda",             callback_data="cmd_ayuda"),
        ],
    ]

    if es_admin(user.id):
        keyboard.append([
            InlineKeyboardButton("🔐 Pendientes", callback_data="cmd_pendientes"),
            InlineKeyboardButton("🚨 Reportes",   callback_data="cmd_reportes"),
        ])

    await update.message.reply_text(
        mensaje,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista completa de comandos"""
    mensaje = (
        "📖 *Cómo usar la Guía Telefónica*\n\n"
        "Escribe directamente en el chat:\n"
        "• Un *número de teléfono* para buscarlo\n"
        "• Un *nombre o apellido* para buscar personas\n\n"
        "Desde el menú de /start puedes:\n"
        "• 🔍 *Buscar* — búsqueda inline desde cualquier chat\n"
        "• ➕ *Agregar contacto* — registrar uno nuevo\n"
        "• 📌 *Mis reportes* — ver tus reportes enviados\n\n"
        "Al ver un contacto tendrás botones para:\n"
        "• 📲 Abrir en Telegram o WhatsApp\n"
        "• ⚠️ Reportar si es sospechoso\n"
        "• 👍 Avalar si es confiable\n"
    )

    if es_admin(update.effective_user.id):
        mensaje += (
            "\n🔐 *Comandos admin:*\n"
            "/pendientes — contactos por aprobar\n"
            "/aprobar `teléfono` — aprobar\n"
            "/rechazar `id` — rechazar\n"
            "/eliminar `teléfono` — eliminar\n"
            "/editar `teléfono, campo, valor` — editar\n"
            "/estadisticas — ver estadísticas\n"
            "/reportes — reportes pendientes\n"
            "/desestimar `id` — desestimar reporte\n"
            "/avales — avales pendientes\n"
            "/reclamos — reclamos pendientes\n"
            "/exportar `csv|json` — exportar BD\n"
            "/banear `id` — banear reportador\n"
            "/verificar `teléfono` — verificar contacto\n"
        )

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def handle_texto_libre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Texto libre para TODOS los usuarios — busca número o nombre directamente"""
    texto = update.message.text.strip()

    # Si parece número de teléfono → mostrar detalle
    limpio = texto.replace('-', '').replace(' ', '').replace('+', '')
    if limpio.isdigit() and len(limpio) >= 5:
        msg = await update.message.reply_text("🔍 Buscando número...")
        await update.message.chat.send_action("typing")
        contacto = db.buscar_por_id_o_telefono(texto)
        if contacto:
            admin = es_admin(update.effective_user.id)
            detalle = formatear_contacto(contacto, mostrar_id=admin)
            markup  = teclado_contacto(contacto, es_admin=admin)
            await msg.edit_text(detalle, parse_mode="Markdown", reply_markup=markup)
        else:
            await msg.edit_text(
                f"❌ No encontré ningún contacto con `{texto}`\n\n"
                f"_¿Quieres registrarlo? Usa /agregar_",
                parse_mode="Markdown",
            )
        return

    # Si tiene 3+ chars → buscar como nombre
    if len(texto) >= 3:
        msg = await update.message.reply_text(f"🔍 Buscando *{texto}*...", parse_mode="Markdown")
        await update.message.chat.send_action("typing")
        contactos = db.buscar_contactos(texto)
        if contactos:
            chat_id = str(update.effective_user.id)
            cache_resultados_set(chat_id, {'contactos': contactos, 'query': texto})
            total = len(contactos)
            total_pags = max(1, (total + 9) // 10)
            t, markup = _formato_lista_compacta(contactos[:10], 1, total, 1, total_pags, texto)
            await msg.edit_text(t, parse_mode="Markdown", reply_markup=markup)
        else:
            await msg.edit_text(
                f"❌ Sin resultados para *{texto}*\n\nIntenta con otro término.",
                parse_mode="Markdown",
            )

