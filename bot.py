"""
Bot de Telegram - Guía Telefónica Colaborativa
@GuiaTelefonicaRootBot
"""

import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
from supabase_service import SupabaseService

load_dotenv()

# Configuración
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

# Servicio de Supabase
db = SupabaseService()

# ============================================
# HELPERS
# ============================================

def es_admin(chat_id: int) -> bool:
    """Verificar si un chat_id es administrador"""
    return str(chat_id) == str(ADMIN_CHAT_ID)


def formatear_contacto(contacto: dict, mostrar_id: bool = False) -> str:
    """Formatear un contacto estilo profesional"""
    info = db.get_info_reportes(contacto['id'])
    mostrar_badge = info['mostrar']
    verificado = info['verificado']
    warning = " ⚠️" if mostrar_badge else ""
    nombre = f"{contacto['nombre']} {contacto['apellido']}".upper()

    texto = f"📋 *Detalles del contacto:*{warning}\n\n"
    if mostrar_id:
        texto += f"• 🔑 ID: `{contacto['id'][:8]}`\n"
    texto += f"• 📱 Número: `{contacto['telefono']}`\n"
    texto += f"• 👤 A nombre de: {nombre}\n"
    if contacto.get('ci'):
        texto += f"• 🆔 Carné de identidad: `{contacto['ci']}`\n"
    if contacto.get('direccion'):
        texto += f"• 📍 Dirección: {contacto['direccion']}\n"
    if contacto.get('categoria_nombre'):
        texto += f"• 📂 Categoría: {contacto['categoria_nombre']}\n"
    tel = contacto['telefono'].replace('-', '').replace(' ', '')
    if len(tel) >= 8:
        num = tel if tel.startswith('+') else f"53{tel}" if len(tel) == 8 else tel
        texto += f"• 📲 [Telegram](https://t.me/+{num}) | [WhatsApp](https://wa.me/{num})\n"
    if mostrar_badge:
        if verificado:
            texto += f"\n⚠️ _Contacto verificado como riesgoso_\n"
        else:
            total = info['pendientes']
            texto += f"\n⚠️ _Reportado {total} veces_\n"
    texto += f"\n_Bot: @GuiaTelefonicaRootBot_"
    return texto


