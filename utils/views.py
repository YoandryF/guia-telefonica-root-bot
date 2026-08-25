"""
views.py — Capa de presentación compartida.

Construye y envía vistas completas (texto + teclado + paginación).
No depende de handlers. Flujo de dependencias:
  handlers → views → formatters / helpers / db

Navegación inline: todas las vistas incluyen botón 🏠 Inicio
para que el usuario navegue sin salir del mensaje original.
"""

import html as _html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes

from utils.helpers import (
    db, cache_resultados_set,
    validar_valor_config,
)
from utils.formatters import formatear_contacto, teclado_contacto, _formato_lista_compacta, _esc


def _inferir_tipo_hint(valor: str) -> str:
    """Sugiere el formato esperado para edición — presentación pura."""
    if valor in ('true', 'false'):
        return "(true o false)"
    try:
        int(valor)
        return "(número entero)"
    except ValueError:
        pass
    try:
        float(valor)
        return "(número decimal, ej: 0.8)"
    except ValueError:
        pass
    return "(texto libre)"


# ── Helpers de navegación ─────────────────────────────────────────────────────

def _btn_inicio() -> list:
    """Fila con botón de volver al inicio — se añade al final de toda vista."""
    return [InlineKeyboardButton("🏠 Inicio", callback_data="cmd_inicio")]


async def _enviar(message: Message, texto: str, markup: InlineKeyboardMarkup,
                  parse_mode: str | None = "Markdown", editar: bool = False) -> None:
    """Enviar o editar un mensaje según el contexto.
    parse_mode=None envía sin formato — siempre pasa parse_mode explícitamente
    al editar para evitar que Telegram herede el modo del mensaje anterior.
    """
    kwargs = {"reply_markup": markup}
    # Siempre pasar parse_mode explícitamente (incluso vacío) para evitar
    # que Telegram herede el parse_mode del mensaje original al editar
    kwargs["parse_mode"] = parse_mode or ""
    if editar:
        await message.edit_text(texto, **kwargs)
    else:
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        else:
            kwargs.pop("parse_mode", None)
        await message.reply_text(texto, **kwargs)


# ── Start / Inicio ────────────────────────────────────────────────────────────

async def mostrar_start(message: Message, user_id: int,
                        primer_nombre: str, editar: bool = False) -> None:
    """Vista principal — botones según rol del usuario."""
    from utils.helpers import es_admin as _es_admin, es_owner as _es_owner

    nombre  = primer_nombre or "amigo"
    mensaje = (
        f"👋 Hola, *{_esc(nombre)}*\\! Bienvenido a la *Guía Telefónica Colaborativa*\\.\n\n"
        "Escribe directamente para buscar:\n\n"
        "> 📱 Por número: `55551234`\n"
        "> 👤 Por nombre: `Juan Pérez`\n"
        "> 🔢 Varios a la vez: `55551234 56789012`\n\n"
        "📲 [Descargar app Android](https://github\\.com/YoandryF/guia-telefonica-root-app/releases/latest)\n\n"
        "_Base de datos colaborativa — tu aporte importa_ 🤝"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔍 Buscar",           switch_inline_query_current_chat=""),
            InlineKeyboardButton("➕ Agregar contacto", callback_data="cmd_agregar"),
        ],
        [
            InlineKeyboardButton("🚫 Lista negra",  callback_data="cmd_listanegra"),
            InlineKeyboardButton("📌 Mis reportes", callback_data="cmd_misreportes"),
        ],
        [
            InlineKeyboardButton("❓ Ayuda", callback_data="cmd_ayuda"),
        ],
    ]

    if _es_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("⏳ Pendientes",   callback_data="cmd_pendientes"),
            InlineKeyboardButton("🚨 Reportes",     callback_data="cmd_reportes"),
            InlineKeyboardButton("📊 Estadísticas", callback_data="cmd_estadisticas"),
        ])

    if _es_owner(user_id):
        keyboard.append([
            InlineKeyboardButton("👑 Admins",   callback_data="cmd_admins"),
            InlineKeyboardButton("⚙️ Config",  callback_data="cmd_config"),
            InlineKeyboardButton("📤 Exportar", callback_data="cmd_exportar"),
        ])

    markup = InlineKeyboardMarkup(keyboard)
    if editar:
        await message.edit_text(mensaje, parse_mode="MarkdownV2",
                                reply_markup=markup, disable_web_page_preview=True)
    else:
        await message.reply_text(mensaje, parse_mode="MarkdownV2",
                                 reply_markup=markup, disable_web_page_preview=True)


