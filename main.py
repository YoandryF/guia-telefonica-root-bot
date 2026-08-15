"""
Bot en thread principal, Flask en thread secundario.
"""
import os, threading, logging, asyncio
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
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
UMBRAL_PENDIENTES = int(os.getenv("UMBRAL_PENDIENTES_ALERTA", "10"))

def _tg_send(chat_id: str, text: str):
    """Enviar mensaje de Telegram vía API"""
    if not BOT_TOKEN or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        return resp.json().get("ok", False)
    except Exception as e:
        logger.error(f"TG send error: {e}")
        return False

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
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
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
                try:
                    tg_resp = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                        json={"chat_id": EVIDENCE_GROUP, "message_id": msg_id},
                    )
                    if tg_resp.json().get("ok"):
                        deleted += 1
                except Exception:
                    pass
                requests.patch(
                    f"{SUPABASE_URL}/rest/v1/reportes?id=eq.{r['id']}",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"evidencia_msg_id": None},
                )
        return jsonify({"deleted": deleted, "total_checked": len(reportes)}), 200
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/notificar-reporte", methods=["POST"])
def notificar_reporte():
    """Notificar al reportador cuando su reporte fue resuelto."""
    from flask import request
    data = request.json or {}
    telegram_id = data.get("telegram_user_id")
    estado = data.get("estado", "")
    contacto = data.get("contacto_nombre", "el contacto")
    nota = data.get("nota_admin", "")
    if not telegram_id:
        return jsonify({"error": "missing telegram_user_id"}), 400
    if estado == "revisado":
        msg = (f"✅ *Tu reporte fue aprobado*\n\n"
               f"El contacto *{contacto}* ha sido marcado como riesgoso gracias a tu reporte.\n"
               f"{'📝 Nota del admin: ' + nota if nota else ''}")
    elif estado == "resuelto":
        msg = (f"ℹ️ *Tu reporte fue desestimado*\n\n"
               f"El reporte sobre *{contacto}* fue revisado y no se tomó acción.\n"
               f"{'📝 Nota del admin: ' + nota if nota else ''}")
    else:
        return jsonify({"ok": False, "reason": "estado no notificable"}), 200
    ok = _tg_send(telegram_id, msg)
    return jsonify({"ok": ok}), 200


@app.route("/alerta-pendientes", methods=["POST"])
def alerta_pendientes():
    """Alertar al admin si hay >= UMBRAL_PENDIENTES reportes sin revisar."""
    if not SUPABASE_URL or not ADMIN_CHAT_ID:
        return jsonify({"error": "config missing"}), 500
    try:
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/contar_reportes_pendientes",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
        total = resp.json() if resp.status_code == 200 else 0
        if isinstance(total, int) and total >= UMBRAL_PENDIENTES:
            msg = (f"🚨 *Alerta: {total} reportes pendientes*\n\n"
                   f"Hay {total} reportes sin revisar en la Guía Telefónica.\n"
                   f"Abre el panel admin para gestionarlos.")
            _tg_send(ADMIN_CHAT_ID, msg)
            return jsonify({"alerta_enviada": True, "pendientes": total}), 200
        return jsonify({"alerta_enviada": False, "pendientes": total}), 200
    except Exception as e:
        logger.error(f"Alerta pendientes error: {e}")
        return jsonify({"error": str(e)}), 500


def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("✅ Flask iniciado")

    from bot import create_app, _set_commands
    telegram_app = create_app()
    if not telegram_app:
        return

    logger.info("✅ Bot polling iniciado")

    # Crear un event loop nuevo y persistente para todo el ciclo de vida del bot.
    # asyncio.run() destruye el loop al terminar — por eso _set_commands y
    # run_polling deben correr en el MISMO loop, no en loops separados.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_set_commands(telegram_app))
        telegram_app.run_polling(drop_pending_updates=False)
    finally:
        loop.close()

if __name__ == "__main__":
    main()
