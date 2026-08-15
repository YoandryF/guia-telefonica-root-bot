"""
Admin command handlers — requires admin privileges.
"""

import io
import csv as csv_module
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import db, ADMIN_CHAT_ID, es_admin
from utils.formatters import formatear_contacto

logger = logging.getLogger(__name__)


async def pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver contactos pendientes con filtro y paginación (botones)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("\U0001f512 Solo el administrador puede usar este comando.")
        return

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

    nav = []
    if inicio > 0:
        nav.append(InlineKeyboardButton("\u2b05 Anterior", callback_data="pend_prev"))
    if fin < total:
        nav.append(InlineKeyboardButton("Siguiente \u27a1", callback_data="pend_next"))
    if nav:
        await update.message.reply_text(f"P\u00e1gina {pagina+1}/{(total+por_pagina-1)//por_pagina}", reply_markup=InlineKeyboardMarkup([nav]))


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


async def eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eliminar contacto (solo admin). Uso: /eliminar teléfono|ID"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador puede usar este comando.")
        return

    if not context.args:
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
    nuevo_valor = ", ".join(partes[2:])

    campos_validos = ['nombre', 'apellido', 'telefono', 'direccion', 'ci', 'categoria']
    if campo not in campos_validos:
        await update.message.reply_text(f"⚠️ Campo inválido. Usa: {', '.join(campos_validos)}")
        return

    contacto = db.buscar_por_id_o_telefono(identificador)
    if not contacto:
        await update.message.reply_text("❌ Contacto no encontrado.")
        return

    try:
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
    content_bytes = io.BytesIO()
    await file.download_to_memory(content_bytes)
    content = content_bytes.getvalue().decode("utf-8")

    contactos = []
    if doc.file_name.endswith(".csv"):
        reader = csv_module.DictReader(io.StringIO(content))
        for row in reader:
            if row.get("nombre") and row.get("telefono"):
                contactos.append(row)
    else:
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

        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"🚨 *Nuevo reporte*\n\nContacto: `{contacto_id}`\nMotivo: {motivo}\nPor: {update.effective_user.first_name}\n\nUsa /reportes para ver todos",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


async def avales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver avales pendientes de revisión (solo admin)"""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Solo el administrador.")
        return

    try:
        response = db.client.table("avales").select(
            "*, contactos(nombre, apellido, telefono)"
        ).eq("estado", "pendiente").order("fecha").execute()

        if not response.data:
            await update.message.reply_text("✅ No hay avales pendientes.")
            return

        await update.message.reply_text(
            f"👍 *Avales pendientes ({len(response.data)}):*",
            parse_mode="Markdown"
        )

        for a in response.data[:10]:
            contacto = a.get("contactos", {})
            nombre = f"{contacto.get('nombre', '')} {contacto.get('apellido', '')}"
            keyboard = [[
                InlineKeyboardButton("✅ Aprobar", callback_data=f"aval_aprobar_{a['id'][:8]}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"aval_rechazar_{a['id'][:8]}"),
            ]]
            await update.message.reply_text(
                f"👤 *{nombre}*\n📱 `{contacto.get('telefono', '')}`\n"
                f"Por: `{a.get('avalado_por', 'desconocido')}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
