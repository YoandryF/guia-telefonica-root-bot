"""
Punto de entrada principal
Flask en el puerto principal (para Render + UptimeRobot)
Bot de Telegram en polling (thread separado)
"""

import os
import threading
import logging
import asyncio
from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
def root():
    return jsonify({"app": "Guia Telefonica Bot", "status": "running"}), 200


@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": "running"}), 200


def run_bot():
    """Ejecutar el bot de Telegram en polling (thread separado)"""
    from bot import create_app
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    telegram_app = create_app()
    logger.info("✅ Bot de Telegram iniciado en modo polling")
    telegram_app.run_polling(allowed_updates=["message", "callback_query"])


def main():
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Bot thread iniciado")

    port = int(os.getenv("PORT", 10000))
    logger.info(f"✅ Flask server en puerto {port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
