"""
Flujos interactivos (ConversationHandler) para /agregar y /reportar
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, ContextTypes, filters
from supabase_service import SupabaseService

db = SupabaseService()

# === /agregar interactivo ===
AGR_NOMBRE, AGR_APELLIDO, AGR_TELEFONO, AGR_DIRECCION, AGR_CI, AGR_CATEGORIA = range(6)

async def agregar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicio de /agregar — si tiene args, procesa directo; si no, inicia flujo"""
    if context.args:
        # Modo directo (1 línea)
        texto = " ".join(context.args)
        partes = [p.strip() for p in texto.split(",")]
        if len(partes) >= 3:
            return await _registrar_contacto(update, context, partes)
        else:
            await update.message.reply_text("⚠️ Formato: `/agregar Nombre, Apellido, Teléfono`", parse_mode="Markdown")
            return ConversationHandler.END

    # Modo interactivo
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
    await update.message.reply_text(f"✅ Nombre: *{nombre}*\n\n¿Cuál es el *apellido*?", parse_mode="Markdown")
    return AGR_APELLIDO

async def agregar_apellido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    apellido = update.message.text.strip()
    if len(apellido) < 2:
        await update.message.reply_text("⚠️ Mínimo 2 caracteres. Intenta de nuevo:")
        return AGR_APELLIDO
    context.user_data['apellido'] = apellido
    await update.message.reply_text(f"✅ Apellido: *{apellido}*\n\n¿Cuál es el *teléfono*?", parse_mode="Markdown")
    return AGR_TELEFONO

async def agregar_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telefono = update.message.text.strip()
    if len(telefono) < 5:
        await update.message.reply_text("⚠️ Mínimo 5 dígitos. Intenta de nuevo:")
        return AGR_TELEFONO
    context.user_data['telefono'] = telefono
    await update.message.reply_text(
        f"✅ Teléfono: *{telefono}*\n\n¿Cuál es la *dirección*?\n(Escribe *no* para omitir)",
        parse_mode="Markdown",
    )
    return AGR_DIRECCION

async def agregar_direccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    context.user_data['direccion'] = None if texto.lower() == 'no' else texto
    await update.message.reply_text(
        "¿Cuál es el *CI* (Carnet de Identidad)?\n(Escribe *no* para omitir)",
        parse_mode="Markdown",
    )
    return AGR_CI

