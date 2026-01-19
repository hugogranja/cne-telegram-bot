#!/usr/bin/env python3
"""
Bot de Telegram - CNE Colombia
Consulta resoluciones del CNE usando Gemini AI
Deploy en Railway.app
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# Configuración desde variables de entorno
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

STORE_ID = 'fileSearchStores/resoluciones-cne-txt-201520-4yk268rd1sc8'

# Lista de modelos para rotación (cada uno tiene cuota separada ~5 req/min)
# Total: ~20 requests/minuto con 4 modelos
MODELOS = [
    'gemini-3-flash-preview',   # Más potente
    'gemini-2.5-flash',         # Muy bueno
    'gemini-2.0-flash',         # Rápido
    'gemini-2.0-flash-lite',    # Ligero
]

# Índice para rotación round-robin
modelo_actual_idx = 0

# Instrucción del sistema
INSTRUCCION_SISTEMA = """Eres un asistente experto en derecho electoral colombiano.
Tienes acceso a 5,976 resoluciones del Consejo Nacional Electoral (CNE) de Colombia.

IMPORTANTE: Al final de cada respuesta, SIEMPRE debes incluir una sección llamada
"RESOLUCIONES CONSULTADAS:" donde listes las resoluciones específicas del CNE que
utilizaste para responder. Usa el formato:
- Resolución No. XXXX de YYYY (tema principal)

Si no encontraste resoluciones específicas, indica "No se encontraron resoluciones específicas sobre este tema."
"""

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cliente de Google AI
google_client = None

def inicializar_google():
    """Inicializa el cliente de Google AI"""
    global google_client
    try:
        google_client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info("✅ Conectado a Google AI")
        return True
    except Exception as e:
        logger.error(f"❌ Error conectando a Google AI: {e}")
        return False

def consultar_cne(pregunta: str) -> str:
    """Consulta las resoluciones del CNE con rotación de modelos"""
    global modelo_actual_idx

    prompt_completo = f"""{INSTRUCCION_SISTEMA}

PREGUNTA DEL USUARIO:
{pregunta}

Responde de manera completa y al final incluye la sección "RESOLUCIONES CONSULTADAS:" con las resoluciones específicas del CNE que utilizaste."""

    # Intentar con todos los modelos en rotación round-robin
    intentos = 0
    max_intentos = len(MODELOS) * 2  # Dar 2 vueltas completas si es necesario

    while intentos < max_intentos:
        modelo = MODELOS[modelo_actual_idx]
        modelo_actual_idx = (modelo_actual_idx + 1) % len(MODELOS)  # Rotar al siguiente
        intentos += 1

        try:
            response = google_client.models.generate_content(
                model=modelo,
                contents=prompt_completo,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[STORE_ID]
                            )
                        )
                    ]
                )
            )

            if response.text:
                # Nombre corto del modelo para mostrar
                if "3-flash" in modelo:
                    modelo_corto = "G3-Flash"
                elif "2.5-flash" in modelo:
                    modelo_corto = "G2.5-Flash"
                elif "2.0-flash-lite" in modelo:
                    modelo_corto = "G2-Lite"
                else:
                    modelo_corto = "G2-Flash"

                logger.info(f"Respuesta exitosa con {modelo}")
                return f"🤖 *Respuesta* (_{modelo_corto}_):\n\n{response.text}"

        except Exception as e:
            error = str(e)
            if '429' in error or '503' in error:
                logger.warning(f"Modelo {modelo} en rate limit, rotando...")
                continue
            else:
                logger.error(f"Error en {modelo}: {error}")
                continue

    return "⚠️ No se pudo obtener respuesta. Todos los modelos están temporalmente ocupados. Intenta de nuevo en 30 segundos."

# Handlers de Telegram

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    mensaje = """
🏛️ *CHATBOT CNE - Consejo Nacional Electoral*

¡Bienvenido! Soy un asistente especializado en derecho electoral colombiano.

Tengo acceso a *5,976 resoluciones* del CNE (2023-2025).

