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
                .is_("deleted_at", None)
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
                .is_("deleted_at", None)
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
                .is_("deleted_at", None)
                .order("fecha_creacion", desc=False)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo pendientes: {e}")
            return []

    def buscar_por_telefono(self, telefono: str) -> dict:
        """Buscar contacto por teléfono (normalizado)"""
        if not self._check_client():
            return None

        try:
            # Normalizar: solo dígitos
            tel_limpio = ''.join(c for c in telefono if c.isdigit())

            # Intentar búsqueda directa
            response = (
                self.client.table("contactos")
                .select("*")
                .ilike("telefono", f"%{telefono}%")
                .is_("deleted_at", None)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]

            # Si no encuentra, buscar con solo dígitos
            if tel_limpio != telefono:
                response = (
                    self.client.table("contactos")
                    .select("*")
                    .ilike("telefono", f"%{tel_limpio}%")
                    .is_("deleted_at", None)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return response.data[0]

            # Intentar con los últimos 8 dígitos (sin código país)
            if len(tel_limpio) > 8:
                ultimos8 = tel_limpio[-8:]
                response = (
                    self.client.table("contactos")
                    .select("*")
                    .ilike("telefono", f"%{ultimos8}%")
                    .is_("deleted_at", None)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return response.data[0]

            return None
        except Exception as e:
            logger.error(f"Error buscando por teléfono: {e}")
            return None

    def buscar_por_id_o_telefono(self, identificador: str) -> dict:
        """Buscar contacto por ID parcial o teléfono"""
        if not self._check_client():
            return None

        try:
            # Primero intentar por ID
            response = (
                self.client.table("contactos")
                .select("*")
                .like("id", f"{identificador}%")
                .is_("deleted_at", None)
                .execute()
            )
            if response.data:
                return response.data[0]

            # Si no, buscar por teléfono
            return self.buscar_por_telefono(identificador)
        except Exception as e:
            logger.error(f"Error buscando contacto: {e}")
            return None

    def get_contactos_por_creador(self, chat_id: str) -> list:
        """Obtener contactos registrados por un usuario"""
        if not self._check_client():
            return []

        try:
            response = (
                self.client.table("contactos")
                .select("*")
                .eq("creado_por", chat_id)
                .is_("deleted_at", None)
                .order("fecha_creacion", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo contactos por creador: {e}")
            return []

    def aprobar_contacto(self, identificador: str, aprobado_por: str = None) -> dict:
        """Aprobar un contacto pendiente (busca por ID parcial o teléfono)"""
        if not self._check_client():
            return {"error": "BD no disponible"}

        try:
            # Buscar por ID parcial
            response = (
                self.client.table("contactos")
                .select("*")
                .like("id", f"{identificador}%")
                .eq("estado", "pendiente")
                .execute()
            )

            # Si no, buscar por teléfono
            if not response.data:
                response = (
                    self.client.table("contactos")
                    .select("*")
                    .ilike("telefono", f"%{identificador}%")
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

    def rechazar_contacto(self, identificador: str, motivo: str = None) -> dict:
        """Rechazar un contacto pendiente (busca por ID parcial o teléfono)"""
        if not self._check_client():
            return {"error": "BD no disponible"}

        try:
            # Buscar por ID parcial
            response = (
                self.client.table("contactos")
                .select("*")
                .like("id", f"{identificador}%")
                .eq("estado", "pendiente")
                .execute()
            )

            # Si no, buscar por teléfono
            if not response.data:
                response = (
                    self.client.table("contactos")
                    .select("*")
                    .ilike("telefono", f"%{identificador}%")
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
            aprobados = self.client.table("contactos").select("id", count="exact").eq("estado", "aprobado").is_("deleted_at", None).execute()
            pendientes = self.client.table("contactos").select("id", count="exact").eq("estado", "pendiente").is_("deleted_at", None).execute()
            rechazados = self.client.table("contactos").select("id", count="exact").eq("estado", "rechazado").is_("deleted_at", None).execute()
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
    # REPORTES
    # ============================================

    def reportar_contacto(self, contacto_id: str, motivo: str, descripcion: str = None, reportado_por: str = None) -> dict:
        """Reportar un contacto"""
        if not self._check_client():
            return {"error": "BD no disponible"}
        try:
            self.client.table("reportes").insert({
                "contacto_id": contacto_id,
                "motivo": motivo,
                "descripcion": descripcion,
                "reportado_por": reportado_por,
                "reportado_desde": "telegram",
            }).execute()
            return {"data": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def get_conteo_reportes(self, contacto_id: str) -> int:
        """Obtener cantidad de reportes activos de un contacto"""
        if not self._check_client():
            return 0
        try:
            response = self.client.table("reportes").select("id", count="exact").eq("contacto_id", contacto_id).in_("estado", ["pendiente", "revisado"]).execute()
            return response.count or 0
        except Exception:
            return 0

    def get_info_reportes(self, contacto_id: str) -> dict:
        """Info detallada de reportes: aprobados, pendientes, mostrarBadge"""
        if not self._check_client():
            return {"aprobados": 0, "pendientes": 0, "mostrar": False, "verificado": False}
        try:
            aprobados = self.client.table("reportes").select("id", count="exact").eq("contacto_id", contacto_id).eq("estado", "revisado").execute()
            pendientes = self.client.table("reportes").select("id", count="exact").eq("contacto_id", contacto_id).eq("estado", "pendiente").execute()
            a = aprobados.count or 0
            p = pendientes.count or 0
            return {"aprobados": a, "pendientes": p, "mostrar": a >= 1 or p >= 3, "verificado": a >= 1}
        except Exception:
            return {"aprobados": 0, "pendientes": 0, "mostrar": False, "verificado": False}

    def get_reportes_pendientes(self) -> list:
        """Obtener reportes pendientes con datos del contacto"""
        if not self._check_client():
            return []
        try:
            response = self.client.table("reportes").select("*, contactos(nombre, apellido, telefono)").eq("estado", "pendiente").order("fecha_reporte").execute()
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo reportes: {e}")
            return []

    def desestimar_reporte(self, reporte_id: str) -> dict:
        """Desestimar un reporte"""
        if not self._check_client():
            return {"error": "BD no disponible"}
        try:
            response = self.client.table("reportes").update({"estado": "resuelto"}).like("id", f"{reporte_id}%").execute()
            if not response.data:
                return {"error": "Reporte no encontrado"}
            return {"data": "ok"}
        except Exception as e:
            return {"error": str(e)}

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

    # ============================================
    # GESTIÓN DE ADMINS
    # ============================================

    def crear_admin(self, email: str, password: str, nombre: str) -> dict:
        """Crear un nuevo usuario admin (auth + tabla admins)"""
        if not self._check_client():
            return {"error": "BD no disponible"}

        try:
            # Crear usuario en Supabase Auth
            auth_response = self.client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
            })

            user_id = auth_response.user.id

            # Registrar en tabla admins
            self.client.table("admins").insert({
                "user_id": user_id,
                "email": email,
                "nombre_admin": nombre,
                "activo": True,
            }).execute()

            return {"data": {"email": email, "nombre": nombre}}
        except Exception as e:
            logger.error(f"Error creando admin: {e}")
            return {"error": str(e)}

    def get_admins(self) -> list:
        """Obtener lista de admins"""
        if not self._check_client():
            return []

        try:
            response = self.client.table("admins").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"Error obteniendo admins: {e}")
            return []

    def desactivar_admin(self, email: str) -> dict:
        """Desactivar un admin por email"""
        if not self._check_client():
            return {"error": "BD no disponible"}

        try:
            response = (
                self.client.table("admins")
                .update({"activo": False})
                .eq("email", email)
                .execute()
            )

            if not response.data:
                return {"error": "Admin no encontrado"}

            return {"data": response.data[0]}
        except Exception as e:
            logger.error(f"Error desactivando admin: {e}")
            return {"error": str(e)}
