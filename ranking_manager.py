from __future__ import annotations
import time
import json
import requests
import pytz
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database import (
    leer_ranking_america,
    guardar_ranking_america,
    leer_ultimo_valor_guardado,
    leer_valor_dia_anterior
)

# Catálogo base de países de América
PAISES_CATALOGO = [
    {"name": "Uruguay", "iso": "uy", "code": "URU", "default_val": 62, "auto": False},
    {"name": "Chile", "iso": "cl", "code": "CHL", "default_val": 89, "auto": True, "bcrp_name": "Chile"},
    {"name": "Paraguay", "iso": "py", "code": "PRY", "default_val": 102, "auto": False},
    {"name": "Perú", "iso": "pe", "code": "PER", "default_val": 107, "auto": True, "bcrp_name": "Perú"},
    {"name": "Panamá", "iso": "pa", "code": "PAN", "default_val": 114, "auto": False},
    {"name": "Guatemala", "iso": "gt", "code": "GTM", "default_val": 116, "auto": False},
    {"name": "Costa Rica", "iso": "cr", "code": "CRI", "default_val": 129, "auto": False},
    {"name": "Honduras", "iso": "hn", "code": "HND", "default_val": 164, "auto": False},
    {"name": "República Dominicana", "iso": "do", "code": "DOM", "default_val": 165, "auto": False},
    {"name": "Brasil", "iso": "br", "code": "BRA", "default_val": 178, "auto": True, "bcrp_name": "Brasil"},
    {"name": "Colombia", "iso": "co", "code": "COL", "default_val": 191, "auto": True, "bcrp_name": "Colombia"},
    {"name": "México", "iso": "mx", "code": "MEX", "default_val": 190, "auto": True, "bcrp_name": "México"},
    {"name": "El Salvador", "iso": "sv", "code": "SLV", "default_val": 300, "auto": False},
    {"name": "Ecuador", "iso": "ec", "code": "ECU", "default_val": 432, "auto": True, "bcrp_name": "Ecuador"},
    {"name": "Bolivia", "iso": "bo", "code": "BOL", "default_val": 422, "auto": False},
    {"name": "Venezuela", "iso": "ve", "code": "VEN", "default_val": 6662, "auto": True, "bcrp_name": "Venezuela"},
]

def obtener_datos_bcrp() -> dict[str, tuple[int, int]]:
    """
    Obtiene los datos diarios del BCRP para los países automáticos.
    Retorna un diccionario { 'País': (valor_actual, delta) }
    """
    url = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04709XD-PD04710XD-PD04711XD-PD04712XD-PD04713XD-PD04714XD-PD04715XD-PD38581XD-PD04708XD/json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        series = data.get("config", {}).get("series", [])
        periods = data.get("periods", [])
        if len(periods) < 2:
            return {}

        last_p = periods[-1]["values"]
        prev_p = periods[-2]["values"]

        resultados = {}
        for idx, serie in enumerate(series):
            s_name = serie.get("name", "")
            for p in PAISES_CATALOGO:
                if p.get("auto") and p.get("bcrp_name") and p["bcrp_name"] in s_name:
                    try:
                        val_now = int(last_p[idx])
                        val_prev = int(prev_p[idx])
                        delta = val_now - val_prev
                        resultados[p["name"]] = (val_now, delta)
                    except (ValueError, IndexError):
                        pass
        return resultados
    except Exception as e:
        print(f"Error consultando API del BCRP: {e}")
        return {}

def obtener_mapa_actual_paises() -> dict[str, dict]:
    """Lee el ranking actual de Firestore o inicializa con los valores del catálogo."""
    mapa = {}
    # 1. Cargar catálogo base como fallback
    for p in PAISES_CATALOGO:
        mapa[p["name"]] = {
            "name": p["name"],
            "iso": p["iso"],
            "code": p["code"],
            "value": p["default_val"],
            "delta": 0,
            "isLocal": False
        }

    # 2. Cargar datos guardados previamente en Firestore si existen
    doc_fs = leer_ranking_america()
    if doc_fs and "paises" in doc_fs:
        for p in doc_fs["paises"]:
            name = p.get("name")
            if name in mapa:
                mapa[name]["value"] = p.get("value", mapa[name]["value"])
                mapa[name]["delta"] = p.get("delta", 0)

    return mapa

# -------------------------------------------------------------
# Funciones auxiliares de Telegram para interactividad
# -------------------------------------------------------------

def enviar_mensaje_telegram(texto: str, parse_mode: str = "Markdown") -> int | None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": parse_mode
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if res.get("ok"):
            return res["result"]["message_id"]
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")
    return None

