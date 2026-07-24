# 🤖 Guía Telefónica - Bot de Telegram

Bot de Telegram para la Guía Telefónica Colaborativa. Permite buscar, consultar y registrar contactos con sistema de aprobación administrativa.

## 🔗 Bot

[@GuiaTelefonicaRootBot](https://t.me/GuiaTelefonicaRootBot)

## 🛠️ Stack

- **Python 3.11** + python-telegram-bot
- **Supabase** (PostgreSQL) como base de datos
- **Flask** para health check
- **Render.com** para hosting (free tier)
- **UptimeRobot** para keep-alive

## 📋 Comandos

### Públicos
| Comando | Descripción |
|---------|-------------|
| `/start` | Mensaje de bienvenida |
| `/ayuda` | Lista de comandos |
| `/listar` | Ver contactos aprobados |
| `/buscar texto` | Buscar por nombre/teléfono/CI |
| `/agregar N, A, T` | Registrar nuevo contacto |
| `/miscontactos` | Mis contactos registrados |
| `/categorias` | Ver categorías disponibles |

### Admin
| Comando | Descripción |
|---------|-------------|
| `/pendientes` | Contactos por aprobar |
| `/aprobar id` | Aprobar contacto |
| `/rechazar id motivo` | Rechazar contacto |
| `/estadisticas` | Ver estadísticas |

## 🚀 Deploy

### Variables de entorno (Render)
```
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_ADMIN_CHAT_ID=xxx
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_xxx
PORT=10000
HEALTH_PORT=8080
```

### Deploy a Render
1. Conectar este repo en Render.com
2. Seleccionar "Web Service" → Docker
3. Configurar variables de entorno
4. Deploy automático en cada push

## 📁 Estructura
```
├── main.py              # Punto de entrada
├── bot.py               # Lógica del bot (comandos)
├── supabase_service.py  # Operaciones con BD
├── health_server.py     # Flask para UptimeRobot
├── requirements.txt     # Dependencias
├── Dockerfile           # Build para Render
├── render.yaml          # Config de deploy
└── .env.example         # Variables necesarias
```

## 📄 Licencia

MIT
