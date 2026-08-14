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
    """Verificar si un chat_id es administrador o owner"""
    if str(chat_id) == str(ADMIN_CHAT_ID):
        return True
    # Verificar en tabla admins
    try:
        response = db.client.table("admins").select("id").eq("chat_id_telegram", str(chat_id)).eq("activo", True).execute()
        return len(response.data) > 0
    except Exception:
        return False


def es_owner(chat_id: int) -> bool:
    """Verificar si es el owner (solo uno)"""
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


def _formato_lista_compacta(contactos: list, inicio_num: int, total: int, pagina: int, total_pags: int, query_texto: str = "") -> tuple[str, InlineKeyboardMarkup]:
    """Genera el mensaje de lista numerada compacta + botones de paginación."""
    lineas = []
    for i, c in enumerate(contactos):
        num = inicio_num + i
        nombre = f"{c['nombre']} {c['apellido']}"
        # Truncar nombre a 20 chars
        if len(nombre) > 20:
            nombre = nombre[:18] + "…"
        tel = c['telefono']
        dir_ = c.get('direccion', '')
        if dir_ and len(dir_) > 25:
            dir_ = dir_[:23] + "…"
        linea = f"*{num}.* {nombre.upper()}\n"
        linea += f"   📱 `{tel}`\n"
        if dir_:
            linea += f"   🏠 {dir_}\n"
        lineas.append(linea)

    texto = "".join(lineas)
    texto += f"\n📊 Mostrando {inicio_num}-{inicio_num + len(contactos) - 1} de *{total}* resultados\n"
    if query_texto:
        texto += f"\n_Para ver detalles, escribe el número de teléfono_"
    else:
        texto += f"\n_Escribe el número para ver detalles o usa los botones_"

    # Botones de paginación
    botones = []
    fila = []
    if pagina > 1:
        prefijo = f"pg_{query_texto}_" if query_texto else "pg__"
        fila.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"{prefijo}{pagina - 1}"))
    if pagina < total_pags:
        prefijo = f"pg_{query_texto}_" if query_texto else "pg__"
        fila.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"{prefijo}{pagina + 1}"))
    if fila:
        botones.append(fila)

    return texto, InlineKeyboardMarkup(botones)


# Cache simple de resultados de búsqueda por chat_id
_cache_resultados: dict = {}


async def _mostrar_lista(update_or_query, context, contactos: list, pagina: int, query_texto: str = "", editar: bool = False):
    """Mostrar lista paginada. Puede enviar nuevo mensaje o editar existente."""
    por_pagina = 10
    total = len(contactos)
    total_pags = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = max(1, min(pagina, total_pags))
    inicio = (pagina - 1) * por_pagina
    items = contactos[inicio:inicio + por_pagina]
    inicio_num = inicio + 1

    texto, markup = _formato_lista_compacta(items, inicio_num, total, pagina, total_pags, query_texto)

    if editar:
        await update_or_query.edit_message_text(texto, parse_mode="Markdown", reply_markup=markup)
    else:
        msg = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
        await msg.reply_text(texto, parse_mode="Markdown", reply_markup=markup)


