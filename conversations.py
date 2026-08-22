"""
Flujos interactivos (ConversationHandler) para /agregar y /reportar.
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, ContextTypes, filters
from supabase_service import SupabaseService

db = SupabaseService()

# Provincias de Cuba ordenadas
PROVINCIAS = [
    "Pinar del Río", "Artemisa", "La Habana", "Mayabeque",
    "Matanzas", "Villa Clara", "Cienfuegos", "Sancti Spíritus",
    "Ciego de Ávila", "Camagüey", "Las Tunas", "Holguín",
    "Granma", "Santiago de Cuba", "Guantánamo", "Isla de la Juventud",
]

MUNICIPIOS = {
    "Pinar del Río":       ["Consolación del Sur","Guane","La Palma","Los Palacios","Mantua","Minas de Matahambre","Pinar del Río","San Juan y Martínez","San Luis","Sandino","Viñales"],
    "Artemisa":            ["Alquízar","Artemisa","Bauta","Caimito","Candelaria","Güira de Melena","Guanajay","Mariel","San Antonio de los Baños","San Cristóbal","Bahía Honda"],
    "La Habana":           ["Arroyo Naranjo","Boyeros","Centro Habana","Cerro","Cotorro","Diez de Octubre","Guanabacoa","Habana del Este","Habana Vieja","La Lisa","Marianao","Playa","Plaza de la Revolución","Regla","San Miguel del Padrón"],
    "Mayabeque":           ["Batabanó","Bejucal","Güines","Jaruco","Madruga","Melena del Sur","Nueva Paz","Quivicán","San José de las Lajas","San Nicolás de Bari","Santa Cruz del Norte"],
    "Matanzas":            ["Calimete","Cárdenas","Ciénaga de Zapata","Colón","Jagüey Grande","Jovellanos","Limonar","Los Arabos","Martí","Matanzas","Pedro Betancourt","Perico","Unión de Reyes"],
    "Villa Clara":         ["Caibarién","Camajuaní","Cifuentes","Corralillo","Encrucijada","Manicaragua","Placetas","Quemado de Güines","Ranchuelo","Remedios","Sagua la Grande","Santa Clara","Santo Domingo"],
    "Cienfuegos":          ["Abreus","Aguada de Pasajeros","Cienfuegos","Cruces","Cumanayagua","Lajas","Palmira","Rodas"],
    "Sancti Spíritus":     ["Cabaiguán","Fomento","Jatibonico","La Sierpe","Sancti Spíritus","Trinidad","Taguasco","Yaguajay"],
    "Ciego de Ávila":      ["Baraguá","Bolivia","Chambas","Ciego de Ávila","Ciro Redondo","Florencia","Majagua","Morón","Primero de Enero","Venezuela"],
    "Camagüey":            ["Camagüey","Carlos Manuel de Céspedes","Esmeralda","Florida","Guáimaro","Jimaguayú","Minas","Najasa","Nuevitas","Santa Cruz del Sur","Sibanicú","Sierra de Cubitas","Vertientes"],
    "Las Tunas":           ["Amancio","Colombia","Jesús Menéndez","JobaBo","Las Tunas","Majibacoa","Manatí","Puerto Padre"],
    "Holguín":             ["Antilla","Báguanos","Banes","Cacocum","Calixto García","Cueto","Frank País","Gibara","Holguín","Mayarí","Moa","Rafael Freyre","Sagua de Tánamo","Urbano Noris"],
    "Granma":              ["Bartolomé Masó","Bayamo","Buey Arriba","Campechuela","Cauto Cristo","Guisa","Jiguaní","Manzanillo","Media Luna","Niquero","Pilón","Río Cauto","Yara"],
    "Santiago de Cuba":    ["Contramaestre","Guamá","Julio Antonio Mella","Palma Soriano","San Luis","Santiago de Cuba","Segundo Frente","Sierra Maestra","Songo-La Maya","Tercer Frente"],
    "Guantánamo":          ["Baracoa","Caimanera","El Salvador","Guantánamo","Imías","Maisí","Manuel Tames","Niceto Pérez","San Antonio del Sur","Yateras"],
    "Isla de la Juventud": ["Isla de la Juventud"],
}

# Estados de la conversación
AGR_NOMBRE, AGR_APELLIDO, AGR_TELEFONO, AGR_PROVINCIA, AGR_MUNICIPIO = range(5)

# ─────────────────────────────────────────────────────────────────────────────
# /agregar
# ─────────────────────────────────────────────────────────────────────────────

def _teclado_provincias():
    filas = []
    for i in range(0, len(PROVINCIAS), 2):
        fila = PROVINCIAS[i:i+2]
        filas.append(fila)
    filas.append(["/cancelar"])
    return ReplyKeyboardMarkup(filas, resize_keyboard=True, one_time_keyboard=True)

def _teclado_municipios(provincia: str):
    munis = MUNICIPIOS.get(provincia, [])
    filas = []
    for i in range(0, len(munis), 2):
        filas.append(munis[i:i+2])
    filas.append(["/cancelar"])
    return ReplyKeyboardMarkup(filas, resize_keyboard=True, one_time_keyboard=True)


async def agregar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicio de /agregar — si tiene args procesa directo; si no, flujo interactivo."""
    if context.args:
        texto  = " ".join(context.args)
        partes = [p.strip() for p in texto.split(",")]
        if len(partes) >= 5:
            # Formato: Nombre, Apellido, Teléfono, Provincia, Municipio
            return await _registrar_directo(update, context, partes)
        else:
            await update.message.reply_text(
                "⚠️ Formato directo:\n`/agregar Nombre, Apellido, Teléfono, Provincia, Municipio`\n\n"
                "O usa /agregar sin argumentos para el flujo interactivo.",
                parse_mode="Markdown",
            )
            return ConversationHandler.END

    await update.message.reply_text(
        "✏️ *Nuevo contacto — Paso 1/5*\n\n¿Cuál es el *nombre*?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["/cancelar"]], resize_keyboard=True),
    )
    return AGR_NOMBRE


