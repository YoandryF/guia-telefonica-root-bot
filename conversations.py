"""
Flujos interactivos (ConversationHandler) para /agregar y /reportar
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, ContextTypes, filters
from supabase_service import SupabaseService

db = SupabaseService()

# === Catálogo Cuba (provincias y municipios) ===
PROVINCIAS_CUBA = [
    "Pinar del Río", "Artemisa", "La Habana", "Mayabeque", "Matanzas",
    "Villa Clara", "Cienfuegos", "Sancti Spíritus", "Ciego de Ávila",
    "Camagüey", "Las Tunas", "Holguín", "Granma", "Santiago de Cuba",
    "Guantánamo", "Isla de la Juventud"
]

MUNICIPIOS_CUBA = {
    "Pinar del Río": ["Consolación del Sur", "Guane", "La Palma", "Los Palacios", "Mantua", "Minas de Matahambre", "Pinar del Río", "San Juan y Martínez", "San Luis", "Sandino", "Viñales"],
    "Artemisa": ["Alquízar", "Artemisa", "Bauta", "Caimito", "Candelaria", "Güira de Melena", "Guanajay", "Mariel", "San Antonio de los Baños", "San Cristóbal", "Bahía Honda"],
    "La Habana": ["Arroyo Naranjo", "Boyeros", "Centro Habana", "Cerro", "Cotorro", "Diez de Octubre", "Guanabacoa", "Habana del Este", "Habana Vieja", "La Lisa", "Marianao", "Playa", "Plaza de la Revolución", "Regla", "San Miguel del Padrón"],
    "Mayabeque": ["Batabanó", "Bejucal", "Güines", "Jaruco", "Madruga", "Melena del Sur", "Nueva Paz", "Quivicán", "San José de las Lajas", "San Nicolás de Bari", "Santa Cruz del Norte"],
    "Matanzas": ["Calimete", "Cárdenas", "Ciénaga de Zapata", "Colón", "Jagüey Grande", "Jovellanos", "Limonar", "Los Arabos", "Martí", "Matanzas", "Pedro Betancourt", "Perico", "Unión de Reyes"],
    "Villa Clara": ["Caibarién", "Camajuaní", "Cifuentes", "Corralillo", "Encrucijada", "Manicaragua", "Placetas", "Quemado de Güines", "Ranchuelo", "Remedios", "Sagua la Grande", "Santa Clara", "Santo Domingo"],
    "Cienfuegos": ["Abreus", "Aguada de Pasajeros", "Cienfuegos", "Cruces", "Cumanayagua", "Lajas", "Palmira", "Rodas"],
    "Sancti Spíritus": ["Cabaiguán", "Fomento", "Jatibonico", "La Sierpe", "Sancti Spíritus", "Taguasco", "Trinidad", "Yaguajay"],
    "Ciego de Ávila": ["Baraguá", "Bolivia", "Chambas", "Ciego de Ávila", "Ciro Redondo", "Florencia", "Majagua", "Morón", "Primero de Enero", "Venezuela"],
    "Camagüey": ["Camagüey", "Carlos Manuel de Céspedes", "Esmeralda", "Florida", "Guáimaro", "Jimaguayú", "Minas", "Najasa", "Nuevitas", "Santa Cruz del Sur", "Sibanicú", "Sierra de Cubitas", "Vertientes"],
    "Las Tunas": ["Amancio", "Colombia", "Jesús Menéndez", "Jobabo", "Las Tunas", "Majibacoa", "Manatí", "Puerto Padre"],
    "Holguín": ["Antilla", "Báguanos", "Banes", "Cacocum", "Calixto García", "Cueto", "Frank País", "Gibara", "Holguín", "Mayarí", "Moa", "Rafael Freyre", "Sagua de Tánamo", "Urbano Noris"],
    "Granma": ["Bartolomé Masó", "Bayamo", "Buey Arriba", "Campechuela", "Cauto Cristo", "Guisa", "Jiguaní", "Manzanillo", "Media Luna", "Niquero", "Pilón", "Río Cauto", "Yara"],
    "Santiago de Cuba": ["Contramaestre", "Guamá", "Julio Antonio Mella", "Palma Soriano", "San Luis", "Santiago de Cuba", "Segundo Frente", "Songo-La Maya", "Tercer Frente"],
    "Guantánamo": ["Baracoa", "Caimanera", "El Salvador", "Guantánamo", "Imías", "Maisí", "Manuel Tames", "Niceto Pérez", "San Antonio del Sur", "Yateras"],
    "Isla de la Juventud": ["Isla de la Juventud"],
}

# === /agregar interactivo ===
AGR_NOMBRE, AGR_APELLIDO, AGR_TELEFONO, AGR_PROVINCIA, AGR_MUNICIPIO, AGR_DIRECCION, AGR_CI, AGR_CATEGORIA = range(8)

async def agregar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicio de /agregar — si tiene args, procesa directo; si no, inicia flujo"""
    if context.args:
        texto = " ".join(context.args)
        partes = [p.strip() for p in texto.split(",")]
        if len(partes) >= 3:
            return await _registrar_contacto(update, context, partes)
        else:
            await update.message.reply_text("⚠️ Formato: `/agregar Nombre, Apellido, Teléfono`", parse_mode="Markdown")
            return ConversationHandler.END

    await update.message.reply_text(
        "✏️ *Nuevo contacto — Paso 1/7*\n\n¿Cuál es el *nombre*?",
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

    # Mostrar provincias en teclado (4 columnas)
    teclado = []
    for i in range(0, len(PROVINCIAS_CUBA), 2):
        fila = PROVINCIAS_CUBA[i:i+2]
        teclado.append(fila)
    teclado.append(["no"])

    await update.message.reply_text(
        f"✅ Teléfono: *{telefono}*\n\n🗺 ¿*Provincia*?\n(Selecciona o escribe *no* para omitir)",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(teclado, resize_keyboard=True, one_time_keyboard=True),
    )
    return AGR_PROVINCIA

async def agregar_provincia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto.lower() == 'no':
        context.user_data['provincia'] = None
        context.user_data['municipio'] = None
        await update.message.reply_text(
            "¿Cuál es la *dirección*?\n(Escribe *no* para omitir)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["/cancelar", "no"]], resize_keyboard=True),
        )
        return AGR_DIRECCION

    # Buscar provincia
    provincia = None
    for p in PROVINCIAS_CUBA:
        if p.lower() == texto.lower() or texto.lower() in p.lower():
            provincia = p
            break

    if not provincia:
        context.user_data['provincia'] = texto
        context.user_data['municipio'] = None
        await update.message.reply_text(
            f"✅ Provincia: *{texto}*\n\n¿Cuál es la *dirección*?\n(Escribe *no* para omitir)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["/cancelar", "no"]], resize_keyboard=True),
        )
        return AGR_DIRECCION

    context.user_data['provincia'] = provincia

    # Mostrar municipios de esa provincia
    municipios = MUNICIPIOS_CUBA.get(provincia, [])
    if municipios:
        teclado = []
        for i in range(0, len(municipios), 2):
            teclado.append(municipios[i:i+2])
        teclado.append(["no"])
        await update.message.reply_text(
            f"✅ Provincia: *{provincia}*\n\n🏘 ¿*Municipio*?\n(Selecciona o escribe *no* para omitir)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(teclado, resize_keyboard=True, one_time_keyboard=True),
        )
        return AGR_MUNICIPIO
    else:
        context.user_data['municipio'] = None
        await update.message.reply_text(
            f"✅ Provincia: *{provincia}*\n\n¿Cuál es la *dirección*?\n(Escribe *no* para omitir)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["/cancelar", "no"]], resize_keyboard=True),
        )
        return AGR_DIRECCION

async def agregar_municipio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto.lower() == 'no':
        context.user_data['municipio'] = None
    else:
        context.user_data['municipio'] = texto

    await update.message.reply_text(
        f"✅ Municipio: *{context.user_data.get('municipio', 'N/A')}*\n\n¿Cuál es la *dirección*?\n(Escribe *no* para omitir)",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["/cancelar", "no"]], resize_keyboard=True),
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
        provincia=data.get('provincia'), municipio=data.get('municipio'),
        creado_por=str(update.effective_user.id), creado_desde="telegram",
    )

    if resultado.get("error"):
        error = resultado["error"]
        if "duplicate" in str(error).lower():
            await update.message.reply_text("⚠️ Ese teléfono o CI ya está registrado.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text(f"❌ Error: {error}", reply_markup=ReplyKeyboardRemove())
    else:
        ubicacion = ""
        if data.get('municipio'):
            ubicacion += f"\n🏘 {data['municipio']}"
        if data.get('provincia'):
            ubicacion += f"\n🗺 {data['provincia']}"

        await update.message.reply_text(
            f"✅ *Contacto registrado*\n\n👤 {data['nombre']} {data['apellido']}\n📱 {data['telefono']}{ubicacion}\n\n⏳ Pendiente de aprobación.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
    context.user_data.clear()
    return ConversationHandler.END

async def _registrar_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE, partes: list):
    """Registrar el contacto en Supabase (modo directo)"""
    nombre = partes[0]
    apellido = partes[1]
    telefono = partes[2]
    direccion = partes[3] if len(partes) > 3 else None
    ci = partes[4] if len(partes) > 4 else None
    provincia = partes[5] if len(partes) > 5 else None
    municipio = partes[6] if len(partes) > 6 else None

    resultado = db.registrar_contacto(
        nombre=nombre, apellido=apellido, telefono=telefono,
        direccion=direccion, ci=ci, provincia=provincia, municipio=municipio,
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
            AGR_PROVINCIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_provincia)],
            AGR_MUNICIPIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_municipio)],
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