*¿Cómo usarme?*
Simplemente escribe tu pregunta sobre:
• Candidaturas y requisitos
• Inhabilidades e incompatibilidades
• Financiamiento de campañas
• Propaganda electoral
• Doble militancia
• Tribunales de garantías
• Y mucho más...

*Comandos:*
/start - Ver este mensaje
/ayuda - Ejemplos de preguntas
/info - Información del sistema

_Escribe tu pregunta para comenzar..._
"""
    await update.message.reply_text(mensaje, parse_mode='Markdown')

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ayuda"""
    mensaje = """
📚 *EJEMPLOS DE PREGUNTAS*

• ¿Qué es la doble militancia y cuáles son sus sanciones?

• ¿Cuáles son los requisitos para inscribir una candidatura presidencial?

• ¿Qué inhabilidades existen para ser alcalde?

• ¿Cómo regula el CNE la propaganda electoral en vallas?

• ¿Cuáles son las funciones de los tribunales de garantías electorales?

• ¿Qué dice el CNE sobre el financiamiento de campañas políticas?

• ¿Cuáles son los topes de gastos para campañas?

_Escribe cualquier pregunta sobre derecho electoral colombiano..._
"""
    await update.message.reply_text(mensaje, parse_mode='Markdown')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /info"""
    mensaje = """
ℹ️ *INFORMACIÓN DEL SISTEMA*

📁 *Base de datos:*
   5,976 resoluciones del CNE

📅 *Período:*
   2023, 2024, 2025

🤖 *Modelos de IA:* (rotación automática)
   • Gemini 3 Flash Preview
   • Gemini 2.5 Flash
   • Gemini 2.0 Flash
   • Gemini 2.0 Flash Lite

🔍 *Tecnología:*
   Google AI File Search

⚡ *Tiempo de respuesta:*
   10-30 segundos aprox.

_Desarrollado para consultas de derecho electoral colombiano_
"""
    await update.message.reply_text(mensaje, parse_mode='Markdown')

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa los mensajes de texto (preguntas)"""
    pregunta = update.message.text
    user = update.effective_user

    logger.info(f"Pregunta de {user.first_name} ({user.id}): {pregunta[:50]}...")

    # Enviar mensaje de "escribiendo..."
    await update.message.chat.send_action('typing')

    # Mensaje de espera
    mensaje_espera = await update.message.reply_text(
        "🔍 _Buscando en 5,976 resoluciones del CNE..._",
        parse_mode='Markdown'
    )

    # Consultar
    respuesta = consultar_cne(pregunta)

    # Eliminar mensaje de espera
    try:
        await mensaje_espera.delete()
    except:
        pass

    # Enviar respuesta (dividir si es muy larga)
    if len(respuesta) > 4000:
        partes = [respuesta[i:i+4000] for i in range(0, len(respuesta), 4000)]
        for i, parte in enumerate(partes):
            try:
                if i == 0:
                    await update.message.reply_text(parte, parse_mode='Markdown')
                else:
                    await update.message.reply_text(f"_(continuación)_\n\n{parte}", parse_mode='Markdown')
            except:
                await update.message.reply_text(parte.replace('*', '').replace('_', ''))
    else:
        try:
            await update.message.reply_text(respuesta, parse_mode='Markdown')
        except:
            await update.message.reply_text(respuesta.replace('*', '').replace('_', ''))

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores"""
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "❌ Ocurrió un error procesando tu mensaje. Intenta de nuevo."
        )

def main():
    """Función principal"""

    # Verificar variables de entorno
    if not TELEGRAM_TOKEN:
        print("❌ ERROR: Falta TELEGRAM_TOKEN")
        return

    if not GOOGLE_API_KEY:
        print("❌ ERROR: Falta GOOGLE_API_KEY")
        return

    print("🤖 BOT DE TELEGRAM - CNE COLOMBIA")
    print("=" * 50)

    # Inicializar Google AI
    if not inicializar_google():
        print("❌ No se pudo conectar a Google AI")
        return

    # Crear aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Agregar handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("help", ayuda))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    app.add_error_handler(error_handler)

    # Iniciar bot
    print("✅ Bot iniciado - t.me/cne_colombia_bot")
    print("=" * 50)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