# ── Lista negra ───────────────────────────────────────────────────────────────

async def mostrar_listanegra(message: Message, pagina: int = 1,
                              editar: bool = False) -> None:
    """Lista paginada de contactos reportados — accesible a todos los usuarios."""
    por_pagina = 10
    offset     = (pagina - 1) * por_pagina
    total      = db.contar_contactos_con_reportes()

    if total == 0:
        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message, "✅ La lista negra está vacía por ahora.",
                      markup, parse_mode=None, editar=editar)
        return

    reportados = db.get_contactos_con_reportes(limite=por_pagina, offset=offset)
    total_pags = max(1, (total + por_pagina - 1) // por_pagina)
    inicio_num = offset + 1

    texto  = f"🚫 <b>Lista Negra</b>\n"
    texto += f"<i>{total} números reportados — Página {pagina}/{total_pags}</i>\n"
    texto += "——————————————————\n\n"

    for i, c in enumerate(reportados, inicio_num):
        nombre = _html.escape(f"{c['nombre']} {c['apellido']}".upper())
        tel    = _html.escape(c['telefono'])
        estado = "⛔ Verificado" if c.get('verificado') else "🔴 Reportado"
        texto += f"{i}. <b>{nombre}</b>\n   📱 <code>{tel}</code> — {estado}\n\n"

    botones = []
    nav = []
    if pagina > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"ln_{pagina-1}"))
    nav.append(InlineKeyboardButton(f"· {pagina}/{total_pags} ·", callback_data="noop"))
    if pagina < total_pags:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"ln_{pagina+1}"))
    if nav:
        botones.append(nav)
    botones.append(_btn_inicio())

    await _enviar(message, texto, InlineKeyboardMarkup(botones),
                  parse_mode="HTML", editar=editar)


# ── Ayuda ─────────────────────────────────────────────────────────────────────

async def mostrar_ayuda(message: Message, user_id: int, editar: bool = False) -> None:
    """Vista de ayuda con sección admin si corresponde."""
    from utils.helpers import es_admin as _es_admin

    texto = (
        "📖 *Guía de uso*\n\n"
        "*Formas de buscar:*\n\n"
        "> 1\\. Por número: `55551234`\n"
        "> 2\\. Por nombre: `Juan Pérez`\n"
        "> 3\\. Varios a la vez: `55551234 56789012`\n\n"
        "*Notas:*\n"
        "• No importan mayúsculas ni minúsculas\n"
        "• Los espacios en los números se ignoran\n\n"
        "*Para agregar:* toca ➕ o escribe /agregar\n"
        "*Para reportar:* busca el número y toca ⚠️\n"
    )

    if _es_admin(user_id):
        texto += (
            "\n*Comandos admin:*\n"
            "> /pendientes — aprobar contactos\n"
            "> /reportes — gestionar reportes\n"
            "> /avales — avales pendientes\n"
            "> /reclamos — reclamos pendientes\n"
            "> /estadisticas — ver estadísticas\n"
            "> /exportar csv — exportar BD\n"
            "> /banear — banear reportador\n"
        )

    markup = InlineKeyboardMarkup([_btn_inicio()])
    await _enviar(message, texto, markup, parse_mode="MarkdownV2", editar=editar)


