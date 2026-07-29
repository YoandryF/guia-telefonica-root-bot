"""
Bot en thread principal, Flask en thread secundario.
"""
import os, threading, logging
from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/")
def root():
    return jsonify({"app": "Guia Telefonica Bot", "status": "running"}), 200

@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": "running"}), 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("✅ Flask iniciado")

    from bot import create_app
    telegram_app = create_app()
    if telegram_app:
        logger.info("✅ Bot polling iniciado")
        telegram_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
