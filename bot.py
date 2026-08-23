"""
Bot de Telegram - Guía Telefónica Colaborativa
@GuiaTelefonicaRootBot
"""

import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

TOKEN         = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
PORT          = int(os.getenv("PORT", 10000))
WEBHOOK_URL   = os.getenv("RENDER_EXTERNAL_URL", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

from handlers.public  import start, ayuda, handle_texto_libre
from handlers.admin   import (
    pendientes, aprobar, rechazar, estadisticas, eliminar,
    confirmar_eliminar, editar, reportes, desestimar,
    banear_reportador, desbanear, exportar, importar_archivo,
    handle_texto_admin, verificar, reclamos, avales,
)
from handlers.owner   import registrar_admin, listar_admins, eliminar_admin, config, setconfig
from handlers.callbacks import callback_handler


def create_app():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurado")
        return None

    app = Application.builder().token(TOKEN).build()

    # ── Comandos públicos ─────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("help",  ayuda))

    # ── Flujos interactivos (todo se hace desde botones o texto libre) ────────
    from conversations import get_agregar_handler, get_reportar_handler
    app.add_handler(get_agregar_handler())
    app.add_handler(get_reportar_handler())

    # ── Callbacks de botones inline ───────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(callback_handler))

    # ── Texto libre del admin (motivo rechazo, edición config) ───────────────
    if ADMIN_CHAT_ID:
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.User(int(ADMIN_CHAT_ID)),
            handle_texto_admin,
        ))
        # Archivos del admin (importar CSV/JSON)
        app.add_handler(MessageHandler(
            filters.Document.ALL & filters.User(int(ADMIN_CHAT_ID)),
            importar_archivo,
        ))

    # ── Texto libre de todos (búsqueda directa escribiendo) ──────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto_libre))

    # ── Comandos admin (internos, no aparecen en menú público) ───────────────
    app.add_handler(CommandHandler("pendientes",        pendientes))
    app.add_handler(CommandHandler("aprobar",           aprobar))
    app.add_handler(CommandHandler("rechazar",          rechazar))
    app.add_handler(CommandHandler("estadisticas",      estadisticas))
    app.add_handler(CommandHandler("eliminar",          eliminar))
    app.add_handler(CommandHandler("confirmar_eliminar",confirmar_eliminar))
    app.add_handler(CommandHandler("editar",            editar))
    app.add_handler(CommandHandler("reportes",          reportes))
    app.add_handler(CommandHandler("desestimar",        desestimar))
    app.add_handler(CommandHandler("banear",            banear_reportador))
    app.add_handler(CommandHandler("desbanear",         desbanear))
    app.add_handler(CommandHandler("exportar",          exportar))
    app.add_handler(CommandHandler("verificar",         verificar))
    app.add_handler(CommandHandler("reclamos",          reclamos))
    app.add_handler(CommandHandler("avales",            avales))

    # ── Comandos owner ────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("registrar_admin",   registrar_admin))
    app.add_handler(CommandHandler("listar_admins",     listar_admins))
    app.add_handler(CommandHandler("eliminar_admin",    eliminar_admin))
    app.add_handler(CommandHandler("config",            config))
    app.add_handler(CommandHandler("setconfig",         setconfig))

    return app


async def _set_commands(app):
    """Solo /start y /ayuda en el menú del bot."""
    from telegram import BotCommand, BotCommandScopeDefault
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Inicio y bienvenida"),
            BotCommand("ayuda", "Cómo usar el bot"),
        ],
        scope=BotCommandScopeDefault(),
    )


def main():
    app = create_app()
    if not app:
        return
    app.post_init = _set_commands
    logger.info("Iniciando bot en modo polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