# ── Contacto ──────────────────────────────────────────────────────────────────

async def mostrar_contacto(message: Message, contacto: dict,
                           es_admin: bool = False, editar: bool = False) -> None:
    """Ficha completa de un contacto con botones de acción."""
    info_reportes = db.get_info_reportes(contacto['id'])
    texto  = formatear_contacto(contacto, info_reportes=info_reportes, mostrar_id=es_admin)
    markup = teclado_contacto(contacto, es_admin=es_admin)
    await _enviar(message, texto, markup, parse_mode="MarkdownV2", editar=editar)


# ── Pendientes ────────────────────────────────────────────────────────────────

async def mostrar_pendientes(message: Message, context: ContextTypes.DEFAULT_TYPE,
                             user_id: int, pagina: int = 0,
                             editar: bool = False) -> None:
    """Lista de contactos pendientes con botones de aprobación y navegación."""
    contactos = db.get_contactos_pendientes()

    if not contactos:
        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message, "✅ No hay contactos pendientes.", markup, editar=editar)
        return

    POR_PAG = 5
    total   = len(contactos)
    pagina  = max(0, min(pagina, (total - 1) // POR_PAG))
    inicio  = pagina * POR_PAG
    lote    = contactos[inicio:inicio + POR_PAG]

    cache_resultados_set(str(user_id) + '_pend', {'contactos': contactos})
    context.user_data['pend_pagina'] = pagina

    texto = f"⏳ *Pendientes ({inicio+1}–{min(inicio+POR_PAG, total)} de {total})*\n\n"
    botones = []

    for c in lote:
        nombre = f"{c['nombre']} {c['apellido']}"
        prov   = c.get('provincia') or ''
        mun    = c.get('municipio') or ''
        ubi    = f" — {mun}, {prov}" if mun else (f" — {prov}" if prov else "")
        texto += f"👤 *{nombre}*\n📱 `{c['telefono']}`{ubi}\n\n"
        cid8   = c['id'][:8]
        botones.append([
            InlineKeyboardButton(f"✅ {c['telefono']}", callback_data=f"aprobar_{cid8}"),
            InlineKeyboardButton("❌",                  callback_data=f"rechazar_{cid8}"),
            InlineKeyboardButton("🗑",                  callback_data=f"confirmar_del_{cid8}"),
        ])

    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"pend_pg_{pagina-1}"))
    if inicio + POR_PAG < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"pend_pg_{pagina+1}"))
    if nav:
        botones.append(nav)
    botones.append(_btn_inicio())

    await _enviar(message, texto, InlineKeyboardMarkup(botones), editar=editar)


# ── Reportes ──────────────────────────────────────────────────────────────────

async def mostrar_reportes(message: Message, editar: bool = False) -> None:
    """Lista de reportes pendientes con botones de gestión."""
    lista = db.get_reportes_pendientes()

    if not lista:
        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message, "✅ No hay reportes pendientes.", markup, editar=editar)
        return

    texto   = f"🚨 *Reportes pendientes ({len(lista)}):*\n\n"
    botones = []

    for r in lista[:10]:
        contacto = r.get("contactos") or {}
        nombre   = f"{contacto.get('nombre','?')} {contacto.get('apellido','')}"
        desc     = r.get('descripcion') or ''
        texto += (
            f"👤 *{nombre}* — `{contacto.get('telefono','')}`\n"
            f"⚠️ {r['motivo']}"
            + (f": _{desc[:50]}_" if desc else "")
            + "\n\n"
        )
        cid8 = r['id'][:8]
        botones.append([
            InlineKeyboardButton("✅ Verificar",  callback_data=f"verificar_rep_{cid8}"),
            InlineKeyboardButton("🗑 Desestimar", callback_data=f"desestimar_rep_{cid8}"),
        ])

    botones.append(_btn_inicio())
    await _enviar(message, texto, InlineKeyboardMarkup(botones), editar=editar)