def paginar_contactos(contactos: list, pagina: int, por_pagina: int = 10) -> tuple:
    """Paginar lista de contactos"""
    total_paginas = max(1, (len(contactos) + por_pagina - 1) // por_pagina)
    pagina = max(1, min(pagina, total_paginas))
    inicio = (pagina - 1) * por_pagina
    fin = inicio + por_pagina
    return contactos[inicio:fin], pagina, total_paginas


# ============================================
# COMANDOS PÚBLICOS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida"""
    # Registrar usuario
    user = update.effective_user
    db.registrar_usuario_telegram(
        chat_id=str(user.id),
        nombre_usuario=user.username,
        primer_nombre=user.first_name,
        ultimo_nombre=user.last_name,
    )

    mensaje = (
        "👋 *¡Bienvenido a la Guía Telefónica!*\n\n"
        "📋 Soy un bot colaborativo para buscar y registrar contactos.\n\n"
        "*Comandos disponibles:*\n"
        "/listar - Ver contactos aprobados\n"
        "/buscar `texto` - Buscar por nombre/teléfono/CI\n"
        "/agregar - Registrar nuevo contacto\n"
        "/miscontactos - Mis contactos registrados\n"
        "/categorias - Ver categorías\n"
        "/reportar - Reportar un contacto\n"
        "/ayuda - Todos los comandos\n"
    )

    if es_admin(user.id):
        mensaje += (
            "\n🔐 *Comandos de Admin:*\n"
            "/pendientes - Contactos por aprobar\n"
            "/aprobar `id` - Aprobar contacto\n"
            "/rechazar `id` `motivo` - Rechazar contacto\n"
            "/estadisticas - Ver estadísticas\n"
            "/exportar `formato` - Exportar BD\n"
        )

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista completa de comandos"""
    mensaje = (
        "📖 *AYUDA - Guía Telefónica*\n\n"
        "*Consultas:*\n"
        "/listar - Lista contactos (paginado)\n"
        "/listar `N` - Página N de contactos\n"
        "/buscar `texto` - Busca por nombre, teléfono o CI\n"
        "/categorias - Ver categorías\n\n"
        "*Registro:*\n"
        "/agregar - Registrar contacto (interactivo)\n"
        "/agregar `Nombre, Apellido, Teléfono` - Directo\n"
        "/cancelar\\_registro `teléfono` - Cancelar mi pendiente\n\n"
        "*Mis datos:*\n"
        "/miscontactos - Contactos que has registrado\n\n"
        "*Reportes:*\n"
        "/reportar - Reportar contacto (interactivo)\n"
        "/reportar `teléfono` `motivo` - Directo\n"
    )

    if es_admin(update.effective_user.id):
        mensaje += (
            "\n🔐 *Admin:*\n"
            "/pendientes - Contactos por aprobar\n"
            "/aprobar `teléfono` - Aprobar contacto\n"
            "/rechazar `teléfono` `motivo` - Rechazar\n"
            "/editar `teléfono, campo, valor` - Editar\n"
            "/eliminar `teléfono` - Eliminar contacto\n"
            "/estadisticas - Ver estadísticas\n"
            "/exportar `csv|json` - Exportar BD\n"
            "/reportes - Ver reportes pendientes\n"
            "/desestimar `id` - Desestimar reporte\n"
            "\n👑 *Owner:*\n"
            "/registrar\\_admin `email pass nombre`\n"
            "/listar\\_admins\n"
            "/eliminar\\_admin `email`\n"
        )

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listar contactos aprobados (paginado, con filtro por categoría)"""
    pagina = 1
    categoria_filtro = None

    if context.args:
        for arg in context.args:
            try:
                pagina = int(arg)
            except ValueError:
                categoria_filtro = arg.lower()

    contactos = db.get_contactos_aprobados()

    if categoria_filtro:
        contactos = [c for c in contactos if c.get('categoria_nombre', '').lower().find(categoria_filtro) >= 0]

    if not contactos:
        msg = "📭 No hay contactos"
        if categoria_filtro:
            msg += f" en la categoría '{categoria_filtro}'"
        await update.message.reply_text(msg)
        return

    items, pag_actual, total_pags = paginar_contactos(contactos, pagina)

    texto = f"📋 *Contactos aprobados* (pág {pag_actual}/{total_pags})\n\n"
    for c in items:
        texto += formatear_contacto(c, mostrar_id=es_admin(update.effective_user.id)) + "\n"

    texto += f"\n📊 Total: {len(contactos)} contactos"
    if total_pags > 1:
        texto += f"\n📄 Usa `/listar {pag_actual + 1}` para la siguiente página"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buscar contactos por nombre/teléfono/CI"""
    if not context.args:
        await update.message.reply_text(
            "🔍 Usa: `/buscar texto`\nEjemplo: `/buscar Juan`",
            parse_mode="Markdown",
        )
        return

    query = " ".join(context.args)
    contactos = db.buscar_contactos(query)

    if not contactos:
        await update.message.reply_text(f"🔍 No se encontraron resultados para: *{query}*", parse_mode="Markdown")
        return

    texto = f"🔍 *Resultados para:* `{query}`\n\n"
    for c in contactos[:20]:
        texto += formatear_contacto(c, mostrar_id=es_admin(update.effective_user.id)) + "\n"

    if len(contactos) > 20:
        texto += f"\n... y {len(contactos) - 20} más"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def agregar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registrar nuevo contacto"""
    if not context.args:
        await update.message.reply_text(
            "✏️ *Registrar contacto*\n\n"
            "Formato mínimo:\n"
            "`/agregar Nombre, Apellido, Teléfono`\n\n"
            "Formato completo:\n"
            "`/agregar Nombre, Apellido, Teléfono, Dirección, CI`\n\n"
            "Ejemplo:\n"
            "`/agregar Juan, Pérez, 555-1234, Calle 10 #5, 85010112345`",
            parse_mode="Markdown",
        )
        return

    texto = " ".join(context.args)
    partes = [p.strip() for p in texto.split(",")]

    if len(partes) < 3:
        await update.message.reply_text(
            "⚠️ Mínimo 3 campos: Nombre, Apellido, Teléfono\n"
            "Separados por comas.",
        )
        return

    nombre = partes[0]
    apellido = partes[1]
    telefono = partes[2]
    direccion = partes[3] if len(partes) > 3 else None
    ci = partes[4] if len(partes) > 4 else None

    # Validaciones básicas
    if len(nombre) < 2 or len(apellido) < 2:
        await update.message.reply_text("⚠️ Nombre y apellido deben tener al menos 2 caracteres.")
        return

    if len(telefono) < 5:
        await update.message.reply_text("⚠️ El teléfono debe tener al menos 5 dígitos.")
        return

    # Registrar en Supabase
    resultado = db.registrar_contacto(
        nombre=nombre,
        apellido=apellido,
        telefono=telefono,
        direccion=direccion,
        ci=ci,
        creado_por=str(update.effective_user.id),
        creado_desde="telegram",
    )

    if resultado.get("error"):
        error = resultado["error"]
        if "telefono" in str(error).lower() or "duplicate" in str(error).lower():
            await update.message.reply_text("⚠️ Ese teléfono o CI ya está registrado.")
        else:
            await update.message.reply_text(f"❌ Error al registrar: {error}")
        return

    await update.message.reply_text(
        f"✅ *Contacto registrado exitosamente*\n\n"
        f"👤 {nombre} {apellido}\n"
        f"📱 {telefono}\n\n"
        f"⏳ Estado: *Pendiente de aprobación*\n"
        f"El administrador revisará tu registro.",
        parse_mode="Markdown",
    )

    # Notificar al admin
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"📬 *Nuevo contacto pendiente*\n\n"
                    f"👤 {nombre} {apellido}\n"
                    f"📱 {telefono}\n"
                    f"📍 {direccion or 'N/A'}\n"
                    f"🆔 {ci or 'N/A'}\n"
                    f"👁 Registrado por: @{update.effective_user.username or update.effective_user.first_name}\n\n"
                    f"Usa /pendientes para gestionar"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error notificando admin: {e}")


async def miscontactos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver contactos registrados por este usuario"""
    chat_id = str(update.effective_user.id)
    contactos = db.get_contactos_por_creador(chat_id)

    if not contactos:
        await update.message.reply_text("📭 No has registrado contactos aún.")
        return

    texto = "📋 *Mis contactos registrados:*\n\n"
    for c in contactos:
        estado_emoji = {"aprobado": "✅", "pendiente": "⏳", "rechazado": "❌"}.get(c["estado"], "❓")
        texto += f"{estado_emoji} {c['nombre']} {c['apellido']} - {c['telefono']}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver categorías disponibles"""
    cats = db.get_categorias()

    if not cats:
        await update.message.reply_text("📂 No hay categorías configuradas.")
        return

    texto = "📂 *Categorías disponibles:*\n\n"
    for cat in cats:
        texto += f"  {cat.get('icono', '📋')} {cat['nombre']}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


# ============================================
# COMANDOS DE ADMIN
# ============================================

async def pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver contactos pendientes de aprobación (solo admin) con botones"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    contactos = db.get_contactos_pendientes()

    if not contactos:
        await update.message.reply_text("✅ No hay contactos pendientes de aprobación.")
        return

    await update.message.reply_text(f"⏳ *{len(contactos)} contacto(s) pendiente(s):*", parse_mode="Markdown")

    for c in contactos[:10]:
        texto = (
            f"👤 *{c['nombre']} {c['apellido']}*\n"
            f"📱 `{c['telefono']}`\n"
        )
        if c.get('direccion'):
            texto += f"📍 {c['direccion']}\n"
        if c.get('ci'):
            texto += f"🆔 CI: {c['ci']}\n"

        keyboard = [
            [
                InlineKeyboardButton("✅ Aprobar", callback_data=f"aprobar_{c['id'][:8]}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar_{c['id'][:8]}"),
            ],
            [
                InlineKeyboardButton("🗑 Eliminar", callback_data=f"eliminar_{c['id'][:8]}"),
            ],
        ]
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejar clicks en botones inline"""
    query = update.callback_query
    await query.answer()

    if not es_admin(query.from_user.id):
        await query.edit_message_text("🔒 Solo el administrador.")
        return

    data = query.data
    if data.startswith("aprobar_"):
        contacto_id = data.replace("aprobar_", "")
        resultado = db.aprobar_contacto(contacto_id, aprobado_por=str(query.from_user.id))
        if resultado.get("error"):
            await query.edit_message_text(f"❌ Error: {resultado['error']}")
        else:
            contacto = resultado.get("data", {})
            await query.edit_message_text(f"✅ *Aprobado:* {contacto.get('nombre', '')} {contacto.get('apellido', '')}", parse_mode="Markdown")

    elif data.startswith("rechazar_"):
        contacto_id = data.replace("rechazar_", "")
        context.user_data['rechazar_id'] = contacto_id
        await query.edit_message_text("❌ Escribe el motivo de rechazo:")

    elif data.startswith("eliminar_"):
        contacto_id = data.replace("eliminar_", "")
        contacto = db.buscar_por_id_o_telefono(contacto_id)
        if contacto:
            db.client.table("contactos").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", contacto["id"]).execute()
            await query.edit_message_text(f"🗑 *Eliminado:* {contacto['nombre']} {contacto['apellido']}", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ No encontrado.")


async def aprobar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aprobar un contacto pendiente (solo admin)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    if not context.args:
        await update.message.reply_text("Usa: `/aprobar teléfono` o `/aprobar ID`", parse_mode="Markdown")
        return

    identificador = context.args[0]
    resultado = db.aprobar_contacto(identificador, aprobado_por=str(update.effective_user.id))

    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}")
        return

    contacto = resultado.get("data")
    await update.message.reply_text(
        f"✅ *Contacto aprobado*\n\n"
        f"👤 {contacto['nombre']} {contacto['apellido']}\n"
        f"📱 {contacto['telefono']}",
        parse_mode="Markdown",
    )

    # Notificar al creador
    if contacto.get("creado_por") and contacto["creado_desde"] == "telegram":
        try:
            await context.bot.send_message(
                chat_id=contacto["creado_por"],
                text=f"✅ Tu contacto *{contacto['nombre']} {contacto['apellido']}* fue aprobado!",
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def rechazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rechazar un contacto pendiente (solo admin)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usa: `/rechazar ID motivo`", parse_mode="Markdown")
        return

    contacto_id = context.args[0]
    motivo = " ".join(context.args[1:])

    resultado = db.rechazar_contacto(contacto_id, motivo=motivo)

    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}")
        return

    contacto = resultado.get("data")
    await update.message.reply_text(
        f"❌ *Contacto rechazado*\n\n"
        f"👤 {contacto['nombre']} {contacto['apellido']}\n"
        f"📝 Motivo: {motivo}",
        parse_mode="Markdown",
    )

    # Notificar al creador
    if contacto.get("creado_por") and contacto["creado_desde"] == "telegram":
        try:
            await context.bot.send_message(
                chat_id=contacto["creado_por"],
                text=f"❌ Tu contacto *{contacto['nombre']} {contacto['apellido']}* fue rechazado.\nMotivo: {motivo}",
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estadísticas de la guía (solo admin)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    stats = db.get_estadisticas()

    texto = (
        "📊 *Estadísticas de la Guía Telefónica*\n\n"
        f"✅ Aprobados: {stats.get('aprobados', 0)}\n"
        f"⏳ Pendientes: {stats.get('pendientes', 0)}\n"
        f"❌ Rechazados: {stats.get('rechazados', 0)}\n"
        f"📋 Total: {stats.get('total', 0)}\n"
        f"👥 Usuarios Telegram: {stats.get('usuarios_telegram', 0)}\n"
    )

    await update.message.reply_text(texto, parse_mode="Markdown")


# ============================================
# COMANDOS DE OWNER (solo ADMIN_CHAT_ID)
# ============================================

async def registrar_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registrar un nuevo admin (solo owner)
    Uso: /registrar_admin email password nombre
    """
    if not es_admin(update.effective_user.id):
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
    if not es_admin(update.effective_user.id):
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
    if not es_admin(update.effective_user.id):
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



async def listanegra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar contactos reportados (lista negra)"""
    contactos = db.get_contactos_aprobados()
    reportados = []
    for c in contactos:
        info = db.get_info_reportes(c['id'])
        if info['mostrar']:
            reportados.append((c, info))

    if not reportados:
        await update.message.reply_text("\u2705 No hay contactos en la lista negra.")
        return

    texto = "\u26a0\ufe0f *Lista Negra* (" + str(len(reportados)) + " contactos):\n\n"
    for c, info in reportados[:20]:
        nombre = f"{c['nombre']} {c['apellido']}"
        estado = "\U0001f534 Verificado" if info['verificado'] else f"\U0001f7e1 {info['pendientes']} reportes"
        texto += f"\u2022 *{nombre}*\n   \U0001f4f1 `{c['telefono']}`\n   {estado}\n\n"

    if len(reportados) > 20:
        texto += f"... y {len(reportados) - 20} m\u00e1s"

    await update.message.reply_text(texto, parse_mode="Markdown")


# ============================================
# COMANDOS DE ELIMINACIÓN Y EDICIÓN
# ============================================

async def eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eliminar contacto (solo admin). Uso: /eliminar teléfono|ID"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    if not context.args:
        await update.message.reply_text(
            "🗑️ *Eliminar contacto*\n\n"
            "Usa: `/eliminar teléfono` o `/eliminar ID`\n\n"
            "Ejemplo:\n"
            "`/eliminar 555-1234`\n"
            "`/eliminar abc123ef`",
            parse_mode="Markdown",
        )
        return

    identificador = " ".join(context.args)
    contacto = db.buscar_por_id_o_telefono(identificador)

    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado. Verifica el teléfono o ID.")
        return

    # Confirmar
    nombre = f"{contacto['nombre']} {contacto['apellido']}"
    await update.message.reply_text(
        f"⚠️ *¿Eliminar este contacto?*\n\n"
        f"👤 {nombre}\n📱 {contacto['telefono']}\n\n"
        f"Envía `/confirmar_eliminar {contacto['id'][:8]}` para confirmar",
        parse_mode="Markdown",
    )


async def confirmar_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirmar eliminación de contacto"""
    if not es_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usa: `/confirmar_eliminar ID`", parse_mode="Markdown")
        return

    contacto = db.buscar_por_id_o_telefono(context.args[0])
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.")
        return

    try:
        db.client.table("contactos").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", contacto["id"]).execute()
        await update.message.reply_text(
            f"🗑️ *Contacto eliminado*\n\n👤 {contacto['nombre']} {contacto['apellido']}\n📱 {contacto['telefono']}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cancelar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancelar un registro propio pendiente. Uso: /cancelar_registro teléfono"""
    if not context.args:
        await update.message.reply_text("Usa: `/cancelar_registro teléfono`", parse_mode="Markdown")
        return

    identificador = context.args[0]
    chat_id = str(update.effective_user.id)

    try:
        # Buscar contacto pendiente creado por este usuario
        response = db.client.table("contactos").select("*").ilike("telefono", f"%{identificador}%").eq("estado", "pendiente").eq("creado_por", chat_id).execute()

        if not response.data:
            await update.message.reply_text("❌ No se encontró un contacto pendiente tuyo con ese teléfono.")
            return

        contacto = response.data[0]
        db.client.table("contactos").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", contacto["id"]).execute()

        await update.message.reply_text(
            f"✅ Registro cancelado: *{contacto['nombre']} {contacto['apellido']}* ({contacto['telefono']})",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Editar contacto (solo admin). Uso: /editar teléfono, campo, nuevo_valor"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    if not context.args:
        await update.message.reply_text(
            "✏️ *Editar contacto*\n\n"
            "Uso: `/editar teléfono, campo, nuevo_valor`\n\n"
            "Campos: nombre, apellido, telefono, direccion, ci, categoria\n\n"
            "Ejemplo:\n"
            "`/editar 555-1234, nombre, Carlos`\n"
            "`/editar 555-1234, categoria, Médicos`",
            parse_mode="Markdown",
        )
        return

    texto = " ".join(context.args)
    partes = [p.strip() for p in texto.split(",")]

    if len(partes) < 3:
        await update.message.reply_text("⚠️ Formato: `/editar teléfono, campo, nuevo_valor`", parse_mode="Markdown")
        return

    identificador = partes[0]
    campo = partes[1].lower()
    nuevo_valor = ", ".join(partes[2:])  # Por si el valor tiene comas

    campos_validos = ['nombre', 'apellido', 'telefono', 'direccion', 'ci', 'categoria']
    if campo not in campos_validos:
        await update.message.reply_text(f"⚠️ Campo inválido. Usa: {', '.join(campos_validos)}")
        return

    contacto = db.buscar_por_id_o_telefono(identificador)
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.")
        return

    try:
        # Si es categoría, buscar el ID por nombre
        if campo == 'categoria':
            categorias = db.get_categorias()
            cat_id = None
            for c in categorias:
                if nuevo_valor.lower() in c['nombre'].lower() or c['nombre'].lower() in nuevo_valor.lower():
                    cat_id = c['id']
                    break
            if not cat_id:
                nombres = ", ".join([c['nombre'] for c in categorias])
                await update.message.reply_text(f"⚠️ Categoría no encontrada. Disponibles: {nombres}")
                return
            db.client.table("contactos").update({
                "categoria_id": cat_id,
                "ultima_modificacion": datetime.utcnow().isoformat(),
            }).eq("id", contacto["id"]).execute()
        else:
            db.client.table("contactos").update({
                campo: nuevo_valor,
                "ultima_modificacion": datetime.utcnow().isoformat(),
            }).eq("id", contacto["id"]).execute()

        await update.message.reply_text(
            f"✏️ *Contacto actualizado*\n\n"
            f"👤 {contacto['nombre']} {contacto['apellido']}\n"
            f"📝 {campo} → *{nuevo_valor}*",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ============================================
# COMANDOS DE REPORTES
# ============================================

async def reportar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reportar un contacto. Uso: /reportar id motivo"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Reportar contacto*\n\n"
            "Uso: `/reportar ID motivo`\n\n"
            "Motivos válidos:\n"
            "• `numero_incorrecto`\n"
            "• `no_existe`\n"
            "• `spam`\n"
            "• `duplicado`\n"
            "• `otro`\n\n"
            "Ejemplo: `/reportar abc123 spam`",
            parse_mode="Markdown",
        )
        return

    contacto_id = context.args[0]
    motivo = context.args[1]
    descripcion = " ".join(context.args[2:]) if len(context.args) > 2 else None

    motivos_validos = ['numero_incorrecto', 'no_existe', 'spam', 'duplicado', 'otro']
    if motivo not in motivos_validos:
        await update.message.reply_text(f"⚠️ Motivo inválido. Usa uno de: {', '.join(motivos_validos)}")
        return

    # Buscar contacto por ID o teléfono
    contacto = db.buscar_por_id_o_telefono(contacto_id)
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.")
        return

    resultado = db.reportar_contacto(
        contacto_id=contacto['id'],
        motivo=motivo,
        descripcion=descripcion,
        reportado_por=str(update.effective_user.id),
    )

    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}")
    else:
        await update.message.reply_text("⚠️ Reporte enviado. Gracias por informar.")

        # Notificar al admin
        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"🚨 *Nuevo reporte*\n\nContacto: `{contacto_id}`\nMotivo: {motivo}\nPor: {update.effective_user.first_name}\n\nUsa /reportes para ver todos",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


async def reportes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver reportes pendientes (solo admin)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    lista = db.get_reportes_pendientes()

    if not lista:
        await update.message.reply_text("✅ No hay reportes pendientes.")
        return

    texto = f"🚨 *Reportes pendientes ({len(lista)}):*\n\n"
    for r in lista[:20]:
        contacto = r.get("contactos", {})
        nombre = f"{contacto.get('nombre', '')} {contacto.get('apellido', '')}"
        texto += (
            f"🆔 `{r['id'][:8]}`\n"
            f"👤 {nombre} ({contacto.get('telefono', '')})\n"
            f"⚠️ Motivo: {r['motivo']}\n"
            f"💬 {r.get('descripcion', 'Sin descripción')}\n"
            f"✅ `/desestimar {r['id'][:8]}`\n\n"
        )

    await update.message.reply_text(texto, parse_mode="Markdown")


async def desestimar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desestimar un reporte (solo admin)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    if not context.args:
        await update.message.reply_text("Usa: `/desestimar ID`", parse_mode="Markdown")
        return

    reporte_id = context.args[0]
    resultado = db.desestimar_reporte(reporte_id)

    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}")
    else:
        await update.message.reply_text("✅ Reporte desestimado.")


# ============================================
# COMANDOS DE EXPORTACIÓN/IMPORTACIÓN
# ============================================

async def exportar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exportar contactos (solo admin). Uso: /exportar csv|json"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    formato = context.args[0].lower() if context.args else "csv"
    if formato not in ("csv", "json"):
        await update.message.reply_text("Usa: `/exportar csv` o `/exportar json`", parse_mode="Markdown")
        return

    await update.message.reply_text("⏳ Generando archivo...")

    contactos = db.get_contactos_aprobados()
    if not contactos:
        await update.message.reply_text("📭 No hay contactos para exportar.")
        return

    import io
    import csv as csv_module
    import json

    if formato == "csv":
        output = io.StringIO()
        writer = csv_module.writer(output)
        writer.writerow(["nombre", "apellido", "telefono", "direccion", "ci"])
        for c in contactos:
            writer.writerow([c["nombre"], c["apellido"], c["telefono"], c.get("direccion", ""), c.get("ci", "")])
        content = output.getvalue().encode("utf-8")
        filename = "guia_telefonica.csv"
    else:
        data = {
            "metadatos": {"total": len(contactos), "fecha": str(datetime.utcnow())},
            "contactos": [{"nombre": c["nombre"], "apellido": c["apellido"], "telefono": c["telefono"], "direccion": c.get("direccion"), "ci": c.get("ci")} for c in contactos],
        }
        content = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        filename = "guia_telefonica.json"

    await update.message.reply_document(
        document=io.BytesIO(content),
        filename=filename,
        caption=f"✅ {len(contactos)} contactos exportados ({formato.upper()})",
    )


async def importar_archivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Importar archivo enviado por admin"""
    if not es_admin(update.effective_user.id):
        return

    doc = update.message.document
    if not doc.file_name.endswith((".csv", ".json")):
        await update.message.reply_text("⚠️ Solo acepto archivos .csv o .json")
        return

    await update.message.reply_text("⏳ Procesando archivo...")

    file = await context.bot.get_file(doc.file_id)
    import io
    content_bytes = io.BytesIO()
    await file.download_to_memory(content_bytes)
    content = content_bytes.getvalue().decode("utf-8")

    contactos = []
    if doc.file_name.endswith(".csv"):
        import csv as csv_module
        reader = csv_module.DictReader(io.StringIO(content))
        for row in reader:
            if row.get("nombre") and row.get("telefono"):
                contactos.append(row)
    else:
        import json
        data = json.loads(content)
        items = data.get("contactos", data) if isinstance(data, dict) else data
        for item in items:
            if item.get("nombre") and item.get("telefono"):
                contactos.append(item)

    nuevos, duplicados, errores = 0, 0, 0
    for c in contactos:
        resultado = db.registrar_contacto(
            nombre=c.get("nombre", ""),
            apellido=c.get("apellido", ""),
            telefono=c.get("telefono", ""),
            direccion=c.get("direccion"),
            ci=c.get("ci"),
            creado_por=str(update.effective_user.id),
            creado_desde="telegram",
        )
        if resultado.get("error"):
            if "duplicate" in str(resultado["error"]).lower():
                duplicados += 1
            else:
                errores += 1
        else:
            nuevos += 1

    await update.message.reply_text(
        f"✅ *Importación completada*\n\n"
        f"📊 Procesados: {len(contactos)}\n"
        f"✅ Nuevos: {nuevos}\n"
        f"⚠️ Duplicados: {duplicados}\n"
        f"❌ Errores: {errores}\n\n"
        f"Los contactos quedan *pendientes* de aprobación.",
        parse_mode="Markdown",
    )


# ============================================
# MAIN
# ============================================

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
    app.add_handler(CallbackQueryHandler(callback_handler))
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

    # Comandos export/import
    app.add_handler(CommandHandler("exportar", exportar))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.User(int(ADMIN_CHAT_ID)), importar_archivo))

    # Comandos reportes (admin)
    app.add_handler(CommandHandler("reportes", reportes))
    app.add_handler(CommandHandler("desestimar", desestimar))

    return app


def main():
    """Iniciar el bot (para uso local)"""
    app = create_app()
    if not app:
        return

    logger.info("Iniciando bot en modo polling (local)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
