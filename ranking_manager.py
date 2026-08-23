from __future__ import annotations
import time
import json
import io
import zipfile
import unicodedata
import requests
import pytz
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database import (
    leer_ranking_america,
    guardar_ranking_america,
    leer_ultimo_valor_guardado,
    leer_valor_dia_anterior
)

# Catálogo base de países de América y sus posibles nombres en el Excel del BCRD
PAISES_CATALOGO = [
    {"name": "Uruguay",              "iso": "uy", "code": "URU", "default_val": 68,   "excel_names": ["uruguay"]},
    {"name": "Chile",                "iso": "cl", "code": "CHL", "default_val": 90,   "excel_names": ["chile"]},
    {"name": "Paraguay",             "iso": "py", "code": "PRY", "default_val": 109,  "excel_names": ["paraguay"]},
    {"name": "Perú",                 "iso": "pe", "code": "PER", "default_val": 111,  "excel_names": ["peru"]},
    {"name": "Guatemala",            "iso": "gt", "code": "GTM", "default_val": 118,  "excel_names": ["guatemala"]},
    {"name": "Panamá",               "iso": "pa", "code": "PAN", "default_val": 118,  "excel_names": ["panama"]},
    {"name": "Costa Rica",           "iso": "cr", "code": "CRI", "default_val": 131,  "excel_names": ["costa rica"]},
    {"name": "República Dominicana", "iso": "do", "code": "DOM", "default_val": 157,  "excel_names": ["rep dom", "dominicana"]},
    {"name": "Honduras",             "iso": "hn", "code": "HND", "default_val": 158,  "excel_names": ["honduras"]},
    {"name": "Brasil",               "iso": "br", "code": "BRA", "default_val": 181,  "excel_names": ["brasil", "brazil"]},
    {"name": "Colombia",             "iso": "co", "code": "COL", "default_val": 188,  "excel_names": ["colombia"]},
    {"name": "México",               "iso": "mx", "code": "MEX", "default_val": 200,  "excel_names": ["mexico"]},
    {"name": "El Salvador",          "iso": "sv", "code": "SLV", "default_val": 275,  "excel_names": ["el salvador"]},
    {"name": "Bolivia",              "iso": "bo", "code": "BOL", "default_val": 422,  "excel_names": ["bolivia"]},
    {"name": "Ecuador",              "iso": "ec", "code": "ECU", "default_val": 431,  "excel_names": ["ecuador"]},
    {"name": "Venezuela",            "iso": "ve", "code": "VEN", "default_val": 6770, "excel_names": ["venezuela"]},
]

EXCEL_EMBI_URL = "https://bcrdgdcprod.blob.core.windows.net/documents/entorno-internacional/documents/Serie_Historica_Spread_del_EMBI.xlsx"

def _normalizar_texto(texto: str | None) -> str:
    """Normaliza texto removiendo acentos y pasando a minúsculas."""
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    ).lower().strip()