# ── Estadísticas ──────────────────────────────────────────────────────────────

async def mostrar_estadisticas(message: Message, editar: bool = False) -> None:
    """Vista de estadísticas generales."""
    stats = db.get_estadisticas()
    texto = (
        "📊 *Estadísticas*\n\n"
        f"✅ Aprobados:         {stats.get('aprobados', 0):,}\n"
        f"⏳ Pendientes:        {stats.get('pendientes', 0):,}\n"
        f"❌ Rechazados:        {stats.get('rechazados', 0):,}\n"
        f"📋 Total contactos:   {stats.get('total', 0):,}\n"
        f"👥 Usuarios Telegram: {stats.get('usuarios_telegram', 0):,}\n"
    )
    markup = InlineKeyboardMarkup([_btn_inicio()])
    await _enviar(message, texto, markup, editar=editar)


# ── Admins ────────────────────────────────────────────────────────────────────

async def mostrar_admins(message: Message, editar: bool = False) -> None:
    """Lista de admins registrados (solo owner)."""
    admins = db.get_admins()

    if not admins:
        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message,
                      "📭 No hay admins registrados.\n\nUsa /registrar_admin para agregar uno.",
                      markup, editar=editar)
        return

    texto = "<b>🔐 Admins registrados</b>\n"
    texto += f"<i>{len(admins)} administrador{'es' if len(admins) != 1 else ''}</i>\n"
    texto += "——————————————————\n\n"
    for a in admins:
        estado = "🟢" if a.get("activo") else "🔴"
        nombre = _html.escape(a.get('nombre_admin') or '?')
        email  = _html.escape(a.get('email', ''))
        chat   = a.get('chat_id_telegram') or '—'
        texto += f"{estado} <b>{nombre}</b>\n"
        texto += f"   📧 <code>{email}</code>\n"
        texto += f"   🪪 ID Telegram: <code>{chat}</code>\n\n"

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Registrar admin", callback_data="cmd_admin_registrar"),
            InlineKeyboardButton("🗑 Eliminar admin",  callback_data="cmd_admin_eliminar"),
        ],
        _btn_inicio(),
    ])
    await _enviar(message, texto, markup, parse_mode="HTML", editar=editar)


# ── Mis reportes ──────────────────────────────────────────────────────────────

async def mostrar_mis_reportes(message: Message, user_id: str,
                                editar: bool = False) -> None:
    """Reportes enviados por el usuario."""
    try:
        resp = db.client.table("reportes").select(
            "id, motivo, fecha_reporte, contactos(nombre, apellido, telefono)"
        ).eq("reportado_por", user_id).order("fecha_reporte", desc=True).limit(10).execute()

        if not resp.data:
            markup = InlineKeyboardMarkup([_btn_inicio()])
            await _enviar(message, "📭 No has enviado reportes aún.", markup, editar=editar)
            return

        texto = f"📌 *Tus reportes ({len(resp.data)}):*\n\n"
        for r in resp.data:
            c     = r.get('contactos') or {}
            fecha = (r.get('fecha_reporte') or '')[:10]
            texto += (
                f"⚠️ *{c.get('nombre','')} {c.get('apellido','')}*"
                f" — `{c.get('telefono','')}`\n"
                f"   {r['motivo']} — {fecha}\n\n"
            )

        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message, texto, markup, editar=editar)

    except Exception as e:
        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message, f"❌ Error: {e}", markup, editar=editar)


# ── Configuración ─────────────────────────────────────────────────────────────

