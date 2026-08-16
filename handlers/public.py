"""
Public command handlers — accessible by all users.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.helpers import db, ADMIN_CHAT_ID, es_admin, _cache_resultados, _mostrar_lista
from utils.formatters import formatear_contacto, _formato_lista_compacta

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida + verificación deep link"""
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

    # Invitación por referido (/start invitacion_GT-XXXXXXXX)
    if context.args and len(context.args) > 0 and context.args[0].startswith("invitacion_"):
        codigo_inv = context.args[0].replace("invitacion_", "")
        try:
            result = db.client.rpc("registrar_referido", {
                "p_codigo":     codigo_inv,
                "p_referido_id": str(user.id),
            }).execute()
            res = result.data if result.data else {}
            ok    = res.get("ok", False)
            error = res.get("error", "")
            if ok:
                logger.info(f"Referido registrado: {user.id} via código {codigo_inv}")
            elif error == "YA_REFERIDO":
                pass  # ya registrado, no interrumpir el flujo
            elif error == "AUTOREFERIDO":
                pass  # silencioso
            # Continuar al mensaje de bienvenida normal
        except Exception as e:
            logger.error(f"Error registrando referido: {e}")
        # No hacer return — mostrar bienvenida normalmente

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
    """Listar contactos aprobados con paginación real desde Supabase"""
    pagina = 1
    if context.args:
        try:
            pagina = int(context.args[0])
        except ValueError:
            pass

    msg = await update.message.reply_text("⏳ Cargando contactos...")
    await update.message.chat.send_action("typing")

    por_pagina = 10
    offset = (pagina - 1) * por_pagina
    contactos, total = db.get_contactos_aprobados(limite=por_pagina, offset=offset)

    if not contactos:
        await msg.edit_text("📭 No hay contactos aprobados aún.")
        return

    total_pags = max(1, (total + por_pagina - 1) // por_pagina)
    inicio_num = offset + 1
    chat_id = str(update.effective_user.id)
    _cache_resultados[chat_id] = {'tipo': 'listar', 'total': total, 'por_pagina': por_pagina}

    texto, markup = _formato_lista_compacta(contactos, inicio_num, total, pagina, total_pags, '')
    await msg.edit_text(texto, parse_mode="Markdown", reply_markup=markup)


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buscar contactos con lista compacta paginada"""
    if not context.args:
        await update.message.reply_text(
            "🔍 Escribe el nombre, teléfono o CI a buscar:\n"
            "Ejemplo: `/buscar Juan` o simplemente escribe el texto",
            parse_mode="Markdown",
        )
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Buscando *{query}*...", parse_mode="Markdown")
    await update.message.chat.send_action("typing")

    contactos = db.buscar_contactos(query)

    if not contactos:
        await msg.edit_text(f"❌ Sin resultados para: *{query}*\n\nIntenta con otro término.", parse_mode="Markdown")
        return

    chat_id = str(update.effective_user.id)
    _cache_resultados[chat_id] = {'contactos': contactos, 'query': query}

    total = len(contactos)
    total_pags = max(1, (total + 9) // 10)
    texto, markup = _formato_lista_compacta(contactos[:10], 1, total, 1, total_pags, query)
    await msg.edit_text(texto, parse_mode="Markdown", reply_markup=markup)


async def miscontactos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver contactos registrados por este usuario con estado y detalle"""
    msg = await update.message.reply_text("⏳ Cargando tus contactos...")
    await update.message.chat.send_action("typing")
    chat_id = str(update.effective_user.id)
    contactos = db.get_contactos_por_creador(chat_id)

    if not contactos:
        await msg.edit_text(
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

    await msg.edit_text(texto, parse_mode="Markdown")


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


async def listanegra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista negra paginada — contactos reportados ordenados por score de riesgo"""
    pagina = 1
    if context.args:
        try:
            pagina = int(context.args[0])
        except ValueError:
            pass

    msg = await update.message.reply_text("⏳ Cargando lista negra...")
    await update.message.chat.send_action("typing")

    por_pagina = 10
    offset = (pagina - 1) * por_pagina
    reportados = db.get_contactos_con_reportes(limite=por_pagina, offset=offset)
    total = db.contar_contactos_con_reportes()

    if not reportados and pagina == 1:
        await msg.edit_text("✅ No hay contactos en la lista negra.")
        return

    total_pags = max(1, (total + por_pagina - 1) // por_pagina)
    inicio_num = offset + 1

    # Guardar en cache para paginación por botones
    chat_id = str(update.effective_user.id)
    _cache_resultados[chat_id] = {'tipo': 'listanegra', 'total': total, 'por_pagina': por_pagina}

    texto = f"⚠️ *Lista Negra — {total} contactos*\n\n"
    for i, c in enumerate(reportados, inicio_num):
        nombre = f"{c['nombre']} {c['apellido']}"
        if len(nombre) > 22:
            nombre = nombre[:20] + "…"
        verificado = c.get('verificado', False)
        estado = "🔴 Verificado" if verificado else "🟡 Reportado"
        texto += f"*{i}.* {nombre.upper()}\n   📱 `{c['telefono']}` — {estado}\n\n"

    texto += f"📊 Mostrando {inicio_num}-{inicio_num + len(reportados) - 1} de *{total}*\n"
    texto += "_Escribe el número para ver detalles completos_"

    # Botones de paginación
    botones = []
    fila = []
    if pagina > 1:
        fila.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"ln_{pagina - 1}"))
    if pagina < total_pags:
        fila.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"ln_{pagina + 1}"))
    if fila:
        botones.append(fila)

    markup = InlineKeyboardMarkup(botones) if botones else None
    await msg.edit_text(texto, parse_mode="Markdown", reply_markup=markup)


async def handle_texto_libre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Texto libre para TODOS los usuarios — busca número o nombre directamente"""
    texto = update.message.text.strip()

    # Si parece número de teléfono → mostrar detalle
    limpio = texto.replace('-', '').replace(' ', '').replace('+', '')
    if limpio.isdigit() and len(limpio) >= 5:
        msg = await update.message.reply_text("🔍 Buscando número...")
        await update.message.chat.send_action("typing")
        contacto = db.buscar_por_id_o_telefono(texto)
        if contacto:
            admin = es_admin(update.effective_user.id)
            detalle = formatear_contacto(contacto, mostrar_id=admin)
            if admin:
                keyboard = [[InlineKeyboardButton("🗑 Eliminar", callback_data=f"confirmar_del_{contacto['id'][:8]}")]]
                await msg.edit_text(detalle, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await msg.edit_text(detalle, parse_mode="Markdown")
        else:
            await msg.edit_text(
                f"❌ No encontré ningún contacto con `{texto}`\n\n"
                f"_¿Quieres registrarlo? Usa /agregar_",
                parse_mode="Markdown",
            )
        return

    # Si tiene 3+ chars → buscar como nombre
    if len(texto) >= 3:
        msg = await update.message.reply_text(f"🔍 Buscando *{texto}*...", parse_mode="Markdown")
        await update.message.chat.send_action("typing")
        contactos = db.buscar_contactos(texto)
        if contactos:
            chat_id = str(update.effective_user.id)
            _cache_resultados[chat_id] = {'contactos': contactos, 'query': texto}
            total = len(contactos)
            total_pags = max(1, (total + 9) // 10)
            t, markup = _formato_lista_compacta(contactos[:10], 1, total, 1, total_pags, texto)
            await msg.edit_text(t, parse_mode="Markdown", reply_markup=markup)
        else:
            await msg.edit_text(
                f"❌ Sin resultados para *{texto}*\n\nIntenta con otro término.",
                parse_mode="Markdown",
            )


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
        db.client.table("avales").insert({
            "contacto_id": contacto["id"],
            "avalado_por": str(update.effective_user.id),
        }).execute()
        await update.message.reply_text(
            f"👍 *Aval enviado* para {contacto['nombre']} {contacto['apellido']}\n\n"
            f"⏳ Pendiente de revisión por el administrador.\n"
            f"Solo los avales aprobados afectan el score del contacto.",
            parse_mode="Markdown"
        )
        # Notificar al admin
        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=(
                        f"👍 *Nuevo aval pendiente*\n\n"
                        f"👤 {contacto['nombre']} {contacto['apellido']}\n"
                        f"📱 `{contacto['telefono']}`\n"
                        f"Por: @{update.effective_user.username or update.effective_user.first_name}\n\n"
                        f"Usa /avales para gestionar"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass
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


async def cancelar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancelar un registro propio pendiente. Uso: /cancelar_registro teléfono"""
    from datetime import datetime

    if not context.args:
        await update.message.reply_text("Usa: `/cancelar_registro teléfono`", parse_mode="Markdown")
        return

    identificador = context.args[0]
    chat_id = str(update.effective_user.id)

    try:
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


async def micodigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera o muestra el código de invitación del usuario."""
    user = update.effective_user
    chat_id = str(user.id)

    try:
        codigo = db.client.rpc(
            'generar_codigo_invitacion',
            {'p_telegram_user_id': chat_id}
        ).execute().data

        if not codigo:
            await update.message.reply_text("❌ Error generando código. Intenta de nuevo.")
            return

        link = f"guia://invitacion/{codigo}"
        await update.message.reply_text(
            f"🎁 *Tu código de invitación*\n\n"
            f"`{codigo}`\n\n"
            f"Comparte este mensaje con quien quieras invitar:\n\n"
            f"_📱 Únete a la Guía Telefónica Colaborativa._\n"
            f"_Usa mi código: *{codigo}*_\n"
            f"_Descarga: https://github.com/YoandryF/guia-telefonica-root-app/releases/latest_\n\n"
            f"O comparte el link directo:\n`{link}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def misreferidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los referidos del usuario."""
    chat_id = str(update.effective_user.id)

    try:
        result = db.client.rpc(
            'get_mis_referidos',
            {'p_telegram_user_id': chat_id}
        ).execute().data

        if not result:
            await update.message.reply_text("❌ Error obteniendo referidos.")
            return

        codigo = result.get('codigo', '')
        total = result.get('total', 0)
        referidos = result.get('referidos') or []

        if not codigo:
            await update.message.reply_text(
                "Aún no tienes código de invitación.\n"
                "Usa /micodigo para generarlo."
            )
            return

        texto = f"🎁 *Mis referidos*\n\n"
        texto += f"📌 Tu código: `{codigo}`\n"
        texto += f"👥 Total referidos: *{total}*\n\n"

        if referidos:
            activos = sum(1 for r in referidos if r.get('activo'))
            texto += f"✅ Activos: {activos}\n\n"
            texto += "_Últimos referidos:_\n"
            for r in referidos[:10]:
                fecha = r.get('fecha', '')[:10] if r.get('fecha') else '—'
                estado = "✅" if r.get('activo') else "⬜"
                texto += f"  {estado} Se unió el {fecha}\n"
            if total > 10:
                texto += f"  _... y {total - 10} más_\n"
        else:
            texto += "_Aún no tienes referidos. ¡Comparte tu código!_"

        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
