"""
Owner-only command handlers — restricted to ADMIN_CHAT_ID.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import db, es_owner

logger = logging.getLogger(__name__)


async def registrar_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registrar un nuevo admin (solo owner)
    Uso: /registrar_admin email password nombre
    """
    if not es_owner(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el owner puede usar este comando.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "📋 *Registrar nuevo admin*\n\n"
            "Uso: `/registrar_admin email password nombre`\n\n"
            "Ejemplo:\n"
            "`/registrar_admin juan@email.com MiPass123 Juan Pérez`",
            parse_mode="Markdown",
        )
        return

    email = context.args[0]
    password = context.args[1]
    nombre = " ".join(context.args[2:])

    resultado = db.crear_admin(email=email, password=password, nombre=nombre)

    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}")
    else:
        await update.message.reply_text(
            f"✅ *Admin registrado exitosamente*\n\n"
            f"👤 {nombre}\n"
            f"📧 {email}\n"
            f"🔑 Password: `{password}`\n\n"
            f"Ya puede iniciar sesión en la app.",
            parse_mode="Markdown",
        )


async def listar_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listar admins registrados (solo owner)"""
    if not es_owner(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el owner puede usar este comando.")
        return

    admins = db.get_admins()

    if not admins:
        await update.message.reply_text("📭 No hay admins registrados.")
        return

    texto = "🔐 *Admins registrados:*\n\n"
    for a in admins:
        estado = "✅" if a.get("activo") else "❌"
        texto += f"{estado} {a.get('nombre_admin', 'Sin nombre')} — {a['email']}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def eliminar_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desactivar un admin (solo owner)
    Uso: /eliminar_admin email
    """
    if not es_owner(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el owner puede usar este comando.")
        return

    if not context.args:
        await update.message.reply_text("Usa: `/eliminar_admin email`", parse_mode="Markdown")
        return

    email = context.args[0]
    resultado = db.desactivar_admin(email)

    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}")
    else:
        await update.message.reply_text(f"✅ Admin `{email}` desactivado.", parse_mode="Markdown")


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver configuración actual con botones (solo owner)"""
    if not es_owner(update.effective_user.id):
        await update.message.reply_text("\U0001f512 Solo el owner.")
        return
    try:
        response = db.client.table("configuracion").select("*").order("clave").execute()
        if not response.data:
            await update.message.reply_text("No hay configuraciones.")
            return
        await update.message.reply_text("\u2699\ufe0f *Configuraci\u00f3n del sistema:*", parse_mode="Markdown")
        for item in response.data:
            keyboard = [[InlineKeyboardButton(f"\u270f\ufe0f Editar", callback_data=f"cfg_edit_{item['clave']}")]]
            await update.message.reply_text(
                f"\u2022 *{item['clave']}*\n   Valor: `{item['valor']}`\n   _{item.get('descripcion','')}_",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
            )
    except Exception as e:
        await update.message.reply_text(f"\u274c Error: {e}")


async def setconfig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cambiar configuración (solo owner). Uso: /setconfig clave valor"""
    if not es_owner(update.effective_user.id):
        await update.message.reply_text("\U0001f512 Solo el owner.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usa: `/setconfig clave valor`\nEjemplo: `/setconfig reportes_dia_normal 5`", parse_mode="Markdown")
        return
    clave = context.args[0]
    valor = " ".join(context.args[1:])
    try:
        response = db.client.table("configuracion").update({"valor": valor}).eq("clave", clave).execute()
        if response.data:
            await update.message.reply_text(f"\u2705 `{clave}` = *{valor}*", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"\u274c Clave `{clave}` no encontrada.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"\u274c Error: {e}")
