"""
Bot de Telegram - Guía Telefónica Colaborativa
@GuiaTelefonicaRootBot

Entry point — only create_app(), _set_commands(), main()
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

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Import handlers
from handlers.public import (
    start, ayuda, listar, buscar, miscontactos, categorias,
    listanegra, handle_texto_libre, avalar, reclamar,
    cancelar_registro, verificarme, micodigo, misreferidos,
)
from handlers.admin import (
    pendientes, aprobar, rechazar, estadisticas, eliminar,
    confirmar_eliminar, editar, reportes, desestimar,
    banear_reportador, desbanear, exportar, importar_archivo,
    handle_texto_admin, verificar, reclamos, reportar, avales,
)
from handlers.owner import (
    registrar_admin, listar_admins, eliminar_admin, config, setconfig,
)
from handlers.callbacks import callback_handler


def create_app():
    """Crear y configurar la aplicación del bot (sin iniciarla)"""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurado")
        return None

    app = Application.builder().token(TOKEN).build()

    # Comandos públicos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("help", ayuda))
    app.add_handler(CommandHandler("listar", listar))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("miscontactos", miscontactos))
    app.add_handler(CommandHandler("categorias", categorias))

    # Flujos interactivos (ConversationHandler)
    from conversations import get_agregar_handler, get_reportar_handler
    app.add_handler(get_agregar_handler())
    app.add_handler(get_reportar_handler())

    # Comandos admin
    app.add_handler(CommandHandler("pendientes", pendientes))
    # Callback de botones inline
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Handler para texto libre del admin (motivo de rechazo, edición config)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(int(ADMIN_CHAT_ID)), handle_texto_admin))
    # Handler para texto libre de TODOS los usuarios (búsqueda directa)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto_libre))
    app.add_handler(CommandHandler("aprobar", aprobar))
    app.add_handler(CommandHandler("rechazar", rechazar))
    app.add_handler(CommandHandler("estadisticas", estadisticas))
    app.add_handler(CommandHandler("listanegra", listanegra))
    app.add_handler(CommandHandler("eliminar", eliminar))
    app.add_handler(CommandHandler("confirmar_eliminar", confirmar_eliminar))
    app.add_handler(CommandHandler("editar", editar))

    # Comandos usuario
    app.add_handler(CommandHandler("cancelar_registro", cancelar_registro))

    # Comandos owner (gestión de admins)
    app.add_handler(CommandHandler("registrar_admin", registrar_admin))
    app.add_handler(CommandHandler("listar_admins", listar_admins))
    app.add_handler(CommandHandler("eliminar_admin", eliminar_admin))

    # Configuración (owner)
    app.add_handler(CommandHandler("config", config))
    app.add_handler(CommandHandler("setconfig", setconfig))

    # Verificacion
    app.add_handler(CommandHandler("verificarme", verificarme))
    app.add_handler(CommandHandler("verificar", verificar))

    # Invitaciones / referidos
    app.add_handler(CommandHandler("micodigo", micodigo))
    app.add_handler(CommandHandler("misreferidos", misreferidos))

    # Avales y reclamos
    app.add_handler(CommandHandler("avalar", avalar))
    app.add_handler(CommandHandler("avales", avales))
    app.add_handler(CommandHandler("reclamar", reclamar))
    app.add_handler(CommandHandler("reclamos", reclamos))

    # Comandos export/import
    app.add_handler(CommandHandler("exportar", exportar))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.User(int(ADMIN_CHAT_ID)), importar_archivo))

    # Comandos reportes (admin)
    app.add_handler(CommandHandler("reportes", reportes))
    app.add_handler(CommandHandler("reportar", reportar))
    app.add_handler(CommandHandler("desestimar", desestimar))
    app.add_handler(CommandHandler("banear_reportador", banear_reportador))
    app.add_handler(CommandHandler("desbanear", desbanear))

    return app


async def _set_commands(app):
    """Registrar solo /start en el menú público — el resto se usa sin menú."""
    from telegram import BotCommand, BotCommandScopeDefault
    await app.bot.set_my_commands(
        [BotCommand("start", "Inicio y bienvenida")],
        scope=BotCommandScopeDefault(),
    )


def main():
    """Iniciar el bot (para uso local)"""
    app = create_app()
    if not app:
        return

    logger.info("Iniciando bot en modo polling (local)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