# ============================================
# COMANDOS PÚBLICOS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida + verificación deep link"""
    # Registrar usuario
    user = update.effective_user
    db.registrar_usuario_telegram(
        chat_id=str(user.id),
        nombre_usuario=user.username,
        primer_nombre=user.first_name,
        ultimo_nombre=user.last_name,
    )

    # Verificación desde la app (deep link: /start verify_CODIGO)
    if context.args and len(context.args) > 0 and context.args[0].startswith("verify_"):
        codigo = context.args[0].replace("verify_", "").upper()
        try:
            result = db.client.rpc("verificar_codigo_telegram", {
                "p_codigo": codigo,
                "p_telegram_user_id": user.id,
                "p_telegram_username": user.username,
            }).execute()
            status = result.data if result.data else "ERROR"
            if status == "OK":
                await update.message.reply_text(
                    "✅ *¡Verificación exitosa!*\n\n"
                    "Ya puedes volver a la app. Tu cuenta de Telegram está vinculada.\n"
                    "Ahora puedes reportar, avalar y reclamar contactos.",
                    parse_mode="Markdown",
                )
            elif status == "CODIGO_INVALIDO":
                await update.message.reply_text(
                    "❌ Código inválido o expirado.\n"
                    "Vuelve a la app y genera un nuevo código.",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(f"⚠️ Error: {status}")
        except Exception as e:
            logger.error(f"Error verificación: {e}")
            await update.message.reply_text("❌ Error procesando verificación. Intenta de nuevo.")
        return

    mensaje = (
        "👋 *Bienvenido a la Guía Telefónica ROOT*\n\n"
        "Puedes buscar escribiendo directamente en el chat:\n\n"
        "┌ 📱 Número de teléfono _\(ej: 55551234\)_\n"
        "├ 👤 Nombre o apellido _\(ej: Juan Pérez\)_\n"
        "└ 🆔 Carné de identidad _\(ej: 85010112345\)_\n\n"
        "✅ Los contactos verificados tienen badge verde\n"
        "⚠️ Los contactos reportados se marcan visiblemente\n\n"
        "📲 *También disponible como app Android:*\n"
        "[⬇️ Descargar APK](https://github.com/YoandryF/guia-telefonica-root-app/releases/latest)\n\n"
        "_Base de datos colaborativa — tu aporte importa_ 🤝"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔍 Buscar", switch_inline_query_current_chat=""),
            InlineKeyboardButton("📋 Ver lista", callback_data="cmd_listar"),
        ],
        [
            InlineKeyboardButton("➕ Agregar contacto", callback_data="cmd_agregar"),
            InlineKeyboardButton("📂 Categorías", callback_data="cmd_categorias"),
        ],
        [
            InlineKeyboardButton("📌 Mis contactos", callback_data="cmd_miscontactos"),
            InlineKeyboardButton("❓ Ayuda", callback_data="cmd_ayuda"),
        ],
    ]

    if es_admin(user.id):
        keyboard.append([
            InlineKeyboardButton("🔐 Pendientes", callback_data="cmd_pendientes"),
            InlineKeyboardButton("🚨 Reportes", callback_data="cmd_reportes"),
        ])

    await update.message.reply_text(mensaje, parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)


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
    """Listar contactos aprobados con paginación inline"""
    await update.message.chat.send_action("typing")
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
        contactos = [c for c in contactos if categoria_filtro in c.get('categoria_nombre', '').lower()]

    if not contactos:
        await update.message.reply_text("📭 No hay contactos aprobados aún.")
        return

    chat_id = str(update.effective_user.id)
    _cache_resultados[chat_id] = {'contactos': contactos, 'query': ''}

    await _mostrar_lista(update, context, contactos, pagina, query_texto='')


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buscar contactos con lista compacta paginada"""
    if not context.args:
        await update.message.reply_text(
            "🔍 Escribe el nombre, teléfono o CI a buscar:\n"
            "Ejemplo: `/buscar Juan` o simplemente escribe el texto",
            parse_mode="Markdown",
        )
        return

    await update.message.chat.send_action("typing")
    query = " ".join(context.args)
    contactos = db.buscar_contactos(query)

    if not contactos:
        await update.message.reply_text(f"🔍 Sin resultados para: *{query}*\n\nIntenta con otro término.", parse_mode="Markdown")
        return

    chat_id = str(update.effective_user.id)
    _cache_resultados[chat_id] = {'contactos': contactos, 'query': query}

    await _mostrar_lista(update, context, contactos, 1, query_texto=query)


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
    """Ver contactos registrados por este usuario con estado y detalle"""
    await update.message.chat.send_action("typing")
    chat_id = str(update.effective_user.id)
    contactos = db.get_contactos_por_creador(chat_id)

    if not contactos:
        await update.message.reply_text(
            "📭 No has registrado contactos aún.\n\n"
            "Usa /agregar para registrar uno.",
        )
        return

    texto = f"📌 *Tus contactos registrados ({len(contactos)}):*\n\n"
    for c in contactos:
        emoji = {"aprobado": "✅", "pendiente": "⏳", "rechazado": "❌"}.get(c["estado"], "❓")
        texto += f"{emoji} *{c['nombre']} {c['apellido']}*\n"
        texto += f"   📱 `{c['telefono']}`\n"
        if c.get('motivo_rechazo'):
            texto += f"   ❌ Motivo: _{c['motivo_rechazo']}_\n"
        texto += "\n"

    pendientes = sum(1 for c in contactos if c["estado"] == "pendiente")
    if pendientes:
        texto += f"_⏳ {pendientes} pendiente(s) de aprobación_"

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
    """Ver contactos pendientes con filtro y paginación (botones)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("\U0001f512 Solo el administrador puede usar este comando.")
        return

    # Filtro opcional
    filtro = " ".join(context.args) if context.args else None
    contactos = db.get_contactos_pendientes()

    if filtro:
        f = filtro.lower()
        contactos = [c for c in contactos if f in c.get('nombre','').lower() or f in c.get('apellido','').lower() or f in c.get('telefono','') or f in (c.get('ci') or '')]

    if not contactos:
        msg = "\u2705 No hay contactos pendientes"
        if filtro:
            msg += f" que coincidan con \"{filtro}\""
        await update.message.reply_text(msg)
        return

    # Paginación: 5 por mensaje
    total = len(contactos)
    pagina = context.user_data.get('pend_pagina', 0)
    por_pagina = 5
    inicio = pagina * por_pagina
    fin = min(inicio + por_pagina, total)
    lote = contactos[inicio:fin]

    header = f"\u23f3 *Pendientes ({inicio+1}-{fin} de {total})*"
    if filtro:
        header += f" — filtro: \"{filtro}\""
    await update.message.reply_text(header, parse_mode="Markdown")

    for c in lote:
        texto = (
            f"\U0001f464 *{c['nombre']} {c['apellido']}*\n"
            f"\U0001f4f1 `{c['telefono']}`\n"
        )
        if c.get('direccion'):
            texto += f"\U0001f4cd {c['direccion']}\n"
        if c.get('ci'):
            texto += f"\U0001f194 CI: {c['ci']}\n"

        keyboard = [
            [
                InlineKeyboardButton("\u2705 Aprobar", callback_data=f"aprobar_{c['id'][:8]}"),
                InlineKeyboardButton("\u274c Rechazar", callback_data=f"rechazar_{c['id'][:8]}"),
            ],
            [
                InlineKeyboardButton("\U0001f5d1 Eliminar", callback_data=f"eliminar_{c['id'][:8]}"),
            ],
        ]
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Botones de navegación
    nav = []
    if inicio > 0:
        nav.append(InlineKeyboardButton("\u2b05 Anterior", callback_data="pend_prev"))
    if fin < total:
        nav.append(InlineKeyboardButton("Siguiente \u27a1", callback_data="pend_next"))
    if nav:
        await update.message.reply_text(f"P\u00e1gina {pagina+1}/{(total+por_pagina-1)//por_pagina}", reply_markup=InlineKeyboardMarkup([nav]))


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejar clicks en botones inline"""
    query = update.callback_query
    await query.answer()

    data = query.data
    admin = es_admin(query.from_user.id)

    # Callbacks PÚBLICOS (sin guard de admin)
    if data.startswith("pg_"):
        partes = data.split("_", 2)
        q = partes[1] if len(partes) > 1 else ""
        pagina = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 1
        chat_id = str(query.from_user.id)
        cache = _cache_resultados.get(chat_id)
        if not cache:
            await query.answer("⚠️ Sesión expirada. Busca de nuevo.", show_alert=True)
            return
        await _mostrar_lista(query, context, cache['contactos'], pagina, query_texto=cache.get('query', ''), editar=True)
        return

    elif data == "cmd_listar":
        contactos = db.get_contactos_aprobados()
        if not contactos:
            await query.edit_message_text("📭 No hay contactos aprobados aún.")
            return
        chat_id = str(query.from_user.id)
        _cache_resultados[chat_id] = {'contactos': contactos, 'query': ''}
        total = len(contactos)
        total_pags = max(1, (total + 9) // 10)
        texto, markup = _formato_lista_compacta(contactos[:10], 1, total, 1, total_pags, '')
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=markup)
        return

    elif data == "cmd_agregar":
        await query.edit_message_text(
            "✏️ Para registrar un contacto usa:\n\n"
            "`/agregar Nombre, Apellido, Teléfono`\n\n"
            "Ejemplo: `/agregar Juan, Pérez, 55551234`",
            parse_mode="Markdown",
        )
        return

    elif data == "cmd_categorias":
        cats = db.get_categorias()
        if not cats:
            await query.edit_message_text("📂 No hay categorías configuradas.")
            return
        texto = "📂 *Categorías disponibles:*\n\n"
        for cat in cats:
            texto += f"  {cat.get('icono', '📋')} {cat['nombre']}\n"
        await query.edit_message_text(texto, parse_mode="Markdown")
        return

    elif data == "cmd_miscontactos":
        chat_id = str(query.from_user.id)
        contactos = db.get_contactos_por_creador(chat_id)
        if not contactos:
            await query.edit_message_text("📭 No has registrado contactos aún.\n\nUsa /agregar para registrar uno.")
            return
        texto = f"📌 *Tus contactos ({len(contactos)}):*\n\n"
        for c in contactos:
            emoji = {"aprobado": "✅", "pendiente": "⏳", "rechazado": "❌"}.get(c["estado"], "❓")
            texto += f"{emoji} *{c['nombre']} {c['apellido']}* — `{c['telefono']}`\n"
        await query.edit_message_text(texto, parse_mode="Markdown")
        return

    elif data == "cmd_ayuda":
        await query.edit_message_text(
            "📖 *Cómo usar la Guía Telefónica:*\n\n"
            "🔍 Escribe el nombre o número directamente\n"
            "📋 /listar — ver todos\n"
            "➕ /agregar — registrar contacto\n"
            "📌 /miscontactos — mis registros\n"
            "⚠️ /reportar — reportar número\n"
            "👍 /avalar — avalar contacto\n"
            "📂 /categorias — ver categorías\n"
            "🚫 /listanegra — contactos reportados\n",
            parse_mode="Markdown",
        )
        return

    elif data in ("cmd_pendientes", "cmd_reportes"):
        if not admin:
            await query.answer("🔒 Solo admins", show_alert=True)
            return
        cmd = "pendientes" if data == "cmd_pendientes" else "reportes"
        await query.edit_message_text(f"Usa /{cmd} para ver la lista.")
        return

    elif data == "cancelar":
        await query.edit_message_text("❌ Operación cancelada.")
        return

    elif data.startswith("reclamo_"):
        if not admin:
            await query.edit_message_text("🔒 Solo el administrador.")
            return
        partes = data.split("_")
        accion = partes[1]  # aceptar o rechazar
        reclamo_id = partes[2]
        try:
            estado = "aceptado" if accion == "aceptar" else "rechazado"
            db.client.table("reclamos").update({"estado": estado}).ilike("id", f"{reclamo_id}%").execute()
            await query.edit_message_text(f"{'✅ Reclamo aceptado' if accion == 'aceptar' else '❌ Reclamo rechazado'}")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
        return

    # A partir de aquí: solo admins
    if not admin:
        await query.edit_message_text("🔒 Solo el administrador.")
        return

    if data.startswith("aprobar_"):
        contacto_id = data.replace("aprobar_", "")
        resultado = db.aprobar_contacto(contacto_id, aprobado_por=str(query.from_user.id))
        if resultado.get("error"):
            await query.edit_message_text(f"❌ Error: {resultado['error']}")
        else:
            contacto = resultado.get("data", {})
            await query.edit_message_text(f"✅ *Aprobado:* {contacto.get('nombre', '')} {contacto.get('apellido', '')}", parse_mode="Markdown")
            # Notificar al creador
            if contacto.get("creado_por") and contacto.get("creado_desde") == "telegram":
                try:
                    await query.bot.send_message(chat_id=contacto["creado_por"], text=f"✅ Tu contacto *{contacto['nombre']} {contacto['apellido']}* fue aprobado!", parse_mode="Markdown")
                except Exception:
                    pass

    elif data.startswith("rechazar_"):
        contacto_id = data.replace("rechazar_", "")
        context.user_data['rechazar_id'] = contacto_id
        await query.edit_message_text("❌ Escribe el motivo de rechazo (envía un mensaje):")

    elif data.startswith("eliminar_"):
        contacto_id = data.replace("eliminar_", "")
        contacto = db.buscar_por_id_o_telefono(contacto_id)
        if contacto:
            db.client.table("contactos").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", contacto["id"]).execute()
            await query.edit_message_text(f"🗑 *Eliminado:* {contacto['nombre']} {contacto['apellido']}", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ No encontrado.")

    elif data.startswith("confirmar_del_"):
        contacto_id = data.replace("confirmar_del_", "")
        contacto = db.buscar_por_id_o_telefono(contacto_id)
        if contacto:
            db.client.table("contactos").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", contacto["id"]).execute()
            await query.edit_message_text(f"🗑 *Eliminado:* {contacto['nombre']} {contacto['apellido']}", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ No encontrado.")

    elif data == "cancelar":
        await query.edit_message_text("❌ Operación cancelada.")



    elif data.startswith("cfg_edit_"):
        clave = data.replace("cfg_edit_", "")
        context.user_data['cfg_edit_clave'] = clave
        await query.edit_message_text(f"✏️ Escribe el nuevo valor para `{clave}`:", parse_mode="Markdown")


    elif data == "pend_prev":
        context.user_data['pend_pagina'] = max(0, context.user_data.get('pend_pagina', 0) - 1)
        await query.edit_message_text(f"⬅️ Usa /pendientes para ver página {context.user_data['pend_pagina']+1}")

    elif data == "pend_next":
        context.user_data['pend_pagina'] = context.user_data.get('pend_pagina', 0) + 1
        await query.edit_message_text(f"➡️ Usa /pendientes para ver página {context.user_data['pend_pagina']+1}")


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




async def handle_texto_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capturar texto libre del admin (motivo de rechazo, config, etc.)"""
    # Editar configuración pendiente
    if 'cfg_edit_clave' in context.user_data:
        clave = context.user_data.pop('cfg_edit_clave')
        valor = update.message.text.strip()
        try:
            db.client.table("configuracion").update({"valor": valor}).eq("clave", clave).execute()
            await update.message.reply_text(f"\u2705 `{clave}` = *{valor}*", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"\u274c Error: {e}")
        return

    # Motivo de rechazo pendiente
    if 'rechazar_id' in context.user_data:
        contacto_id = context.user_data.pop('rechazar_id')
        motivo = update.message.text.strip()
        resultado = db.rechazar_contacto(contacto_id, motivo=motivo)
        if resultado.get("error"):
            await update.message.reply_text(f"❌ Error: {resultado['error']}")
        else:
            contacto = resultado.get("data", {})
            await update.message.reply_text(
                f"❌ *Rechazado:* {contacto.get('nombre', '')} {contacto.get('apellido', '')}\n📝 Motivo: {motivo}",
                parse_mode="Markdown",
            )
            if contacto.get("creado_por") and contacto.get("creado_desde") == "telegram":
                try:
                    await context.bot.send_message(chat_id=contacto["creado_por"], text=f"❌ Tu contacto *{contacto['nombre']} {contacto['apellido']}* fue rechazado.\nMotivo: {motivo}", parse_mode="Markdown")
                except Exception:
                    pass
        return



