import tweepy
import requests
import time
from datetime import datetime
import os
import pytz

BEARER_TOKEN = os.environ.get('BEARER_TOKEN')
CONSUMER_KEY = os.environ.get('CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('ACCESS_TOKEN_SECRET')


# Inicializa el cliente de Tweepy con el Bearer Token
client = tweepy.Client(BEARER_TOKEN, CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

# URL y cabeceras de la API de RapidAPI para riesgo país
url_riesgo_pais = "https://riesgo-pais.p.rapidapi.com/api/riesgopais"
headers = {
    "x-rapidapi-key": "a2df4bf8demsh97afe8342a3d223p118bd5jsn7414c6a2d7b7",
    "x-rapidapi-host": "riesgo-pais.p.rapidapi.com"
}

# Variables para almacenar el último valor del riesgo país y el último tweet publicado
ultimo_valor = None
ultimo_tweet_valor = None

def obtener_riesgo_pais():
    """Obtiene el valor del riesgo país de la API de RapidAPI"""
    response = requests.get(url_riesgo_pais, headers=headers)
    if response.status_code == 200:
        datos = response.json()
        return int(datos['ultimo'])  # Asegúrate de que 'ultimo' sea la clave correcta en la API
    return None

def postear_tweet(nuevo_valor):
    """Postea un tweet con el nuevo valor del riesgo país usando la API v2, incluyendo la fecha y hora"""
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_hora = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    tweet = f"El riesgo país de Argentina ha cambiado: {nuevo_valor} puntos. #RiesgoPaís #Argentina\nFecha y hora: {fecha_hora}"
    client.create_tweet(text=tweet)
    print(f"Tweet enviado: {tweet}")

while True:
    nuevo_valor = obtener_riesgo_pais()
    
    if nuevo_valor is not None:
        # Publicar solo si el riesgo país ha cambiado más de 10 puntos desde el último tweet
        if ultimo_tweet_valor is None or abs(nuevo_valor - ultimo_tweet_valor) >= 10:
            postear_tweet(nuevo_valor)
            ultimo_tweet_valor = nuevo_valor
        else:
            print(f"El riesgo país cambió, pero no es significativo (menos de 10 puntos). Valor actual: {nuevo_valor}")
        
        # Actualizar el último valor obtenido
        ultimo_valor = nuevo_valor

    # Esperar 5 minutos antes de la próxima verificación
    time.sleep(60)  # 5 minutos = 300 segundos