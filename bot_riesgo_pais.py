import tweepy
import requests
import time
from datetime import datetime
import pytz
import os

# Credenciales OAuth 2.0
BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAMH5vwEAAAAAz0el8LALMoCz7myi%2BCt3l3iN4Dw%3DsGRWjv5zoJvFxwpEDKqcg411UGWWGJF5XV1SspRTvq61WzycQG'
CONSUMER_KEY = 'RaMNwo5XQIvLsfHzOUr6Kz8Vl'
CONSUMER_SECRET = '68DkzYuTa1aldWA2BhIAJy4UnZVhfw8EIGqDGOj6mJzFwVbCE7'
ACCESS_TOKEN = '1576646313390768129-Qe0wSb6QtNJakhso3qDn42g7UawTfI'
ACCESS_TOKEN_SECRET = 'fE3Kvi99NdzAeHitKmNy281HjdXten8i2KT0tqrO7OUQ4'

# Inicializa el cliente de Tweepy con el Bearer Token
client = tweepy.Client(BEARER_TOKEN, CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

# URL y cabeceras de la API de RapidAPI para riesgo país
url_riesgo_pais = "https://riesgo-pais.p.rapidapi.com/api/riesgopais"
headers = {
    "x-rapidapi-key": "a2df4bf8demsh97afe8342a3d223p118bd5jsn7414c6a2d7b7",
    "x-rapidapi-host": "riesgo-pais.p.rapidapi.com"
}

# Archivo donde se almacenará el valor del riesgo país
ARCHIVO_RIESGO_PAIS = "riesgo_pais.txt"

def leer_ultimo_valor_guardado():
    """Leer el último valor del riesgo país guardado en un archivo."""
    if os.path.exists(ARCHIVO_RIESGO_PAIS):
        with open(ARCHIVO_RIESGO_PAIS, "r") as file:
            try:
                return int(file.read().strip())  # Leer y convertir el valor a entero
            except ValueError:
                return None
    return None

def guardar_valor_riesgo_pais(valor):
    """Guardar el valor actual del riesgo país en un archivo."""
    with open(ARCHIVO_RIESGO_PAIS, "w") as file:
        file.write(str(valor))  # Escribir el valor como cadena

def obtener_riesgo_pais():
    """Obtiene el valor del riesgo país de la API de RapidAPI."""
    response = requests.get(url_riesgo_pais, headers=headers)
    if response.status_code == 200:
        datos = response.json()
        return int(datos['ultimo'])  # Asegúrate de que 'ultimo' sea la clave correcta en la API
    return None

def postear_tweet(nuevo_valor, ultimo_valor):
    """Postea un tweet indicando si el riesgo país subió o bajó."""
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_hora = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    
    if ultimo_valor is not None:
        diferencia = nuevo_valor - ultimo_valor
        if diferencia > 0:
            movimiento = f"subió {diferencia}"
        else:
            movimiento = f"bajó {abs(diferencia)}"
    else:
        movimiento = "no tiene un valor previo registrado"
    
    tweet = f"El riesgo país de Argentina {movimiento} puntos y ahora es {nuevo_valor} puntos. #RiesgoPaís #Argentina\nFecha y hora: {fecha_hora}"
    client.create_tweet(text=tweet)
    print(f"Tweet enviado: {tweet}")

    # Guardar el nuevo valor del riesgo país después de postear el tweet
    guardar_valor_riesgo_pais(nuevo_valor)

# Bucle principal
while True:
    nuevo_valor = obtener_riesgo_pais()
    
    if nuevo_valor is not None:
        ultimo_valor = leer_ultimo_valor_guardado()
        if ultimo_valor is None or abs(nuevo_valor - ultimo_valor) >= 10:
            postear_tweet(nuevo_valor, ultimo_valor)
        else:
            print(f"El riesgo país cambió, pero no es significativo (menos de 10 puntos). Valor actual: {nuevo_valor}")
        
    # Esperar 5 minutos antes de la próxima verificación
    time.sleep(60)  # 5 minutos = 300 segundos
