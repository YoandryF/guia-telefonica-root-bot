"""
Formatting utilities for contact display.
"""
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def _esc(text: str) -> str:
    """Escapa caracteres especiales para MarkdownV2."""
    if not text:
        return ''
    for ch in r'_*[]()~`>#+-=|{}.!\\':
        text = text.replace(ch, f'\\{ch}')
    return text


def formatear_contacto(contacto: dict, mostrar_id: bool = False, db=None) -> str:
    """Ficha de contacto con diseño blockquote estilo MarkdownV2."""
    if db is None:
        from utils.helpers import db

    info         = db.get_info_reportes(contacto['id'])
    tiene_badge  = info['mostrar']
    verificado   = info['verificado']
    nombre       = f"{contacto['nombre']} {contacto['apellido']}".upper()

    # Cabecera con estado de riesgo
    if verificado:
        estado = "⛔ *RIESGO CONFIRMADO*"
    elif tiene_badge:
        n_rep  = info.get('pendientes', 0)
        estado = f"🔴 *REPORTADO* \\— {n_rep} {'reporte' if n_rep == 1 else 'reportes'}"
    else:
        estado = "🟢 *SIN ALERTAS*"

    lineas = [f"📱 `{_esc(contacto['telefono'])}`\n"]
    lineas.append(f"{estado}\n")

    # Bloque de datos en blockquote
    lineas.append(f"> 👤 {_esc(nombre)}")

    provincia = contacto.get('provincia') or ''
    municipio = contacto.get('municipio') or ''
    if municipio and provincia:
        lineas.append(f"> 📍 {_esc(municipio)}, {_esc(provincia)}")
    elif provincia:
        lineas.append(f"> 📍 {_esc(provincia)}")

    if contacto.get('categoria_nombre'):
        icono = _esc(contacto.get('categoria_icono') or '📂')
        lineas.append(f"> {icono} {_esc(contacto['categoria_nombre'])}")

    if mostrar_id:
        lineas.append(f"> 🔑 `{contacto['id'][:8]}`")

    # Links de contacto
    tel = contacto['telefono'].replace('-','').replace(' ','')
    if len(tel) >= 8:
        num = tel if tel.startswith('+') else f"53{tel}" if len(tel) == 8 else tel
        lineas.append(f"\n📲 [Telegram](https://t\\.me/\\+{num})  •  [WhatsApp](https://wa\\.me/{num})")

    # Badge de riesgo con detalle
    if tiene_badge:
        if verificado:
            lineas.append("\n⚠️ _Verificado como riesgoso por el administrador_")
        else:
            lineas.append(f"\n⚠️ _Reportado {info.get('pendientes',0)} {'vez' if info.get('pendientes',0)==1 else 'veces'} por usuarios_")
    elif contacto.get('verificado'):
        lineas.append("\n✅ _Contacto verificado_")

    lineas.append("\n_@GuiaTelefonicaRootBot_")

    return '\n'.join(lineas)


def teclado_contacto(contacto: dict, es_admin: bool = False) -> InlineKeyboardMarkup:
    """Teclado inline con acciones para un contacto."""
    cid8 = contacto['id'][:8]
    tel  = contacto['telefono'].replace('-','').replace(' ','')
    num  = tel if tel.startswith('+') else f"53{tel}" if len(tel) == 8 else tel

    botones = [
        [
            InlineKeyboardButton("📲 Telegram",  url=f"https://t.me/+{num}"),
            InlineKeyboardButton("💬 WhatsApp",  url=f"https://wa.me/{num}"),
        ],
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
    """Lista numerada compacta con blockquotes + botón Ver por contacto."""

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

        # Indicador de riesgo
        riesgo = ''
        if c.get('reporte_confirmado') or c.get('verificado') == False and c.get('tiene_reportes'):
            riesgo = ' 🔴'
        elif c.get('tiene_reportes'):
            riesgo = ' ⚠️'

        linea  = f"*{num}\\.* {_esc(nombre.upper())}{riesgo}\n"
        linea += f"  `{_esc(tel)}`"
        if ubi:
            linea += f" • {_esc(ubi)}"
        linea += "\n"
        lineas.append(linea)

    texto  = "".join(lineas)
    texto += f"\n_Mostrando {inicio_num}–{inicio_num + len(contactos) - 1} de {total}_"

    # Botón Ver por contacto
    botones = []
    for i, c in enumerate(contactos):
        num  = inicio_num + i
        cid8 = c['id'][:8]
        botones.append([InlineKeyboardButton(
            f"🔍 {num}. {c['telefono']}", callback_data=f"ver_{cid8}"
        )])

    # Paginación
    nav     = []
    prefijo = f"pg_{query_texto}_" if query_texto else "pg__"
    if pagina > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{prefijo}{pagina-1}"))
    if pagina < total_pags:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{prefijo}{pagina+1}"))
    if nav:
        botones.append(nav)

    return texto, InlineKeyboardMarkup(botones)
