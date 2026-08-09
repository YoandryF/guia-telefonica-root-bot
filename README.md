# 🤖 Guía Telefónica — Bot de Telegram

Bot de Telegram para la Guía Telefónica Colaborativa. Buscar, registrar, reportar y administrar contactos.

## 🔗 [@GuiaTelefonicaRootBot](https://t.me/GuiaTelefonicaRootBot)

## 📋 Comandos

### Públicos
| Comando | Descripción |
|---|---|
| `/start` | Bienvenida |
| `/ayuda` | Todos los comandos |
| `/listar [categoria]` | Ver contactos (paginado + filtro) |
| `/buscar texto` | Buscar por nombre/teléfono/CI |
| `/agregar` | Registrar contacto (interactivo) |
| `/miscontactos` | Mis registros |
| `/categorias` | Ver categorías |
| `/reportar` | Reportar contacto (interactivo) |
| `/avalar telefono` | Avalar contacto legítimo |
| `/reclamar telefono msg` | Derecho a réplica |
| `/verificarme telefono` | Verificar mi contacto (badge ✅) |
| `/listanegra` | Contactos reportados |
| `/cancelar_registro tel` | Cancelar mi pendiente |

### Admin
| Comando | Descripción |
|---|---|
| `/pendientes [filtro]` | Contactos por aprobar (botones) |
| `/aprobar tel` | Aprobar |
| `/rechazar tel motivo` | Rechazar |
| `/editar tel, campo, valor` | Editar contacto |
| `/eliminar tel` | Eliminar (con confirmación) |
| `/estadisticas` | Estadísticas |
| `/exportar csv\|json` | Exportar BD |
| `/reportes` | Ver reportes pendientes |
| `/desestimar id` | Desestimar reporte |
| `/reclamos` | Ver reclamos pendientes |
| `/verificar tel` | Verificar contacto manualmente |
| `/banear_reportador id` | Banear abusador |
| `/desbanear id` | Desbanear |

### Owner
| Comando | Descripción |
|---|---|
| `/registrar_admin email pass nombre` | Crear admin |
| `/listar_admins` | Ver admins |
| `/eliminar_admin email` | Desactivar admin |
| `/config` | Ver configuración (botones) |
| `/setconfig clave valor` | Cambiar configuración |

## 🛠️ Stack

- Python 3.11 + python-telegram-bot 21.3
- Supabase (service_role key)
- Flask (health check)
- Render.com (free tier)
- UptimeRobot (keep-alive)

## 🚀 Deploy

### Variables de entorno (Render)
```
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_ADMIN_CHAT_ID=xxx
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
PORT=10000
```

### Estructura
```
├── main.py              # Entry: Flask + bot polling
├── bot.py               # Comandos + callbacks
├── conversations.py     # Flujos interactivos
├── supabase_service.py  # Operaciones BD
├── requirements.txt
├── Dockerfile
└── render.yaml
```

## 📄 Licencia

MIT — [Yoandry Freire](https://github.com/YoandryF) / ROOT Ecosystem