async def handle_texto_libre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Texto libre para TODOS los usuarios — busca número o nombre directamente"""
    texto = update.message.text.strip()

    # Si parece número de teléfono → mostrar detalle
    limpio = texto.replace('-', '').replace(' ', '').replace('+', '')
    if limpio.isdigit() and len(limpio) >= 5:
        await update.message.chat.send_action("typing")
        contacto = db.buscar_por_id_o_telefono(texto)
        if contacto:
            admin = es_admin(update.effective_user.id)
            detalle = formatear_contacto(contacto, mostrar_id=admin)
            if admin:
                keyboard = [[InlineKeyboardButton("🗑 Eliminar", callback_data=f"confirmar_del_{contacto['id'][:8]}")]]
                await update.message.reply_text(detalle, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(detalle, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"❌ No encontré ningún contacto con `{texto}`\n\n"
                f"_¿Quieres registrarlo? Usa /agregar_",
                parse_mode="Markdown",
            )
        return

    # Si tiene 3+ chars → buscar como nombre
    if len(texto) >= 3:
        await update.message.chat.send_action("typing")
        contactos = db.buscar_contactos(texto)
        if contactos:
            chat_id = str(update.effective_user.id)
            _cache_resultados[chat_id] = {'contactos': contactos, 'query': texto}
            await _mostrar_lista(update, context, contactos, 1, query_texto=texto)
        else:
            await update.message.reply_text(
                f"🔍 Sin resultados para *{texto}*\n\n"
                f"Intenta con otro término o usa /listar para ver todos.",
                parse_mode="Markdown",
            )


async def listanegra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista negra compacta — contactos reportados"""
    await update.message.chat.send_action("typing")
    contactos = db.get_contactos_aprobados()
    reportados = []
    for c in contactos:
        info = db.get_info_reportes(c['id'])
        if info['mostrar']:
            reportados.append((c, info))

    if not reportados:
        await update.message.reply_text("✅ No hay contactos en la lista negra.")
        return

    admin = es_admin(update.effective_user.id)
    texto = f"⚠️ *Lista Negra — {len(reportados)} contactos*\n\n"

    for i, (c, info) in enumerate(reportados[:20], 1):
        nombre = f"{c['nombre']} {c['apellido']}"
        if len(nombre) > 22: nombre = nombre[:20] + "…"
        estado = "🔴 Verificado" if info['verificado'] else f"🟡 {info['pendientes']} reportes"
        texto += f"*{i}.* {nombre.upper()}\n   📱 `{c['telefono']}` — {estado}\n\n"

    if len(reportados) > 20:
        texto += f"_... y {len(reportados) - 20} más_"

    texto += "_Escribe el número para ver detalles_"

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
        # Mostrar últimos 5 contactos para elegir
        contactos = db.get_contactos_aprobados()[-5:]
        if not contactos:
            await update.message.reply_text("No hay contactos.")
            return
        await update.message.reply_text(
            "🗑️ *¿Qué contacto eliminar?*\n\nElige uno o usa `/eliminar teléfono`:",
            parse_mode="Markdown",
        )
        for c in contactos:
            keyboard = [[InlineKeyboardButton(f"🗑️ {c['nombre']} {c['apellido']} - {c['telefono']}", callback_data=f"confirmar_del_{c['id'][:8]}")]]
            await update.message.reply_text(
                f"👤 {c['nombre']} {c['apellido']} — 📱 {c['telefono']}",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    identificador = " ".join(context.args)
    contacto = db.buscar_por_id_o_telefono(identificador)

    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado. Verifica el teléfono o ID.")
        return

    # Confirmar con botones
    nombre = f"{contacto['nombre']} {contacto['apellido']}"
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_del_{contacto['id'][:8]}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar"),
        ]
    ]
    await update.message.reply_text(
        f"⚠️ *¿Eliminar este contacto?*\n\n"
        f"👤 {nombre}\n📱 {contacto['telefono']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
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
    """Cambiar configuraci\u00f3n (solo owner). Uso: /setconfig clave valor"""
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


# ============================================
# VERIFICACIÓN DE CONTACTO
# ============================================

async def verificarme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/verificarme teléfono - Solicitar verificación (soy el dueño)"""
    if not context.args:
        await update.message.reply_text("Usa: `/verificarme teléfono`\nEl teléfono debe coincidir con uno que tú registraste.", parse_mode="Markdown")
        return
    telefono = context.args[0]
    chat_id = str(update.effective_user.id)
    contacto = db.buscar_por_id_o_telefono(telefono)
    if not contacto:
        await update.message.reply_text("\u274c Contacto no encontrado.")
        return
    if contacto.get('creado_por') != chat_id:
        await update.message.reply_text("\u274c Solo puedes verificar contactos que t\u00fa registraste.")
        return
    try:
        db.client.table("contactos").update({"verificado": True}).eq("id", contacto["id"]).execute()
        await update.message.reply_text(f"\u2705 *Contacto verificado:* {contacto['nombre']} {contacto['apellido']}\n\nAhora tiene badge verde \u2705", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"\u274c Error: {e}")


async def verificar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/verificar teléfono - Admin verifica manualmente"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("\U0001f512 Solo admin.")
        return
    if not context.args:
        await update.message.reply_text("Usa: `/verificar teléfono`", parse_mode="Markdown")
        return
    contacto = db.buscar_por_id_o_telefono(context.args[0])
    if not contacto:
        await update.message.reply_text("\u274c Contacto no encontrado.")
        return
    try:
        db.client.table("contactos").update({"verificado": True}).eq("id", contacto["id"]).execute()
        await update.message.reply_text(f"\u2705 *Verificado:* {contacto['nombre']} {contacto['apellido']} \u2705", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"\u274c Error: {e}")


# ============================================
# AVALES Y RECLAMOS
# ============================================

async def avalar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Avalar un contacto (es legítimo). Uso: /avalar teléfono"""
    if not context.args:
        await update.message.reply_text("Usa: `/avalar teléfono`\nEjemplo: `/avalar 51001508`", parse_mode="Markdown")
        return
    contacto = db.buscar_por_id_o_telefono(context.args[0])
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.")
        return
    try:
        db.client.table("avales").insert({"contacto_id": contacto["id"], "avalado_por": str(update.effective_user.id)}).execute()
        await update.message.reply_text(f"👍 *Aval registrado* para {contacto['nombre']} {contacto['apellido']}", parse_mode="Markdown")
    except Exception as e:
        if "duplicate" in str(e).lower():
            await update.message.reply_text("⚠️ Ya avalaste este contacto.")
        else:
            await update.message.reply_text(f"❌ Error: {e}")


async def reclamar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reclamar un contacto reportado. Uso: /reclamar teléfono mensaje"""
    if len(context.args) < 2:
        await update.message.reply_text("Usa: `/reclamar teléfono tu mensaje`\nEjemplo: `/reclamar 51001508 Soy el dueño, es legítimo`", parse_mode="Markdown")
        return
    contacto = db.buscar_por_id_o_telefono(context.args[0])
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.")
        return
    mensaje = " ".join(context.args[1:])
    try:
        db.client.table("reclamos").insert({"contacto_id": contacto["id"], "reclamante_id": str(update.effective_user.id), "mensaje": mensaje}).execute()
        await update.message.reply_text("⚖️ *Reclamo enviado.* Un admin lo revisará.", parse_mode="Markdown")
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"⚖️ *Nuevo reclamo*\n\n👤 {contacto['nombre']} {contacto['apellido']}\n📱 {contacto['telefono']}\n💬 {mensaje}\n\nUsa /reclamos para revisar", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def reclamos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver reclamos pendientes (admin)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo admin.")
        return
    try:
        response = db.client.table("reclamos").select("*, contactos(nombre, apellido, telefono)").eq("estado", "pendiente").order("fecha").execute()
        if not response.data:
            await update.message.reply_text("✅ No hay reclamos pendientes.")
            return
        for r in response.data[:10]:
            contacto = r.get("contactos", {})
            nombre = f"{contacto.get('nombre','')} {contacto.get('apellido','')}"
            keyboard = [[
                InlineKeyboardButton("✅ Aceptar", callback_data=f"reclamo_aceptar_{r['id'][:8]}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"reclamo_rechazar_{r['id'][:8]}"),
            ]]
            await update.message.reply_text(
                f"⚖️ *Reclamo*\n👤 {nombre} ({contacto.get('telefono','')})\n💬 {r.get('mensaje','')}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard),
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ============================================
# COMANDOS DE EXPORTACIÓN/IMPORTACIÓN
# ============================================


async def banear_reportador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Banear un reportador. Uso: /banear_reportador identificador [motivo]"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador.")
        return
    if not context.args:
        await update.message.reply_text("Usa: `/banear_reportador dispositivo_id|chat_id [motivo]`", parse_mode="Markdown")
        return
    identificador = context.args[0]
    motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Abuso de reportes"
    try:
        db.client.table("usuarios_baneados").insert({"identificador": identificador, "motivo": motivo, "baneado_por": str(update.effective_user.id)}).execute()
        await update.message.reply_text(f"🚫 *Reportador baneado*\nID: `{identificador}`\nMotivo: {motivo}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def desbanear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desbanear reportador. Uso: /desbanear identificador"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador.")
        return
    if not context.args:
        await update.message.reply_text("Usa: `/desbanear identificador`", parse_mode="Markdown")
        return
    identificador = context.args[0]
    try:
        db.client.table("usuarios_baneados").delete().eq("identificador", identificador).execute()
        await update.message.reply_text(f"✅ Reportador `{identificador}` desbaneado.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")



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

    # Avales y reclamos
    app.add_handler(CommandHandler("avalar", avalar))
    app.add_handler(CommandHandler("reclamar", reclamar))
    app.add_handler(CommandHandler("reclamos", reclamos))

    # Comandos export/import
    app.add_handler(CommandHandler("exportar", exportar))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.User(int(ADMIN_CHAT_ID)), importar_archivo))

    # Comandos reportes (admin)
    app.add_handler(CommandHandler("reportes", reportes))
    app.add_handler(CommandHandler("desestimar", desestimar))
    app.add_handler(CommandHandler("banear_reportador", banear_reportador))
    app.add_handler(CommandHandler("desbanear", desbanear))

    return app


async def _set_commands(app):
    """Actualizar los comandos visibles en el menú de Telegram"""
    from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeAllGroupChats
    comandos_usuario = [
        BotCommand("start", "👋 Inicio y bienvenida"),
        BotCommand("agregar", "➕ Registrar un contacto"),
        BotCommand("miscontactos", "📌 Mis contactos registrados"),
        BotCommand("categorias", "📂 Ver categorías"),
        BotCommand("reportar", "⚠️ Reportar un contacto"),
        BotCommand("avalar", "👍 Avalar un contacto legítimo"),
        BotCommand("listanegra", "🚫 Ver contactos reportados"),
        BotCommand("ayuda", "❓ Ayuda"),
    ]
    await app.bot.set_my_commands(comandos_usuario, scope=BotCommandScopeDefault())


def main():
    """Iniciar el bot (para uso local)"""
    app = create_app()
    if not app:
        return

    logger.info("Iniciando bot en modo polling (local)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