async def agregar_ci(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    context.user_data['ci'] = None if texto.lower() == 'no' else texto

    # Obtener categorías para mostrar opciones
    categorias = db.get_categorias()
    if categorias:
        teclado = [[f"{c.get('icono','')} {c['nombre']}"] for c in categorias]
        teclado.append(["no"])
        await update.message.reply_text(
            "¿*Categoría*? (o escribe *no* para omitir)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(teclado, resize_keyboard=True, one_time_keyboard=True),
        )
        return AGR_CATEGORIA
    else:
        context.user_data['categoria_id'] = None
        return await _finalizar_registro(update, context)


async def agregar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto.lower() == 'no':
        context.user_data['categoria_id'] = None
    else:
        # Buscar categoría por nombre
        categorias = db.get_categorias()
        cat_id = None
        for c in categorias:
            if c['nombre'].lower() in texto.lower() or texto.lower() in c['nombre'].lower():
                cat_id = c['id']
                break
        context.user_data['categoria_id'] = cat_id
    return await _finalizar_registro(update, context)


async def _finalizar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    resultado = db.registrar_contacto(
        nombre=data['nombre'], apellido=data['apellido'], telefono=data['telefono'],
        direccion=data.get('direccion'), ci=data.get('ci'),
        creado_por=str(update.effective_user.id), creado_desde="telegram",
    )

    if resultado.get("error"):
        error = resultado["error"]
        if "duplicate" in str(error).lower():
            await update.message.reply_text("⚠️ Ese teléfono o CI ya está registrado.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text(f"❌ Error: {error}", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(
            f"✅ *Contacto registrado*\n\n👤 {data['nombre']} {data['apellido']}\n📱 {data['telefono']}\n\n⏳ Pendiente de aprobación.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
    context.user_data.clear()
    return ConversationHandler.END

async def _registrar_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE, partes: list):
    """Registrar el contacto en Supabase"""
    nombre = partes[0]
    apellido = partes[1]
    telefono = partes[2]
    direccion = partes[3] if len(partes) > 3 else None
    ci = partes[4] if len(partes) > 4 else None

    resultado = db.registrar_contacto(
        nombre=nombre, apellido=apellido, telefono=telefono,
        direccion=direccion, ci=ci,
        creado_por=str(update.effective_user.id), creado_desde="telegram",
    )

    if resultado.get("error"):
        error = resultado["error"]
        if "duplicate" in str(error).lower():
            await update.message.reply_text("⚠️ Ese teléfono o CI ya está registrado.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text(f"❌ Error: {error}", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(
            f"✅ *Contacto registrado*\n\n👤 {nombre} {apellido}\n📱 {telefono}\n\n⏳ Pendiente de aprobación.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
    context.user_data.clear()
    return ConversationHandler.END

# === /reportar interactivo ===
REP_CONTACTO, REP_MOTIVO, REP_DESCRIPCION = range(10, 13)

MOTIVOS = [
    ['📞 numero_incorrecto', '❌ no_existe'],
    ['📢 spam', '🔄 duplicado'],
    ['📋 otro'],
]

async def reportar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicio de /reportar"""
    if len(context.args) >= 2:
        # Modo directo
        identificador = context.args[0]
        motivo = context.args[1]
        descripcion = " ".join(context.args[2:]) if len(context.args) > 2 else None
        return await _procesar_reporte(update, context, identificador, motivo, descripcion)

    await update.message.reply_text(
        "⚠️ *Reportar contacto — Paso 1/3*\n\n¿Cuál es el *teléfono* del contacto a reportar?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["/cancelar"]], resize_keyboard=True),
    )
    return REP_CONTACTO

async def reportar_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identificador = update.message.text.strip()
    contacto = db.buscar_por_id_o_telefono(identificador)
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado. Verifica el teléfono e intenta de nuevo:")
        return REP_CONTACTO
    context.user_data['contacto_id'] = contacto['id']
    context.user_data['contacto_nombre'] = f"{contacto['nombre']} {contacto['apellido']}"
    await update.message.reply_text(
        f"👤 *{contacto['nombre']} {contacto['apellido']}* ({contacto['telefono']})\n\n¿Cuál es el *motivo*?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(MOTIVOS, resize_keyboard=True, one_time_keyboard=True),
    )
    return REP_MOTIVO

async def reportar_motivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    # Extraer motivo sin emoji
    motivo = texto.split(" ", 1)[-1] if " " in texto else texto
    motivos_validos = ['numero_incorrecto', 'no_existe', 'spam', 'duplicado', 'otro']
    if motivo not in motivos_validos:
        await update.message.reply_text("⚠️ Selecciona un motivo válido:")
        return REP_MOTIVO
    context.user_data['motivo'] = motivo
    await update.message.reply_text(
        "¿Alguna *descripción* adicional?\n(Escribe *no* para omitir)",
        parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup([["/cancelar", "no"]], resize_keyboard=True),
    )
    return REP_DESCRIPCION

async def reportar_descripcion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    descripcion = None if texto.lower() == 'no' else texto
    data = context.user_data
    return await _procesar_reporte(update, context, data['contacto_id'], data['motivo'], descripcion)

async def _procesar_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE, identificador: str, motivo: str, descripcion: str = None):
    """Procesar el reporte"""
    motivos_validos = ['numero_incorrecto', 'no_existe', 'spam', 'duplicado', 'otro']
    if motivo not in motivos_validos:
        await update.message.reply_text(f"⚠️ Motivo inválido. Usa: {', '.join(motivos_validos)}", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    contacto = db.buscar_por_id_o_telefono(identificador)
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    resultado = db.reportar_contacto(
        contacto_id=contacto['id'], motivo=motivo,
        descripcion=descripcion, reportado_por=str(update.effective_user.id),
    )

    if resultado.get("error"):
        await update.message.reply_text(f"❌ Error: {resultado['error']}", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("⚠️ Reporte enviado. Gracias por informar.", reply_markup=ReplyKeyboardRemove())

    context.user_data.clear()
    return ConversationHandler.END

# === Cancelar ===
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === Builders ===
def get_agregar_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("agregar", agregar_inicio)],
        states={
            AGR_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_nombre)],
            AGR_APELLIDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_apellido)],
            AGR_TELEFONO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_telefono)],
            AGR_DIRECCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_direccion)],
            AGR_CI: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_ci)],
            AGR_CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_categoria)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

def get_reportar_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("reportar", reportar_inicio)],
        states={
            REP_CONTACTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, reportar_contacto)],
            REP_MOTIVO: [MessageHandler(filters.TEXT & ~filters.COMMAND, reportar_motivo)],
            REP_DESCRIPCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, reportar_descripcion)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