async def agregar_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 2:
        await update.message.reply_text("⚠️ Mínimo 2 caracteres. Intenta de nuevo:")
        return AGR_NOMBRE
    context.user_data['nombre'] = nombre
    await update.message.reply_text(
        f"✅ Nombre: *{nombre}*\n\n*Paso 2/5* — ¿Cuál es el *apellido*?",
        parse_mode="Markdown",
    )
    return AGR_APELLIDO


async def agregar_apellido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    apellido = update.message.text.strip()
    if len(apellido) < 2:
        await update.message.reply_text("⚠️ Mínimo 2 caracteres. Intenta de nuevo:")
        return AGR_APELLIDO
    context.user_data['apellido'] = apellido
    await update.message.reply_text(
        f"✅ Apellido: *{apellido}*\n\n*Paso 3/5* — ¿Cuál es el *teléfono*?",
        parse_mode="Markdown",
    )
    return AGR_TELEFONO


async def agregar_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telefono = update.message.text.strip().replace("-", "").replace(" ", "")
    if not telefono.isdigit() or len(telefono) < 7:
        await update.message.reply_text("⚠️ Teléfono inválido — solo dígitos, mínimo 7. Intenta de nuevo:")
        return AGR_TELEFONO
    context.user_data['telefono'] = telefono
    await update.message.reply_text(
        f"✅ Teléfono: *{telefono}*\n\n*Paso 4/5* — Selecciona la *provincia*:",
        parse_mode="Markdown",
        reply_markup=_teclado_provincias(),
    )
    return AGR_PROVINCIA


async def agregar_provincia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    provincia = update.message.text.strip()
    if provincia not in PROVINCIAS:
        await update.message.reply_text(
            "⚠️ Selecciona una provincia del teclado:",
            reply_markup=_teclado_provincias(),
        )
        return AGR_PROVINCIA
    context.user_data['provincia'] = provincia
    await update.message.reply_text(
        f"✅ Provincia: *{provincia}*\n\n*Paso 5/5* — Selecciona el *municipio*:",
        parse_mode="Markdown",
        reply_markup=_teclado_municipios(provincia),
    )
    return AGR_MUNICIPIO