async def mostrar_config(message: Message, pagina: int = 0,
                         seleccion: int | None = None,
                         editar: bool = False) -> None:
    """Vista de configuración — lista paginada con botones de selección y edición.

    Layout inspirado en bots musicales:
      Lista numerada de claves (10 por página)
      Botones 1-10 para seleccionar una clave
      ⬅ página anterior  |  ➡ página siguiente
      Si hay selección activa: muestra detalle + botón ✏️ Editar
      🏠 Inicio siempre al final
    """
    POR_PAG = 10

    try:
        resp = db.client.table("configuracion").select(
            "clave, valor, descripcion"
        ).order("clave").execute()
        configs = resp.data or []
    except Exception as e:
        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message, f"❌ Error cargando configs: {e}", markup, editar=editar)
        return

    total      = len(configs)
    total_pags = max(1, (total + POR_PAG - 1) // POR_PAG)
    pagina     = max(0, min(pagina, total_pags - 1))
    inicio     = pagina * POR_PAG
    lote       = configs[inicio:inicio + POR_PAG]

    # ── Texto: lista numerada (texto plano — valores de BD sin escapar) ─────────
    sel_cfg = None
    if seleccion is not None and 0 <= seleccion < len(lote):
        sel_cfg = lote[seleccion]

    texto  = "<b>⚙️ Configuración del sistema</b>\n"
    texto += f"<i>Página {pagina+1} de {total_pags} — {total} parámetros</i>\n\n"

    for i, c in enumerate(lote):
        n          = i + 1
        valor      = c.get('valor', '—')
        desc_safe  = _html.escape((c.get('descripcion') or c['clave']).strip())
        valor_safe = _html.escape(str(valor))

        if sel_cfg and c['clave'] == sel_cfg['clave']:
            texto += f"▶ <b>{n}. {desc_safe}:</b> <code>{valor_safe}</code>\n"
            texto += f"   <i>Clave: {_html.escape(c['clave'])}</i>\n\n"
        else:
            texto += f"{n}. {desc_safe}: <code>{valor_safe}</code>\n"

    # ── Botones: números 1-N para seleccionar ────────────────────────────────
    botones = []

    # Fila(s) de números — máx 5 por fila
    nums_fila = []
    for i in range(len(lote)):
        n = i + 1
        # Marcar el seleccionado con un símbolo distinto
        label = f"[{n}]" if sel_cfg and lote[i]['clave'] == sel_cfg['clave'] else str(n)
        nums_fila.append(InlineKeyboardButton(
            label, callback_data=f"cfg_sel_{pagina}_{i}"
        ))
        if len(nums_fila) == 5:
            botones.append(nums_fila)
            nums_fila = []
    if nums_fila:
        botones.append(nums_fila)

    # Fila de edición — solo si hay selección
    if sel_cfg:
        botones.append([
            InlineKeyboardButton(
                f"✏️ Editar: {sel_cfg['clave'][:20]}",
                callback_data=f"cfg_edit_{sel_cfg['clave']}"
            )
        ])

    # Paginación
    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"cfg_pg_{pagina-1}"))
    nav.append(InlineKeyboardButton(
        f"· {pagina+1}/{total_pags} ·", callback_data="noop"
    ))
    if pagina < total_pags - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"cfg_pg_{pagina+1}"))
    botones.append(nav)

    # Inicio
    botones.append(_btn_inicio())

    await _enviar(message, texto, InlineKeyboardMarkup(botones),
                  parse_mode="HTML", editar=editar)


async def mostrar_editar_config(message: Message, clave: str,
                                pagina: int = 0, editar: bool = False) -> None:
    """Pantalla de edición de un parámetro — exclusiva del owner.
    Muestra valor actual, tipo esperado e instrucciones.
    El owner responde con texto libre que handle_texto_admin procesa.
    """
    try:
        resp = db.client.table("configuracion").select(
            "clave, valor, descripcion"
        ).eq("clave", clave).limit(1).execute()
        cfg = resp.data[0] if resp.data else None
    except Exception:
        cfg = None

    if not cfg:
        markup = InlineKeyboardMarkup([_btn_inicio()])
        await _enviar(message, "❌ Configuración no encontrada.",
                      markup, parse_mode=None, editar=editar)
        return

    desc      = cfg.get('descripcion') or clave
    valor_act = cfg.get('valor', '—')
    tipo_hint = _inferir_tipo_hint(valor_act)

    texto = (
        f"✏️ Editando configuración\n\n"
        f"📋 {desc}\n"
        f"🔑 Clave: {clave}\n"
        f"📌 Valor actual: {valor_act}\n\n"
        f"Escribe el nuevo valor {tipo_hint}:\n"
        f"(toca Cancelar o escribe /cancelar para descartar)"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"cfg_pg_{pagina}")]
    ])
    await _enviar(message, texto, markup, parse_mode=None, editar=editar)