def enviar_pregunta_botones(texto: str, botones: list[tuple[str, str]]) -> int | None:
    """Envía un mensaje con botones Inline. Cada botón es (texto, callback_data)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    inline_keyboard = [[{"text": b[0], "callback_data": b[1]} for b in botones]]
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": inline_keyboard}
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if res.get("ok"):
            return res["result"]["message_id"]
    except Exception as e:
        print(f"Error enviando pregunta con botones a Telegram: {e}")
    return None

def editar_mensaje_texto(message_id: int, nuevo_texto: str):
    """Edita el texto de un mensaje y elimina los botones."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": nuevo_texto,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": []}
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error editando mensaje en Telegram: {e}")

def obtener_offset_actual() -> int | None:
    """Obtiene el offset más reciente de Telegram para ignorar mensajes pasados."""
    if not TELEGRAM_BOT_TOKEN:
        return None
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params={"limit": 100}, timeout=10)
        res = r.json()
        if res.get("ok") and res.get("result"):
            return res["result"][-1]["update_id"] + 1
    except Exception as e:
        print(f"Error obteniendo offset de Telegram: {e}")
    return None

def esperar_respuesta_callback(message_id: int, offset_inicial: int | None, timeout_segundos: int = 3600) -> tuple[str | None, int | None]:
    """Espera que el usuario presione un botón inline de un mensaje específico."""
    start = time.time()
    offset = offset_inicial

    while (time.time() - start) < timeout_segundos:
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
                            query_id = callback.get("id")
                            data = callback.get("data")
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                                          json={"callback_query_id": query_id}, timeout=10)
                            return data, offset
        except Exception as e:
            print(f"Error en polling de callback Telegram: {e}")
        time.sleep(2)

    return None, offset

def esperar_mensaje_texto_usuario(offset_inicial: int | None, timeout_segundos: int = 3600) -> tuple[str | None, int | None]:
    """Espera que el usuario envíe un mensaje de texto plano en el chat configurado."""
    start = time.time()
    offset = offset_inicial

    while (time.time() - start) < timeout_segundos:
        try:
            params = {"timeout": 10, "limit": 10}
            if offset is not None:
                params["offset"] = offset

            r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params=params, timeout=15)
            res = r.json()
            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    msg = update.get("message")
                    if msg:
                        sender_chat = str(msg.get("chat", {}).get("id"))
                        if sender_chat == str(TELEGRAM_CHAT_ID):
                            text = msg.get("text", "").strip()
                            if text:
                                return text, offset
        except Exception as e:
            print(f"Error en polling de texto Telegram: {e}")
        time.sleep(2)

    return None, offset

# -------------------------------------------------------------
# Flujo Principal de Actualización Interactiva
# -------------------------------------------------------------

