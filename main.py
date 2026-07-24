"""
Punto de entrada principal
Inicia el bot de Telegram + health server para UptimeRobot
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    # Iniciar health server en background
    from health_server import start_health_server
    start_health_server()
    logger.info("✅ Health server iniciado")

    # Iniciar bot
    from bot import main as start_bot
    logger.info("✅ Iniciando bot de Telegram...")
    start_bot()


if __name__ == "__main__":
    main()
