"""
Public command handlers — accessible by all users.
"""

import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import db, ADMIN_CHAT_ID, es_admin, cache_resultados_get, cache_resultados_set
from utils.formatters import formatear_contacto, _formato_lista_compacta, teclado_contacto, _esc
from utils.views import mostrar_contacto, mostrar_lista_busqueda

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
    if context.args and context.args[0].startswith("verify_"):
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
                    "✅ *¡Verificación exitosa\\!*\n\n"
                    "Ya puedes volver a la app\\. Tu cuenta de Telegram está vinculada\\.",
                    parse_mode="MarkdownV2",
                )
            elif status == "CODIGO_INVALIDO":
                await update.message.reply_text(
                    "❌ Código inválido o expirado\\.\nVuelve a la app y genera un nuevo código\\.",
                    parse_mode="MarkdownV2",
                )
            else:
                await update.message.reply_text(f"⚠️ Error: {status}")
        except Exception as e:
            logger.error(f"Error verificación: {e}")
            await update.message.reply_text("❌ Error procesando verificación\\. Intenta de nuevo\\.", parse_mode="MarkdownV2")
        return

    # Invitación por referido
    if context.args and context.args[0].startswith("invitacion_"):
        codigo_inv = context.args[0][len("invitacion_"):]
        try:
            result = db.client.rpc("registrar_referido", {
                "p_codigo":      codigo_inv,
                "p_referido_id": str(user.id),
            }).execute()
            res   = result.data if result.data else {}
            if res.get("ok"):
                await update.message.reply_text(
                    "🎉 *¡Bienvenido\\!*\n\n"
                    "Llegaste a través de una invitación\\.\n\n"
                    "⬇️ [Descargar APK](https://github.com/YoandryF/guia-telefonica-root-app/releases/latest)",
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                )
                return
        except Exception as e:
            logger.error(f"Error registrando referido: {e}")

    # Bienvenida principal
    from utils.views import mostrar_start
    await mostrar_start(update.message, user.id, user.first_name)


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ayuda — delega a la vista compartida que detecta si es admin."""
    from utils.views import mostrar_ayuda
    await mostrar_ayuda(update.message, update.effective_user.id)


async def handle_texto_libre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Búsqueda directa — número simple, múltiples números, o nombre."""
    texto = update.message.text.strip()

    # ── Detectar múltiples números ────────────────────────────────────────────
    # Separadores: coma, punto y coma, espacio, salto de línea
    tokens = re.split(r'[\s,;]+', texto)
    numeros = [t.replace('-','').replace('+','') for t in tokens
               if t.replace('-','').replace(' ','').replace('+','').isdigit()
               and len(t.replace('-','').replace(' ','').replace('+','')) >= 7]

    if len(numeros) > 1:
        # Búsqueda múltiple
        msg = await update.message.reply_text(
            f"🔍 Buscando {len(numeros)} números\\.\\.\\.",
            parse_mode="MarkdownV2",
        )
        await update.message.chat.send_action("typing")

        resultados = []
        no_encontrados = []
        for num in numeros[:10]:  # máximo 10 a la vez
            contacto = db.buscar_por_id_o_telefono(num)
            if contacto:
                resultados.append(contacto)
            else:
                no_encontrados.append(num)

        if not resultados and not no_encontrados:
            await msg.edit_text("❌ No se encontró ningún resultado\\.", parse_mode="MarkdownV2")
            return

        respuesta = f"📊 *Resultados \\({len(numeros)} números\\)*\n\n"

        for c in resultados:
            info  = db.get_info_reportes(c['id'])
            badge = "⛔" if info.get('verificado') else ("🔴" if info['mostrar'] else "🟢")
            nombre = _esc(f"{c['nombre']} {c['apellido']}".upper())
            respuesta += f"{badge} `{_esc(c['telefono'])}` — {nombre}\n"

        if no_encontrados:
            respuesta += f"\n⚪ *Sin datos:*\n"
            for n in no_encontrados:
                respuesta += f"`{_esc(n)}`  "

        respuesta += "\n\n_Toca un número para ver detalles_"

        # Botones para ver detalle de cada encontrado
        botones = [[InlineKeyboardButton(
            f"🔍 {c['telefono']}", callback_data=f"ver_{c['id'][:8]}"
        )] for c in resultados]

        await msg.edit_text(
            respuesta,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(botones) if botones else None,
        )
        return

    # ── Número único ──────────────────────────────────────────────────────────
    limpio = texto.replace('-','').replace(' ','').replace('+','')
    if limpio.isdigit() and len(limpio) >= 7:
        msg = await update.message.reply_text("🔍 Buscando número\\.\\.\\.", parse_mode="MarkdownV2")
        await update.message.chat.send_action("typing")
        contacto = db.buscar_por_id_o_telefono(texto)
        if contacto:
            admin   = es_admin(update.effective_user.id)
            detalle = formatear_contacto(contacto, mostrar_id=admin)
            markup  = teclado_contacto(contacto, es_admin=admin)
            await msg.edit_text(detalle, parse_mode="MarkdownV2", reply_markup=markup)
        else:
            await msg.edit_text(
                f"⚪ El número `{_esc(limpio)}` no está en nuestra base de datos\\.\n\n"
                f"_¿Lo conoces\\? Agrégalo con /agregar_",
                parse_mode="MarkdownV2",
            )
        return

    # ── Búsqueda por nombre ───────────────────────────────────────────────────
    if len(texto) >= 3:
        msg = await update.message.reply_text(
            f"🔍 Buscando *{_esc(texto)}*\\.\\.\\.",
            parse_mode="MarkdownV2",
        )
        await update.message.chat.send_action("typing")
        contactos = db.buscar_contactos(texto)
        if contactos:
            chat_id = str(update.effective_user.id)
            cache_resultados_set(chat_id, {'contactos': contactos, 'query': texto})
            total      = len(contactos)
            total_pags = max(1, (total + 9) // 10)
            t, markup  = _formato_lista_compacta(contactos[:10], 1, total, 1, total_pags, texto)
            await msg.edit_text(t, parse_mode="MarkdownV2", reply_markup=markup)
        else:
            await msg.edit_text(
                f"❌ Sin resultados para *{_esc(texto)}*\n\nIntenta con otro término\\.",
                parse_mode="MarkdownV2",
            )

