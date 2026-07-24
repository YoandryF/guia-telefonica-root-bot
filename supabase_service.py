"""
Servicio de Supabase para la Guía Telefónica
Maneja todas las operaciones con la base de datos
"""

import os
import logging
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            logger.error("SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no configurados")
            self.client = None
            return

        self.client: Client = create_client(url, key)

    def _check_client(self) -> bool:
        if not self.client:
            logger.error("Cliente Supabase no inicializado")
            return False
        return True

    # ============================================
    # CONTACTOS
    # ============================================

    def get_contactos_aprobados(self) -> list:
        """Obtener todos los contactos aprobados"""
        if not self._check_client():
            return []

        try:
            response = (
                self.client.table("contactos")
                .select("*, categorias(nombre, icono)")
                .eq("estado", "aprobado")
                .is_("deleted_at", "null")
                .order("nombre")
                .execute()
            )
            # Aplanar categoría
            contactos = []
            for c in response.data:
                if c.get("categorias"):
                    c["categoria_nombre"] = f"{c['categorias']['icono']} {c['categorias']['nombre']}"
                else:
                    c["categoria_nombre"] = None
                contactos.append(c)
            return contactos
        except Exception as e:
            logger.error(f"Error obteniendo contactos aprobados: {e}")
            return []

    def buscar_contactos(self, query: str) -> list:
        """Buscar contactos aprobados por nombre/teléfono/CI"""
        if not self._check_client():
            return []

        try:
            response = (
                self.client.table("contactos")
                .select("*, categorias(nombre, icono)")
                .eq("estado", "aprobado")
                .is_("deleted_at", "null")
                .or_(
                    f"nombre.ilike.%{query}%,"
                    f"apellido.ilike.%{query}%,"
                    f"telefono.ilike.%{query}%,"
                    f"ci.ilike.%{query}%"
                )
                .order("nombre")
                .execute()
            )
            contactos = []
            for c in response.data:
                if c.get("categorias"):
                    c["categoria_nombre"] = f"{c['categorias']['icono']} {c['categorias']['nombre']}"
                else:
                    c["categoria_nombre"] = None
                contactos.append(c)
            return contactos
        except Exception as e:
            logger.error(f"Error buscando contactos: {e}")
            return []

    def registrar_contacto(self, nombre: str, apellido: str, telefono: str,
                           direccion: str = None, ci: str = None,
                           creado_por: str = None, creado_desde: str = "telegram") -> dict:
        """Registrar nuevo contacto (estado pendiente)"""
        if not self._check_client():
            return {"error": "BD no disponible"}

        try:
            data = {
                "nombre": nombre,
                "apellido": apellido,
                "telefono": telefono,
                "estado": "pendiente",
                "creado_por": creado_por,
                "creado_desde": creado_desde,
            }
            if direccion:
                data["direccion"] = direccion
            if ci:
                data["ci"] = ci

            response = self.client.table("contactos").insert(data).execute()
            return {"data": response.data[0] if response.data else None}
        except Exception as e:
            logger.error(f"Error registrando contacto: {e}")
            return {"error": str(e)}

    def get_contactos_pendientes(self) -> list:
        """Obtener contactos pendientes de aprobación"""
        if not self._check_client():
            return []

        try:
            response = (
                self.client.table("contactos")
                .select("*")
                .eq("estado", "pendiente")
                .is_("deleted_at", "null")
                .order("fecha_creacion", desc=False)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo pendientes: {e}")
            return []

    def get_contactos_por_creador(self, chat_id: str) -> list:
        """Obtener contactos registrados por un usuario"""
        if not self._check_client():
            return []

        try:
            response = (
                self.client.table("contactos")
                .select("*")
                .eq("creado_por", chat_id)
                .is_("deleted_at", "null")
                .order("fecha_creacion", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo contactos por creador: {e}")
            return []

    def aprobar_contacto(self, contacto_id: str, aprobado_por: str = None) -> dict:
        """Aprobar un contacto pendiente"""
        if not self._check_client():
            return {"error": "BD no disponible"}

        try:
            # Buscar contacto por ID parcial
            response = (
                self.client.table("contactos")
                .select("*")
                .like("id", f"{contacto_id}%")
                .eq("estado", "pendiente")
                .execute()
            )

            if not response.data:
                return {"error": "Contacto no encontrado o ya procesado"}

            contacto = response.data[0]
            full_id = contacto["id"]

            # Actualizar estado
            update_response = (
                self.client.table("contactos")
                .update({
                    "estado": "aprobado",
                    "aprobado_por": aprobado_por,
                    "fecha_aprobacion": datetime.utcnow().isoformat(),
                    "ultima_modificacion": datetime.utcnow().isoformat(),
                })
                .eq("id", full_id)
                .execute()
            )

            # Registrar en historial
            self._registrar_historial(full_id, "aprobado", realizado_por=aprobado_por)

            return {"data": update_response.data[0] if update_response.data else contacto}
        except Exception as e:
            logger.error(f"Error aprobando contacto: {e}")
            return {"error": str(e)}

    def rechazar_contacto(self, contacto_id: str, motivo: str = None) -> dict:
        """Rechazar un contacto pendiente"""
        if not self._check_client():
            return {"error": "BD no disponible"}

        try:
            # Buscar contacto por ID parcial
            response = (
                self.client.table("contactos")
                .select("*")
                .like("id", f"{contacto_id}%")
                .eq("estado", "pendiente")
                .execute()
            )

            if not response.data:
                return {"error": "Contacto no encontrado o ya procesado"}

            contacto = response.data[0]
            full_id = contacto["id"]

            # Actualizar estado
            update_response = (
                self.client.table("contactos")
                .update({
                    "estado": "rechazado",
                    "motivo_rechazo": motivo,
                    "ultima_modificacion": datetime.utcnow().isoformat(),
                })
                .eq("id", full_id)
                .execute()
            )

            # Registrar en historial
            self._registrar_historial(full_id, "rechazado", realizado_por="admin")

            return {"data": update_response.data[0] if update_response.data else contacto}
        except Exception as e:
            logger.error(f"Error rechazando contacto: {e}")
            return {"error": str(e)}

    # ============================================
    # CATEGORÍAS
    # ============================================

    def get_categorias(self) -> list:
        """Obtener categorías activas"""
        if not self._check_client():
            return []

        try:
            response = (
                self.client.table("categorias")
                .select("*")
                .eq("activa", True)
                .order("nombre")
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo categorías: {e}")
            return []

    # ============================================
    # ESTADÍSTICAS
    # ============================================

    def get_estadisticas(self) -> dict:
        """Obtener estadísticas generales"""
        if not self._check_client():
            return {}

        try:
            aprobados = self.client.table("contactos").select("id", count="exact").eq("estado", "aprobado").is_("deleted_at", "null").execute()
            pendientes = self.client.table("contactos").select("id", count="exact").eq("estado", "pendiente").is_("deleted_at", "null").execute()
            rechazados = self.client.table("contactos").select("id", count="exact").eq("estado", "rechazado").is_("deleted_at", "null").execute()
            usuarios = self.client.table("usuarios_telegram").select("chat_id", count="exact").execute()

            return {
                "aprobados": aprobados.count or 0,
                "pendientes": pendientes.count or 0,
                "rechazados": rechazados.count or 0,
                "total": (aprobados.count or 0) + (pendientes.count or 0) + (rechazados.count or 0),
                "usuarios_telegram": usuarios.count or 0,
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}

    # ============================================
    # USUARIOS TELEGRAM
    # ============================================

    def registrar_usuario_telegram(self, chat_id: str, nombre_usuario: str = None,
                                   primer_nombre: str = None, ultimo_nombre: str = None):
        """Registrar o actualizar usuario de Telegram"""
        if not self._check_client():
            return

        try:
            self.client.table("usuarios_telegram").upsert({
                "chat_id": chat_id,
                "nombre_usuario": nombre_usuario,
                "primer_nombre": primer_nombre,
                "ultimo_nombre": ultimo_nombre,
                "ultima_interaccion": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            logger.error(f"Error registrando usuario telegram: {e}")

    # ============================================
    # HISTORIAL
    # ============================================

    def _registrar_historial(self, contacto_id: str, accion: str,
                             datos_anteriores: dict = None, datos_nuevos: dict = None,
                             realizado_por: str = None):
        """Registrar acción en historial"""
        try:
            self.client.table("historial").insert({
                "contacto_id": contacto_id,
                "accion": accion,
                "datos_anteriores": datos_anteriores,
                "datos_nuevos": datos_nuevos,
                "realizado_por": realizado_por,
            }).execute()
        except Exception as e:
            logger.error(f"Error registrando historial: {e}")

    # ============================================
    # HEALTH CHECK
    # ============================================

    def health_check(self) -> bool:
        """Verificar conexión con Supabase"""
        if not self._check_client():
            return False

        try:
            self.client.table("categorias").select("id").limit(1).execute()
            return True
        except Exception:
            return False
