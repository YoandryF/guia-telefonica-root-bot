"""
Formatting utilities for contact display.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def formatear_contacto(contacto: dict, mostrar_id: bool = False, db=None) -> str:
    """Formatea un contacto con todos sus datos disponibles."""
    if db is None:
        from utils.helpers import db

    info = db.get_info_reportes(contacto['id'])
    mostrar_badge = info['mostrar']
    verificado    = info['verificado']
    warning       = " ⚠️" if mostrar_badge else ""
    nombre        = f"{contacto['nombre']} {contacto['apellido']}".upper()

    texto = f"📋 *Detalles del contacto:*{warning}\n\n"

    if mostrar_id:
        texto += f"• 🔑 ID: `{contacto['id'][:8]}`\n"

    texto += f"• 📱 Número: `{contacto['telefono']}`\n"
    texto += f"• 👤 Nombre: {nombre}\n"

    if contacto.get('ci'):
        texto += f"• 🆔 CI: `{contacto['ci']}`\n"

    # Ubicación
    provincia = contacto.get('provincia') or ''
    municipio = contacto.get('municipio') or ''
    if municipio and provincia:
        texto += f"• 📍 Ubicación: {municipio}, {provincia}\n"
    elif provincia:
        texto += f"• 📍 Provincia: {provincia}\n"

    if contacto.get('direccion'):
        texto += f"• 🏠 Dirección: {contacto['direccion']}\n"

    if contacto.get('categoria_nombre'):
        icono = contacto.get('categoria_icono') or '📂'
        texto += f"• {icono} Categoría: {contacto['categoria_nombre']}\n"

    # Links de contacto
    tel = contacto['telefono'].replace('-', '').replace(' ', '')
    if len(tel) >= 8:
        num = tel if tel.startswith('+') else f"53{tel}" if len(tel) == 8 else tel
        texto += f"• 📲 [Telegram](https://t.me/+{num}) | [WhatsApp](https://wa.me/{num})\n"

    # Badge de riesgo
    if mostrar_badge:
        if verificado:
            texto += f"\n🔴 *Contacto verificado como riesgoso*\n"
        else:
            total = info['pendientes']
            texto += f"\n⚠️ _Reportado {total} {'vez' if total == 1 else 'veces'}_\n"
    elif contacto.get('verificado'):
        texto += f"\n✅ _Contacto verificado_\n"

    texto += f"\n_@GuiaTelefonicaRootBot_"
    return texto


def teclado_contacto(contacto: dict, es_admin: bool = False) -> InlineKeyboardMarkup:
    """Genera el teclado inline con acciones para un contacto."""
    cid   = contacto['id']
    cid8  = cid[:8]
    tel   = contacto['telefono'].replace('-', '').replace(' ', '')
    num   = tel if tel.startswith('+') else f"53{tel}" if len(tel) == 8 else tel

    botones = [
        # Fila 1: acciones de comunicación
        [
            InlineKeyboardButton("📲 Telegram", url=f"https://t.me/+{num}"),
            InlineKeyboardButton("💬 WhatsApp", url=f"https://wa.me/{num}"),
        ],
        # Fila 2: acciones sociales
        [
            InlineKeyboardButton("⚠️ Reportar", callback_data=f"reportar_{cid8}"),
            InlineKeyboardButton("👍 Avalar",   callback_data=f"avalar_{cid8}"),
        ],
    ]

    if es_admin:
        botones.append([
            InlineKeyboardButton("✅ Aprobar",  callback_data=f"aprobar_{cid8}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar_{cid8}"),
            InlineKeyboardButton("🗑 Eliminar", callback_data=f"confirmar_del_{cid8}"),
        ])

    return InlineKeyboardMarkup(botones)


def _formato_lista_compacta(
    contactos: list,
    inicio_num: int,
    total: int,
    pagina: int,
    total_pags: int,
    query_texto: str = "",
) -> tuple[str, InlineKeyboardMarkup]:
    """Lista numerada compacta + botón 'Ver' por contacto + paginación."""

    lineas = []
    for i, c in enumerate(contactos):
        num    = inicio_num + i
        nombre = f"{c['nombre']} {c['apellido']}"
        if len(nombre) > 22:
            nombre = nombre[:20] + "…"
        tel  = c['telefono']
        mun  = c.get('municipio') or ''
        prov = c.get('provincia') or ''
        ubi  = f"{mun}, {prov}" if mun and prov else prov or mun

        linea  = f"*{num}.* {nombre.upper()}\n"
        linea += f"   📱 `{tel}`\n"
        if ubi:
            linea += f"   📍 {ubi}\n"
        lineas.append(linea)

    texto  = "".join(lineas)
    texto += f"\n📊 {inicio_num}–{inicio_num + len(contactos) - 1} de *{total}*"

    # Botones: uno por contacto para ver detalle directo
    botones = []
    for i, c in enumerate(contactos):
        num   = inicio_num + i
        cid8  = c['id'][:8]
        label = f"{num}. {c['telefono']}"
        botones.append([InlineKeyboardButton(f"🔍 {label}", callback_data=f"ver_{cid8}")])

    # Paginación
    nav = []
    prefijo = f"pg_{query_texto}_" if query_texto else "pg__"
    if pagina > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{prefijo}{pagina - 1}"))
    if pagina < total_pags:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{prefijo}{pagina + 1}"))
    if nav:
        botones.append(nav)

    return texto, InlineKeyboardMarkup(botones)
