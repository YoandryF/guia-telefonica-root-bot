"""
Bot en thread principal, Flask en thread secundario.
"""
import os, threading, logging
from dotenv import load_dotenv
from flask import Flask, jsonify
import requests

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
EVIDENCE_GROUP = os.getenv("TELEGRAM_EVIDENCE_GROUP", "")

@app.route("/")
def root():
    return jsonify({"app": "Guia Telefonica Bot", "status": "running"}), 200

@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": "running"}), 200

@app.route("/cleanup-evidencias", methods=["POST"])
def cleanup_evidencias():
    """Borrar mensajes de evidencias de reportes resueltos hace >30 días"""
    if not SUPABASE_URL or not BOT_TOKEN or not EVIDENCE_GROUP:
        return jsonify({"error": "config missing"}), 500

    try:
        # Buscar reportes resueltos con evidencia, resueltos hace >30 días
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        # Reportes con evidencia cuyo estado es 'resuelto' y fecha_reporte < hace 30 días
        from datetime import datetime, timedelta
        hace_30 = (datetime.utcnow() - timedelta(days=30)).isoformat()

        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/reportes"
            f"?evidencia_msg_id=not.is.null"
            f"&estado=eq.resuelto"
            f"&fecha_reporte=lt.{hace_30}"
            f"&select=id,evidencia_msg_id",
            headers=headers,
        )
        reportes = resp.json() if resp.status_code == 200 else []

        deleted = 0
        for r in reportes:
            msg_id = r.get("evidencia_msg_id")
            if msg_id:
                # Borrar mensaje de Telegram
                try:
                    tg_resp = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                        json={"chat_id": EVIDENCE_GROUP, "message_id": msg_id},
                    )
                    if tg_resp.json().get("ok"):
                        deleted += 1
                except Exception:
                    pass

                # Limpiar referencia en Supabase
                requests.patch(
                    f"{SUPABASE_URL}/rest/v1/reportes?id=eq.{r['id']}",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"evidencia_msg_id": None},
                )

        return jsonify({"deleted": deleted, "total_checked": len(reportes)}), 200
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return jsonify({"error": str(e)}), 500

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
