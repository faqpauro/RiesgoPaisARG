import tweepy
import requests
import time

# Autenticación con la API de Twitter (X)
consumer_key = 'RaMNwo5XQIvLsfHzOUr6Kz8Vl'
consumer_secret = '68DkzYuTa1aldWA2BhIAJy4UnZVhfw8EIGqDGOj6mJzFwVbCE7'
access_token = '1576646313390768129-ygViKmLrqmlvkK6Zipdkt0T6UwoAM9'
access_token_secret = 'dgZfpWRCH9XJH1bbzGH87CYscYL1r6cBaxIoe5ehszBQ2'

auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
api = tweepy.API(auth)

# URL y cabeceras de la API de RapidAPI para riesgo país
url_riesgo_pais = "https://riesgo-pais.p.rapidapi.com/api/riesgopais"
headers = {
    "x-rapidapi-key": "a2df4bf8demsh97afe8342a3d223p118bd5jsn7414c6a2d7b7",
    "x-rapidapi-host": "riesgo-pais.p.rapidapi.com"
}

# Variable para almacenar el último valor del riesgo país y el último tweet publicado
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
    """Postea un tweet con el nuevo valor del riesgo país"""
    tweet = f"El riesgo país de Argentina ha cambiado: {nuevo_valor} puntos. #RiesgoPaís #Argentina"
    api.update_status(tweet)
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
    time.sleep(300)  # 5 minutos = 300 segundos