async def mostrar_eliminar_admin(message: Message, editar: bool = False) -> None:
    """Vista para eliminar un admin — lista con botón por cada uno."""
    admins = db.get_admins()
    activos = [a for a in admins if a.get('activo')]

    if not activos:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Volver", callback_data="cmd_admins")],
            _btn_inicio(),
        ])
        await _enviar(message, "📭 No hay admins activos para eliminar.",
                      markup, parse_mode=None, editar=editar)
        return

    texto = "<b>🗑 Eliminar admin</b>\n\n"
    texto += "Selecciona el admin a desactivar:\n\n"
    for a in activos:
        nombre = _html.escape(a.get('nombre_admin') or '?')
        email  = _html.escape(a.get('email', ''))
        texto += f"• <b>{nombre}</b> — <code>{email}</code>\n"

    botones = []
    for a in activos:
        nombre = a.get('nombre_admin') or '?'
        email  = a.get('email', '')
        botones.append([InlineKeyboardButton(
            f"🗑 {nombre}",
            callback_data=f"del_admin_{email[:30]}"
        )])
    botones.append([InlineKeyboardButton("🔙 Volver", callback_data="cmd_admins")])
    botones.append(_btn_inicio())

    await _enviar(message, texto, InlineKeyboardMarkup(botones),
                  parse_mode="HTML", editar=editar)


async def mostrar_confirmar_eliminar_admin(message: Message, email: str,
                                           editar: bool = False) -> None:
    """Pantalla de confirmación antes de desactivar un admin."""
    admins = db.get_admins()
    admin  = next((a for a in admins if a.get('email', '') == email), None)
    nombre = admin.get('nombre_admin', email) if admin else email

    texto = (
        f"⚠️ <b>¿Desactivar este admin?</b>\n\n"
        f"👤 <b>{_html.escape(nombre)}</b>\n"
        f"📧 <code>{_html.escape(email)}</code>\n\n"
        f"<i>El admin perderá acceso a la app inmediatamente.</i>"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Sí, desactivar", callback_data=f"confirmar_del_admin_{email[:30]}"),
            InlineKeyboardButton("❌ No",             callback_data="cmd_admin_eliminar"),
        ],
        _btn_inicio(),
    ])
    await _enviar(message, texto, markup, parse_mode="HTML", editar=editar)



async def mostrar_lista_busqueda(message: Message, contactos: list, query_texto: str,
                                  user_id: str, pagina: int = 1,
                                  editar: bool = False) -> None:
    """Lista paginada de resultados de búsqueda."""
    cache_resultados_set(user_id, {'contactos': contactos, 'query': query_texto})
    total      = len(contactos)
    total_pags = max(1, (total + 9) // 10)
    inicio     = (pagina - 1) * 10
    items      = contactos[inicio:inicio + 10]
    texto, markup_busqueda = _formato_lista_compacta(
        items, inicio + 1, total, pagina, total_pags, query_texto
    )
    # Agregar botón inicio preservando los botones de paginación existentes
    botones = list(markup_busqueda.inline_keyboard) + [_btn_inicio()]
    await _enviar(message, texto, InlineKeyboardMarkup(botones),
                  parse_mode="MarkdownV2", editar=editar)