async def agregar_municipio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    municipio = update.message.text.strip()
    provincia = context.user_data.get('provincia', '')
    if municipio not in MUNICIPIOS.get(provincia, []):
        await update.message.reply_text(
            "⚠️ Selecciona un municipio del teclado:",
            reply_markup=_teclado_municipios(provincia),
        )
        return AGR_MUNICIPIO
    context.user_data['municipio'] = municipio
    return await _finalizar_registro(update, context)


async def _finalizar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    resultado = db.registrar_contacto(
        nombre     = data['nombre'],
        apellido   = data['apellido'],
        telefono   = data['telefono'],
        provincia  = data.get('provincia'),
        municipio  = data.get('municipio'),
        creado_por = str(update.effective_user.id),
        creado_desde = "telegram",
    )
    if resultado.get("error"):
        err = str(resultado["error"])
        if "duplicate" in err.lower():
            await update.message.reply_text(
                "⚠️ Ese teléfono ya está registrado.",
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            await update.message.reply_text(f"❌ Error: {err}", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(
            f"✅ *Contacto enviado para aprobación*\n\n"
            f"👤 {data['nombre']} {data['apellido']}\n"
            f"📱 {data['telefono']}\n"
            f"📍 {data.get('municipio')}, {data.get('provincia')}\n\n"
            f"⏳ El administrador lo revisará pronto.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        # Notificar al admin
        from utils.helpers import ADMIN_CHAT_ID
        if ADMIN_CHAT_ID:
            try:
                from telegram import Bot
                import os
                bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
                await bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=(
                        f"📥 *Nuevo contacto pendiente*\n\n"
                        f"👤 {data['nombre']} {data['apellido']}\n"
                        f"📱 `{data['telefono']}`\n"
                        f"📍 {data.get('municipio')}, {data.get('provincia')}\n"
                        f"Por: @{update.effective_user.username or update.effective_user.first_name}\n\n"
                        f"Usa /pendientes para aprobar."
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    context.user_data.clear()
    return ConversationHandler.END


async def _registrar_directo(update: Update, context: ContextTypes.DEFAULT_TYPE, partes: list):
    """Registro rápido desde una línea de texto."""
    nombre, apellido, telefono = partes[0], partes[1], partes[2]
    provincia = partes[3] if len(partes) > 3 else None
    municipio = partes[4] if len(partes) > 4 else None

    if provincia and provincia not in PROVINCIAS:
        await update.message.reply_text(f"⚠️ Provincia no reconocida: *{provincia}*", parse_mode="Markdown")
        return ConversationHandler.END

    resultado = db.registrar_contacto(
        nombre=nombre, apellido=apellido, telefono=telefono,
        provincia=provincia, municipio=municipio,
        creado_por=str(update.effective_user.id), creado_desde="telegram",
    )
    if resultado.get("error"):
        err = str(resultado["error"])
        msg = "⚠️ Teléfono ya registrado." if "duplicate" in err.lower() else f"❌ Error: {err}"
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(
            f"✅ *Registrado*\n👤 {nombre} {apellido} — 📱 {telefono}\n⏳ Pendiente de aprobación.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# /reportar
# ─────────────────────────────────────────────────────────────────────────────
REP_CONTACTO, REP_MOTIVO, REP_DESCRIPCION = range(10, 13)

MOTIVOS_TECLADO = [
    ['📞 numero_incorrecto', '❌ no_existe'],
    ['📢 spam',              '🔄 duplicado'],
    ['📋 otro'],
]


async def reportar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) >= 2:
        return await _procesar_reporte(update, context, context.args[0], context.args[1],
                                       " ".join(context.args[2:]) if len(context.args) > 2 else None)
    await update.message.reply_text(
        "⚠️ *Reportar — Paso 1/3*\n\n¿Cuál es el *teléfono* a reportar?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["/cancelar"]], resize_keyboard=True),
    )
    return REP_CONTACTO


async def reportar_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identificador = update.message.text.strip()
    contacto = db.buscar_por_id_o_telefono(identificador)
    if not contacto:
        await update.message.reply_text("❌ No encontrado. Verifica el teléfono:")
        return REP_CONTACTO
    context.user_data['contacto_id']     = contacto['id']
    context.user_data['contacto_nombre'] = f"{contacto['nombre']} {contacto['apellido']}"
    # Mostrar info del contacto + cuántos reportes tiene
    n_rep = contacto.get('score_riesgo', 0) or 0
    badge = f"⚠️ Ya tiene {n_rep} reporte(s)\n" if n_rep else ""
    await update.message.reply_text(
        f"👤 *{contacto['nombre']} {contacto['apellido']}* (`{contacto['telefono']}`)\n{badge}\n"
        f"¿Cuál es el *motivo*?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(MOTIVOS_TECLADO, resize_keyboard=True, one_time_keyboard=True),
    )
    return REP_MOTIVO


async def reportar_motivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto  = update.message.text.strip()
    motivo = texto.split(" ", 1)[-1] if " " in texto else texto
    motivos_validos = ['numero_incorrecto', 'no_existe', 'spam', 'duplicado', 'otro']
    if motivo not in motivos_validos:
        await update.message.reply_text("⚠️ Selecciona un motivo del teclado:")
        return REP_MOTIVO
    context.user_data['motivo'] = motivo
    await update.message.reply_text(
        "¿Alguna *descripción* adicional? (o escribe *no*)",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["/cancelar", "no"]], resize_keyboard=True),
    )
    return REP_DESCRIPCION


async def reportar_descripcion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto       = update.message.text.strip()
    descripcion = None if texto.lower() == 'no' else texto
    data        = context.user_data
    return await _procesar_reporte(update, context, data['contacto_id'], data['motivo'], descripcion)


async def _procesar_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            identificador: str, motivo: str, descripcion: str = None):
    motivos_validos = ['numero_incorrecto', 'no_existe', 'spam', 'duplicado', 'otro']
    if motivo not in motivos_validos:
        await update.message.reply_text(
            f"⚠️ Motivo inválido. Usa: {', '.join(motivos_validos)}",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    contacto = db.buscar_por_id_o_telefono(identificador)
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    resultado = db.reportar_contacto(
        contacto_id  = contacto['id'],
        motivo       = motivo,
        descripcion  = descripcion,
        reportado_por= str(update.effective_user.id),
    )
    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(
            "⚠️ *Reporte enviado.* Gracias por informar.\n\nEl administrador lo revisará pronto.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
        from utils.helpers import ADMIN_CHAT_ID
        if ADMIN_CHAT_ID:
            try:
                from telegram import Bot
                import os
                bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
                nombre = f"{contacto['nombre']} {contacto.get('apellido','')}"
                await bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=(
                        f"🚨 *Nuevo reporte*\n\n"
                        f"👤 {nombre} (`{contacto['telefono']}`)\n"
                        f"⚠️ Motivo: {motivo}\n"
                        f"💬 {descripcion or 'Sin descripción'}\n"
                        f"Por: @{update.effective_user.username or update.effective_user.first_name}"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# Cancelar
# ─────────────────────────────────────────────────────────────────────────────
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────────────────────
def get_agregar_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("agregar", agregar_inicio)],
        states={
            AGR_NOMBRE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_nombre)],
            AGR_APELLIDO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_apellido)],
            AGR_TELEFONO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_telefono)],
            AGR_PROVINCIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_provincia)],
            AGR_MUNICIPIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_municipio)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )


def get_reportar_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("reportar", reportar_inicio)],
        states={
            REP_CONTACTO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reportar_contacto)],
            REP_MOTIVO:      [MessageHandler(filters.TEXT & ~filters.COMMAND, reportar_motivo)],
            REP_DESCRIPCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, reportar_descripcion)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