def ejecutar_flujo_ranking_telegram():
    """
    Ejecuta el cuestionario interactivo para actualizar el ranking de América.
    Se ejecuta típicamente los domingos a las 14:00 hs.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram no configurado. No se puede ejecutar el flujo interactivo de ranking.")
        return

    print("Iniciando flujo interactivo de actualización de ranking por Telegram...")
    offset = obtener_offset_actual()

    # 1. Preguntar si tiene los datos
    pregunta_inicial = (
        "🌎 *Actualización del Ranking de Riesgo País (América)*\n\n"
        "¿Tienes los datos de riesgo país de los países restantes para actualizar la tabla?"
    )
    botones_iniciales = [("✅ Sí", "ranking_si"), ("❌ No", "ranking_no")]
    msg_id = enviar_pregunta_botones(pregunta_inicial, botones_iniciales)

    if not msg_id:
        return

    resp, offset = esperar_respuesta_callback(msg_id, offset, timeout_segundos=1800)

    if resp != "ranking_si":
        editar_mensaje_texto(msg_id, "❌ *Actualización de ranking cancelada*. Se mantienen los datos anteriores.")
        print("El usuario canceló o no respondió la actualización del ranking.")
        return

    editar_mensaje_texto(msg_id, "✅ *Iniciando actualización asistida del ranking*...")

    # Cargar mapa actual de países
    mapa_paises = obtener_mapa_actual_paises()

    # Filtrar únicamente los países manuales/restantes
    paises_restantes = [p for p in PAISES_CATALOGO if not p.get("auto")]

    for p_info in paises_restantes:
        p_name = p_info["name"]
        val_actual = mapa_paises[p_name]["value"]

        # Preguntar si el valor ha cambiado
        txt_pais = f"El último valor de *{p_name}* fue *{val_actual}*.\n¿Ha cambiado?"
        btn_pais = [("✅ Sí", f"chg_si_{p_name}"), ("❌ No", f"chg_no_{p_name}")]
        m_id = enviar_pregunta_botones(txt_pais, btn_pais)

        if not m_id:
            continue

        resp_cambio, offset = esperar_respuesta_callback(m_id, offset, timeout_segundos=1800)

        if resp_cambio and resp_cambio.startswith("chg_si"):
            editar_mensaje_texto(m_id, f"📝 Por favor, escribe el nuevo valor de *{p_name}* (número entero):")

            # Esperar respuesta con el número
            nuevo_valor_int = None
            while nuevo_valor_int is None:
                txt_input, offset = esperar_mensaje_texto_usuario(offset, timeout_segundos=1800)
                if txt_input is None:
                    break
                try:
                    nuevo_valor_int = int(txt_input.replace(".", "").replace(",", "").strip())
                except ValueError:
                    enviar_mensaje_telegram(f"⚠️ Formato inválido. Por favor escribe sólo el número para *{p_name}* (ej: 65):")

            if nuevo_valor_int is not None:
                delta = nuevo_valor_int - val_actual
                mapa_paises[p_name]["value"] = nuevo_valor_int
                mapa_paises[p_name]["delta"] = delta
                delta_str = f"+{delta}" if delta > 0 else str(delta)
                enviar_mensaje_telegram(f"✅ *{p_name}* actualizado: *{nuevo_valor_int}* (Variación: {delta_str})")
        else:
            editar_mensaje_texto(m_id, f"➡️ *{p_name}* mantenido en *{val_actual}* (sin cambios).")
            # Dejamos delta en 0 si no cambió esta semana
            mapa_paises[p_name]["delta"] = 0

        time.sleep(1)

    # 2. Sincronizar países automáticos desde la API del BCRP
    enviar_mensaje_telegram("🔄 Sincronizando datos automáticos del BCRP (Chile, Perú, Brasil, México, Colombia, Ecuador, Venezuela)...")
    datos_bcrp = obtener_datos_bcrp()
    for p_name, (val, delta) in datos_bcrp.items():
        if p_name in mapa_paises:
            mapa_paises[p_name]["value"] = val
            mapa_paises[p_name]["delta"] = delta

    # 3. Incorporar Argentina en tiempo real desde Firestore
    arg_val = leer_ultimo_valor_guardado() or 480
    arg_prev = leer_valor_dia_anterior() or arg_val
    arg_delta = arg_val - arg_prev
    mapa_paises["Argentina"] = {
        "name": "Argentina",
        "iso": "ar",
        "code": "ARG",
        "value": arg_val,
        "delta": arg_delta,
        "isLocal": True
    }

    # 4. Guardar lista completa ordenada en Firestore
    lista_final = list(mapa_paises.values())
    lista_final.sort(key=lambda x: x["value"])

    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_act = datetime.now(tz).strftime('%d/%m/%Y %H:%M')
    guardar_ranking_america(lista_final, fecha_act)

    # 5. Notificar resumen final por Telegram
    resumen_lineas = [f"🏆 *Ranking de Riesgo País (América) Actualizado*\n_Fecha: {fecha_act} hs_\n"]
    for idx, c in enumerate(lista_final, 1):
        d_str = f"+{c['delta']}" if c['delta'] > 0 else str(c['delta'])
        resumen_lineas.append(f"{idx}º {c['name']}: *{c['value']}* ({d_str})")

    resumen_texto = "\n".join(resumen_lineas)
    enviar_mensaje_telegram(resumen_texto)
    print("Flujo interactivo de ranking finalizado con éxito.")

def sincronizar_ranking_automatico():
    """
    Sincroniza los países automáticos del BCRP y Argentina sin hacer preguntas manuales.
    Útil para ejecuciones diarias nocturnas.
    """
    mapa_paises = obtener_mapa_actual_paises()
    datos_bcrp = obtener_datos_bcrp()

    for p_name, (val, delta) in datos_bcrp.items():
        if p_name in mapa_paises:
            mapa_paises[p_name]["value"] = val
            mapa_paises[p_name]["delta"] = delta

    arg_val = leer_ultimo_valor_guardado() or 480
    arg_prev = leer_valor_dia_anterior() or arg_val
    arg_delta = arg_val - arg_prev
    mapa_paises["Argentina"] = {
        "name": "Argentina",
        "iso": "ar",
        "code": "ARG",
        "value": arg_val,
        "delta": arg_delta,
        "isLocal": True
    }

    lista_final = list(mapa_paises.values())
    lista_final.sort(key=lambda x: x["value"])

    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_act = datetime.now(tz).strftime('%d/%m/%Y %H:%M')
    guardar_ranking_america(lista_final, fecha_act)
