"""
Formatting utilities for contact display.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def formatear_contacto(contacto: dict, mostrar_id: bool = False, db=None) -> str:
    """Formatear un contacto estilo profesional.
    
    Args:
        contacto: dict with contact data
        mostrar_id: whether to show the contact ID
        db: SupabaseService instance (if None, imported from helpers)
    """
    if db is None:
        from utils.helpers import db

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


def _formato_lista_compacta(contactos: list, inicio_num: int, total: int, pagina: int, total_pags: int, query_texto: str = "") -> tuple[str, InlineKeyboardMarkup]:
    """Genera el mensaje de lista numerada compacta + botones de paginación."""
    lineas = []
    for i, c in enumerate(contactos):
        num = inicio_num + i
        nombre = f"{c['nombre']} {c['apellido']}"
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