def obtener_datos_embi_excel() -> tuple[dict[str, tuple[int, int]], str | None]:
    """
    Descarga y parsea el Excel de serie histórica del EMBI directamente en memoria.
    Retorna un diccionario { 'País': (valor_actual_bps, delta_bps) } y la fecha del reporte.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        r = requests.get(EXCEL_EMBI_URL, headers=headers, timeout=25)
        r.raise_for_status()

        z = zipfile.ZipFile(io.BytesIO(r.content))
        ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        # 1. Leer tabla de cadenas compartidas (sharedStrings.xml)
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree_ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in tree_ss.findall("ns:si", ns):
                texts = [node.text for node in si.iter() if node.tag.endswith("}t") and node.text]
                shared_strings.append("".join(texts))

        # 2. Leer la primera hoja (sheet1.xml)
        tree_sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        xml_rows = tree_sheet.findall(".//ns:row", ns)

        def _parse_row(row_elem) -> tuple[int, dict[str, str | None]]:
            cells = {}
            for c in row_elem.findall("ns:c", ns):
                ref = c.get("r", "")
                col = "".join([ch for ch in ref if ch.isalpha()])
                t = c.get("t")
                v = c.find("ns:v", ns)
                val = v.text if v is not None else None
                if t == "s" and val is not None:
                    try:
                        val = shared_strings[int(val)]
                    except (IndexError, ValueError):
                        pass
                cells[col] = val
            r_num = int(row_elem.get("r", 0))
            return r_num, cells

        # 3. Extraer encabezados (Fila 2)
        excel_headers = {}
        for r_elem in xml_rows:
            r_num, cells = _parse_row(r_elem)
            if r_num == 2:
                excel_headers = cells
                break

        # Mapear columnas a los países del catálogo
        col_to_country = {}
        for col, h_name in excel_headers.items():
            if not h_name:
                continue
            h_norm = _normalizar_texto(h_name)
            for p in PAISES_CATALOGO:
                if any(_normalizar_texto(alias) in h_norm for alias in p["excel_names"]):
                    col_to_country[col] = p["name"]
                    break

        # 4. Extraer filas con datos válidos (Fecha en Columna A)
        valid_rows = []
        for r_elem in xml_rows:
            r_num, cells = _parse_row(r_elem)
            if r_num > 2 and "A" in cells and cells["A"]:
                try:
                    serial = float(cells["A"])
                    dt = datetime(1899, 12, 30) + timedelta(days=serial)
                    valid_rows.append((dt, cells))
                except ValueError:
                    pass

        if len(valid_rows) < 2:
            msg_err = "⚠️ Menos de 2 filas con datos válidos en el Excel del EMBI."
            print(msg_err)
            enviar_mensaje_telegram(f"⚠️ *Alerta Bot:* {msg_err} Se mantienen los datos de respaldo.")
            return {}, None

        last_dt, last_cells = valid_rows[-1]
        prev_dt, prev_cells = valid_rows[-2]
        fecha_reporte = last_dt.strftime("%d/%m/%Y")

        resultados = {}
        for col, p_name in col_to_country.items():
            raw_last = last_cells.get(col)
            raw_prev = prev_cells.get(col)

            if raw_last is None or raw_last == "N/A":
                continue

            try:
                val_now = int(round(float(raw_last) * 100))
                if raw_prev and raw_prev != "N/A":
                    val_prev = int(round(float(raw_prev) * 100))
                    delta = val_now - val_prev
                else:
                    delta = 0
                resultados[p_name] = (val_now, delta)
            except (ValueError, TypeError):
                pass

        print(f"✅ Excel EMBI parseado con éxito ({len(resultados)} países, fecha de corte: {fecha_reporte}).")
        return resultados, fecha_reporte

    except Exception as e:
        msg_err = f"❌ Error descargando o parseando Excel del EMBI: {e}"
        print(msg_err)
        enviar_mensaje_telegram(f"⚠️ *Alerta Bot:* Error al procesar el Excel del EMBI ({e}). Se mantienen los datos anteriores.")
        return {}, None


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
# Funciones auxiliares de Telegram
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

def esperar_respuesta_callback(message_id: int, offset_inicial: int | None, timeout_segundos: int = 1800) -> tuple[str | None, int | None]:
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

# -------------------------------------------------------------
# Sincronización y Flujo de Actualización
# -------------------------------------------------------------

def sincronizar_ranking_automatico() -> list[dict]:
    """
    Sincroniza todos los países de América desde el Excel del EMBI
    e incorpora Argentina en tiempo real desde Firestore.
    Guarda el resultado consolidado en Firestore.
    """
    mapa_paises = obtener_mapa_actual_paises()
    datos_embi, fecha_corte = obtener_datos_embi_excel()

    # Actualizar países con los datos del Excel
    for p_name, (val, delta) in datos_embi.items():
        if p_name in mapa_paises:
            mapa_paises[p_name]["value"] = val
            mapa_paises[p_name]["delta"] = delta

    # Incorporar Argentina en tiempo real desde Firestore / local
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

    return lista_final

def ejecutar_flujo_ranking_telegram():
    """
    Sincroniza automáticamente el ranking desde el Excel, actualiza Firestore,
    envía el resumen consolidado a Telegram y pregunta sólo si se desea publicar en X.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram no configurado. No se puede ejecutar el flujo interactivo de ranking.")
        return

    print("Iniciando flujo de actualización de ranking por Telegram...")
    offset = obtener_offset_actual()

    # 1. Sincronizar automáticamente desde el Excel del EMBI + Argentina
    enviar_mensaje_telegram("🔄 *Sincronizando ranking de América desde el Excel oficial del EMBI...*")
    lista_final = sincronizar_ranking_automatico()

    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_act = datetime.now(tz).strftime('%d/%m/%Y %H:%M')

    # 2. Enviar tabla resumen a Telegram
    resumen_lineas = [f"🏆 *Ranking de Riesgo País (América) Actualizado*\n_Fecha: {fecha_act} hs_\n"]
    for idx, c in enumerate(lista_final, 1):
        d_str = f"+{c['delta']}" if c['delta'] > 0 else str(c['delta'])
        resumen_lineas.append(f"{idx}º {c['name']}: *{c['value']}* ({d_str})")

    resumen_texto = "\n".join(resumen_lineas)
    enviar_mensaje_telegram(resumen_texto)

    # 3. Preguntar únicamente si se desea publicar la tabla en X (Twitter)
    txt_x = "📢 *¿Deseas publicar la tabla del Ranking de América en X (Twitter)?*"
    btn_x = [("✅ Sí, publicar en X", "pub_x_si"), ("❌ No, no publicar", "pub_x_no")]
    msg_x_id = enviar_pregunta_botones(txt_x, btn_x)

    if msg_x_id:
        resp_x, offset = esperar_respuesta_callback(msg_x_id, offset, timeout_segundos=1800)
        if resp_x == "pub_x_si":
            editar_mensaje_texto(msg_x_id, "⏳ *Publicando tabla en X (Twitter)...*")
            try:
                from publisher import postear_ranking_america_tweet
                postear_ranking_america_tweet(lista_final)
                editar_mensaje_texto(msg_x_id, "✅ *¡Tabla de América publicada con éxito en X (Twitter)!*")
            except Exception as e:
                print(f"Error publicando tabla en X: {e}")
                editar_mensaje_texto(msg_x_id, f"❌ *Error al publicar en X:* {e}")
        else:
            editar_mensaje_texto(msg_x_id, "❌ *No se publicará la tabla en X.*")

    print("Flujo de ranking finalizado con éxito.")

def verificar_comando_telegram() -> bool:
    """
    Verifica si el usuario envió /ranking o /actualizar para disparar el flujo por Telegram.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params={"limit": 10}, timeout=5)
        res = r.json()
        if res.get("ok") and res.get("result"):
            for update in res["result"]:
                msg = update.get("message")
                if msg:
                    sender = str(msg.get("chat", {}).get("id"))
                    text = msg.get("text", "").strip().lower()
                    if sender == str(TELEGRAM_CHAT_ID) and text in ["/ranking", "/actualizar", "ranking", "actualizar"]:
                        # Avanzar offset para no volver a capturar el mismo comando
                        offset = update["update_id"] + 1
                        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params={"offset": offset}, timeout=5)
                        return True
    except Exception as e:
        print(f"Error verificando comandos de Telegram: {e}")
    return False
