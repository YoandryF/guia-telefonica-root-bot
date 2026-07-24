"""
Servidor web para health check (UptimeRobot + Render)
Se ejecuta en paralelo con el bot de Telegram
"""

import os
import threading
import logging
from flask import Flask, jsonify
from supabase_service import SupabaseService

logger = logging.getLogger(__name__)

app = Flask(__name__)
db = SupabaseService()


@app.route("/health")
def health():
    """Endpoint para UptimeRobot - mantiene vivo el servicio en Render"""
    supabase_ok = db.health_check()
    return jsonify({
        "status": "ok",
        "bot": "running",
        "supabase": "connected" if supabase_ok else "disconnected",
    }), 200


@app.route("/")
def root():
    """Página raíz"""
    return jsonify({
        "app": "Guia Telefonica Bot",
        "bot": "@GuiaTelefonicaRootBot",
        "status": "running",
    }), 200


def run_health_server():
    """Ejecutar servidor Flask en un thread separado"""
    port = int(os.getenv("HEALTH_PORT", 8080))
    logger.info(f"Health server iniciado en puerto {port}")
    app.run(host="0.0.0.0", port=port, debug=False)


def start_health_server():
    """Iniciar el health server en background"""
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()
    return thread
