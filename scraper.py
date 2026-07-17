from __future__ import annotations
import requests
import time
from utils import notificar_telegram

def obtener_riesgo_pais(max_reintentos: int = 3) -> int | None:
    """Devuelve el valor de riesgo país o None si no se pudo leer."""
    url = "https://mercados.ambito.com/riesgopais/variacion-ultimo"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for intento in range(1, max_reintentos + 1):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            valor_txt = data.get('ultimo', '').strip().replace(".", "")
            if valor_txt:
                return int(valor_txt)
            else:
                raise ValueError("El campo 'ultimo' está vacío o no existe en el JSON.")
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"[{intento}/{max_reintentos}] Error leyendo Ámbito ({type(e).__name__}): {e}; reintento en 10 s…")
            notificar_telegram(f"[{intento}/{max_reintentos}] Error Ámbito: {type(e).__name__}")
            time.sleep(10)
        except Exception as e:
            print(f"[{intento}/{max_reintentos}] Error inesperado: {e}; reintento en 5 s…")
            notificar_telegram(f"Error inesperado: {e}")
            time.sleep(5)

    print("❌ No se pudo obtener Riesgo País tras varios intentos.")
    notificar_telegram("No se pudo obtener Riesgo País tras varios intentos de leer Ámbito.")
    return None
