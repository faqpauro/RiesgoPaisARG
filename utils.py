from __future__ import annotations
import requests
import pytz
from datetime import datetime
from io import BytesIO
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def notificar_telegram(mensaje: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram no configurado; mensaje no enviado.")
        return
    ts = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")
    texto = f"[{ts}] {mensaje}"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"No se pudo enviar a Telegram: {e}")

def calcular_porcentaje_cambio(nuevo_valor, ultimo_valor):
    """Calcula el porcentaje de cambio entre el nuevo valor y el último valor."""
    if ultimo_valor is None or ultimo_valor == 0:
        return 0
    return ((nuevo_valor - ultimo_valor) / ultimo_valor) * 100

def calcular_porcentaje_cambio_diario(nuevo_valor, valor_dia_anterior):
    """Calcula el porcentaje de cambio diario en base al valor del día anterior."""
    if valor_dia_anterior is None or valor_dia_anterior == 0:
        return 0
    return ((nuevo_valor - valor_dia_anterior) / valor_dia_anterior) * 100

def traducir_fecha(fecha: datetime) -> str:
    """Traduce el nombre del mes en una fecha."""
    meses = {
        "January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
        "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
        "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
    }
    fecha_str = fecha.strftime("%d de %B")
    for mes_ing, mes_esp in meses.items():
        fecha_str = fecha_str.replace(mes_ing, mes_esp)
    return fecha_str

def obtener_mejor_valor_desde_fecha(valor_actual, historico):
    """Determina la fecha más reciente con un valor inferior al valor actual."""
    mejor_fecha = None
    mejor_valor = None
    for fecha, valor in sorted(historico, key=lambda x: x[0], reverse=True):
        if valor < valor_actual:
            mejor_fecha = fecha
            mejor_valor = valor
            break
    return mejor_fecha, mejor_valor

def enviar_grafico_moderacion_telegram(imagen_bytes: BytesIO) -> int | None:
    """Envía el gráfico a Telegram para aprobación con botones interactivos y retorna el message_id."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram no configurado para moderación.")
        return None
    
    import json
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Aceptar", "callback_data": "aprobar_grafico"},
                {"text": "❌ Rechazar", "callback_data": "rechazar_grafico"}
            ]
        ]
    }
    
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": "📊 *Evolución Histórica - Riesgo País*\n¿Deseas publicar este gráfico en X (Twitter)?",
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(reply_markup)
    }
    
    files = {
        "photo": ("grafico.png", imagen_bytes.getvalue(), "image/png")
    }
    
    try:
        r = requests.post(url, data=data, files=files, timeout=15)
        res = r.json()
        if res.get("ok"):
            return res["result"]["message_id"]
        else:
            print(f"Error de Telegram al enviar foto: {res}")
            return None
    except Exception as e:
        print(f"No se pudo enviar foto de moderación a Telegram: {e}")
        return None

def editar_mensaje_moderacion(message_id: int, nuevo_texto: str):
    """Edita la descripción de la foto de moderación en Telegram y remueve los botones."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageCaption"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "caption": nuevo_texto,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": []}  # Vacío para remover los botones
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"No se pudo editar el mensaje de moderación: {e}")

def esperar_decision_moderacion(message_id: int, timeout_minutos: int = 720) -> bool | None:
    """Realiza consultas en getUpdates para capturar la respuesta del usuario (Aceptar o Rechazar)."""
    if not TELEGRAM_BOT_TOKEN:
        return False
        
    import time
    start_time = time.time()
    offset = None
    
    # Obtener el offset inicial para saltear actualizaciones viejas
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params={"limit": 100}, timeout=10)
        res = r.json()
        if res.get("ok") and res.get("result"):
            offset = res["result"][-1]["update_id"] + 1
    except Exception as e:
        print(f"Error al obtener offset inicial de Telegram: {e}")
        
    print(f"Esperando decisión de moderación en Telegram para el mensaje {message_id}...")
    
    while (time.time() - start_time) < (timeout_minutos * 60):
        try:
            params = {"timeout": 10, "limit": 10}
            if offset is not None:
                params["offset"] = offset
                
            r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params=params, timeout=15)
            res = r.json()
            
            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    
                    callback = update.get("callback_query")
                    if callback:
                        msg = callback.get("message", {})
                        if msg.get("message_id") == message_id:
                            data = callback.get("data")
                            query_id = callback.get("id")
                            
                            # Responder a Telegram para desactivar el indicador visual de carga del botón
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", 
                                          json={"callback_query_id": query_id}, timeout=10)
                            
                            if data == "aprobar_grafico":
                                editar_mensaje_moderacion(message_id, "✅ *Gráfico Aprobado*: Publicando en X...")
                                return True
                            elif data == "rechazar_grafico":
                                editar_mensaje_moderacion(message_id, "❌ *Gráfico Rechazado*: No se publicará en X.")
                                return False
                                
        except Exception as e:
            print(f"Error en consulta de getUpdates de moderación: {e}")
            
        time.sleep(10)
        
    # Expiración
    editar_mensaje_moderacion(message_id, "⚠️ *Moderación Expirada*: El gráfico no se publicó por falta de respuesta.")
    return None
