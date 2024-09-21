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

# Función para obtener el último tweet del usuario
def obtener_ultimo_tweet():
    user_id = client.get_me().data.id  # Obtener el ID del usuario actual
    tweets = client.get_users_tweets(user_id, max_results=1)
    
    if tweets.data:
        ultimo_tweet = tweets.data[0].text
        # Intentar extraer el valor del riesgo país del último tweet
        try:
            ultimo_valor = int(ultimo_tweet.split("ahora es")[1].split("puntos")[0].strip())
            return ultimo_valor
        except (IndexError, ValueError):
            return None
    return None

def obtener_riesgo_pais():
    """Obtiene el valor del riesgo país de la API de RapidAPI"""
    response = requests.get(url_riesgo_pais, headers=headers)
    if response.status_code == 200:
        datos = response.json()
        return int(datos['ultimo'])  # Asegúrate de que 'ultimo' sea la clave correcta en la API
    return None

def postear_tweet(nuevo_valor, ultimo_valor):
    """Postea un tweet indicando si el riesgo país subió o bajó"""
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

while True:
    nuevo_valor = obtener_riesgo_pais()
    
    if nuevo_valor is not None:
        ultimo_valor = obtener_ultimo_tweet()
        if ultimo_valor is None or abs(nuevo_valor - ultimo_valor) >= 10:
            postear_tweet(nuevo_valor, ultimo_valor)
        else:
            print(f"El riesgo país cambió, pero no es significativo (menos de 10 puntos). Valor actual: {nuevo_valor}")
        
    # Esperar 5 minutos antes de la próxima verificación
    time.sleep(300)  # 5 minutos = 300 segundos
