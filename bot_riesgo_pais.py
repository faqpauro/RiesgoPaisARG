import tweepy
import requests
import time
from datetime import datetime
import pytz
import os

# Credenciales OAuth 2.0
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

# Archivos donde se almacenan los valores del riesgo país
ARCHIVO_RIESGO_PAIS = "riesgo_pais.txt"
ARCHIVO_RIESGO_PAIS_ANTERIOR = "riesgo_pais_dia_anterior.txt"

def leer_ultimo_valor_guardado():
    """Leer el último valor del riesgo país guardado en un archivo."""
    if os.path.exists(ARCHIVO_RIESGO_PAIS):
        with open(ARCHIVO_RIESGO_PAIS, "r") as file:
            try:
                return int(file.read().strip())  # Leer y convertir el valor a entero
            except ValueError:
                return None
    return None

def leer_valor_dia_anterior():
    """Leer el valor del riesgo país guardado para el día anterior."""
    if os.path.exists(ARCHIVO_RIESGO_PAIS_ANTERIOR):
        with open(ARCHIVO_RIESGO_PAIS_ANTERIOR, "r") as file:
            try:
                return int(file.read().strip())  # Leer y convertir el valor a entero
            except ValueError:
                return None
    return None

def guardar_valor_riesgo_pais(valor):
    """Guardar el valor actual del riesgo país en un archivo."""
    with open(ARCHIVO_RIESGO_PAIS, "w") as file:
        file.write(str(valor))  # Escribir el valor como cadena

def actualizar_valor_dia_anterior():
    """Actualizar el valor del día anterior al final del día."""
    valor_actual = leer_ultimo_valor_guardado()
    if valor_actual is not None:
        guardar_valor_dia_anterior(valor_actual)

def guardar_valor_dia_anterior(valor):
    """Guardar el valor del riesgo país para el día anterior."""
    with open(ARCHIVO_RIESGO_PAIS_ANTERIOR, "w") as file:
        file.write(str(valor))  # Escribir el valor como cadena

def obtener_riesgo_pais():
    """Obtiene el valor del riesgo país de la API de RapidAPI."""
    response = requests.get(url_riesgo_pais, headers=headers)
    if response.status_code == 200:
        datos = response.json()
        return int(datos['ultimo'])  # Asegúrate de que 'ultimo' sea la clave correcta en la API
    return None

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

def postear_tweet(nuevo_valor, ultimo_valor):
    """Postea un tweet indicando si el riesgo país subió o bajó."""
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_hora = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    
    if ultimo_valor is not None:
        diferencia = nuevo_valor - ultimo_valor
        # Calcular porcentaje respecto al valor del día anterior
        valor_dia_anterior = leer_valor_dia_anterior()
        porcentaje_cambio_diario = calcular_porcentaje_cambio_diario(nuevo_valor, valor_dia_anterior)
        # Determinar si usar "punto" o "puntos"
        puntos_texto = "punto" if abs(diferencia) == 1 else "puntos"
        if diferencia > 0:
            movimiento = f"😭 El riesgo país subió {diferencia} {puntos_texto} ⬆️"
        else:
            movimiento = f"💪 El riesgo país bajó {abs(diferencia)} {puntos_texto} ⬇️"
    else:
        movimiento = "ℹ️ No tiene un valor previo registrado"
        porcentaje_cambio_diario = 0  # Para evitar errores si no hay valor previo
    
    tweet = (
        f"{movimiento}\n"
        f"⚠️ Ahora es de {nuevo_valor} ({porcentaje_cambio_diario:.2f}%)\n"
        f"🇦🇷 #RiesgoPaís #Argentina\n"
        f"🕒 {fecha_hora}"
    )
    client.create_tweet(text=tweet)
    print(f"Tweet enviado: {tweet}")

    # Guardar el nuevo valor del riesgo país después de postear el tweet
    guardar_valor_riesgo_pais(nuevo_valor)

def postear_resumen_diario():
    """Postea un tweet con el resumen diario del cambio del riesgo país."""
    valor_actual = leer_ultimo_valor_guardado()
    valor_dia_anterior = leer_valor_dia_anterior()
    if valor_actual is not None and valor_dia_anterior is not None:
        diferencia = valor_actual - valor_dia_anterior
        puntos_texto = "punto" if abs(diferencia) == 1 else "puntos"
        porcentaje_cambio_diario = calcular_porcentaje_cambio_diario(valor_actual, valor_dia_anterior)
        if diferencia > 0:
            movimiento = f"😭 El riesgo país subió {diferencia} {puntos_texto} hoy. ⬆️"
        elif diferencia < 0:
            movimiento = f"💪 El riesgo país bajó {abs(diferencia)} {puntos_texto} hoy. ⬇️"
        else:
            movimiento = "ℹ️ El riesgo país no cambió hoy."
        
        fecha_actual = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime('%d/%m')
        tweet = (
            f"🔔 RESUMEN DEL DÍA {fecha_actual} 🔔\n"
            f"\n"
            f"{movimiento}\n"
            f"📊 Variación porcentual del día: {porcentaje_cambio_diario:.2f}%\n"
            f"🇦🇷 #RiesgoPaís #Argentina"
        )
        client.create_tweet(text=tweet)
        print(f"Tweet resumen diario enviado: {tweet}")

# Bucle principal
actualizado_hoy = False
resumen_diario_posteado = False

# Bucle principal
while True:
    nuevo_valor = obtener_riesgo_pais()
    
    if nuevo_valor is not None:
        ultimo_valor = leer_ultimo_valor_guardado()
        if ultimo_valor is None or abs(nuevo_valor - ultimo_valor) != 0:
            postear_tweet(nuevo_valor, ultimo_valor)
        else:
            print(f"El riesgo país no cambió. Valor actual: {nuevo_valor}")
        
    # Verificar si la hora está entre 23:50 y 23:55 para actualizar el valor del día anterior
    hora_actual = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).time()
    if hora_actual.hour == 23 and 50 <= hora_actual.minute <= 55 and not actualizado_hoy:
        actualizar_valor_dia_anterior()
        actualizado_hoy = True
        resumen_diario_posteado = False  # Permitir que se postee el resumen al día siguiente
        print("Valor del día anterior actualizado.")

    # Postear el resumen diario a las 22:00
    if hora_actual.hour == 22 and hora_actual.weekday() < 5 and not resumen_diario_posteado:
        postear_resumen_diario()
        resumen_diario_posteado = True
    
    # Resetear el indicador al inicio de un nuevo día
    if hora_actual.hour == 0:
        actualizado_hoy = False
        resumen_diario_posteado = False
        
    # Esperar 5 minutos antes de la próxima verificación
    time.sleep(300)  # 5 minutos = 300 segundos
