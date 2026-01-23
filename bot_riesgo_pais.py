import tweepy
import requests
import time
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
import os
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, timedelta
import math
import random
from playwright.sync_api import sync_playwright, TimeoutError

# Definir las credenciales usando las variables de entorno
firebase_cred = {
    "type": os.environ.get('FIREBASE_TYPE'),
    "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
    "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
    "private_key": os.environ.get('FIREBASE_PRIVATE_KEY').replace("\\n", "\n"),
    "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
    "client_id": os.environ.get('FIREBASE_CLIENT_ID'),
    "auth_uri": os.environ.get('FIREBASE_AUTH_URI'),
    "token_uri": os.environ.get('FIREBASE_TOKEN_URI'),
    "auth_provider_x509_cert_url": os.environ.get('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
    "client_x509_cert_url": os.environ.get('FIREBASE_CLIENT_X509_CERT_URL'),
    "universe_domain": os.environ.get('FIREBASE_UNIVERSE_DOMAIN')
}

# Inicializa Firebase con las credenciales del diccionario
cred = credentials.Certificate(firebase_cred)
firebase_admin.initialize_app(cred)

# Inicializa el cliente de Firestore
db = firestore.client()

# Credenciales OAuth 2.0
BEARER_TOKEN = os.environ.get('BEARER_TOKEN')
CONSUMER_KEY = os.environ.get('CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('ACCESS_TOKEN_SECRET')

# Credenciales Bot Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Inicializa el cliente de Tweepy con el Bearer Token
client = tweepy.Client(BEARER_TOKEN, CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# URL y cabeceras de la API de RapidAPI para riesgo país
url_riesgo_pais = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo"

def leer_ultimo_valor_guardado():
    doc_ref = db.collection('riesgo_pais').document('ultimo_valor')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('valor')
    return None

def leer_valor_dia_anterior():
    doc_ref = db.collection('riesgo_pais').document('valor_dia_anterior')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('valor')
    return None

def leer_historico_riesgo_pais():
    historico = []
    docs = db.collection('historico_riesgo_pais').stream()
    for doc in docs:
        data = doc.to_dict()
        fecha = data.get('fecha')
        valor = data.get('valor')
        historico.append((datetime.strptime(fecha, '%d-%m-%Y'), valor))
    return historico

def leer_valor_ultimo_dia_mes_anterior():
    """Lee el valor del último día del mes anterior desde Firebase."""
    doc_ref = db.collection('riesgo_pais').document('ultimo_dia_mes_anterior')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('valor')
    return None

def guardar_valor_ultimo_dia_mes_anterior(valor):
    """Guarda el valor del último día del mes actual en Firebase."""
    doc_ref = db.collection('riesgo_pais').document('ultimo_dia_mes_anterior')
    doc_ref.set({'valor': valor})
    print(f"Valor del último día del mes actual guardado: {valor}")

def guardar_valor_riesgo_pais(valor):
    doc_ref = db.collection('riesgo_pais').document('ultimo_valor')
    doc_ref.set({'valor': valor})

def actualizar_valor_dia_anterior():
    """Actualizar el valor del día anterior al final del día."""
    valor_actual = leer_ultimo_valor_guardado()
    if valor_actual is not None:
        guardar_valor_dia_anterior(valor_actual)

def guardar_valor_dia_anterior(valor):
    doc_ref = db.collection('riesgo_pais').document('valor_dia_anterior')
    doc_ref.set({'valor': valor})

def guardar_historico_riesgo_pais(valor):
    """Guarda el valor del riesgo país para la fecha actual en Firestore."""
    # Obtener la fecha actual en el formato requerido
    fecha_actual = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime('%d-%m-%Y')
    
    # Referencia al documento usando la fecha como ID
    doc_ref = db.collection('historico_riesgo_pais').document(fecha_actual)
    
    # Escritura del valor sin verificar si ya existe (asumimos que se ejecuta solo una vez al día)
    doc_ref.set({'fecha': fecha_actual, 'valor': valor})
    print(f"Valor del riesgo país guardado para la fecha {fecha_actual}: {valor}")

def obtener_riesgo_pais(max_reintentos: int = 3) -> int | None:
    """Devuelve el valor de riesgo país o None si no se pudo leer."""
    for intento in range(1, max_reintentos + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()

                try:
                    page.goto(
                        "https://www.ambito.com/contenidos/RIESGO-PAIS.html",
                        wait_until="domcontentloaded",
                        timeout=60_000
                    )
                    span = page.wait_for_selector(
                        "span.variation-last__value.data-ultimo",
                        timeout=60_000
                    )
                    valor_txt = span.inner_text().strip().replace(".", "")
                    return int(valor_txt)
                finally:
                    # cerrar antes de salir del `with`
                    context.close()
                    browser.close()

        except TimeoutError:
            print(f"[{intento}/{max_reintentos}] Timeout leyendo Ámbito; reintento en 10 s…")
            notificar_telegram(f"[{intento}/{max_reintentos}] Timeout Ámbito")
            time.sleep(10)
        except Exception as e:
            print(f"[{intento}/{max_reintentos}] Error inesperado: {e}; reintento en 5 s…")
            notificar_telegram(f"Error leyendo Ámbito: {e}")
            time.sleep(5)

    print("❌ No se pudo obtener Riesgo País tras varios intentos.")
    notificar_telegram("No se pudo obtener Riesgo País tras varios intentos.")
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

def traducir_fecha(fecha):
    """Traduce el nombre del mes en una fecha."""
    meses = {
        "January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
        "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
        "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
    }
    # Formatear la fecha y traducir el mes
    fecha_str = fecha.strftime("%d de %B")
    for mes_ing, mes_esp in meses.items():
        fecha_str = fecha_str.replace(mes_ing, mes_esp)
    return fecha_str

def generar_grafico_en_memoria(datos):
    """Genera un gráfico visualmente moderno para los últimos 10 años de riesgo país."""
    
    # Lista de presidentes por año (ajusta según los datos reales)
    presidentes = {
        1998: "Carlos Menem",
        1999: "Carlos Menem",
        2000: "Fernando de la Rúa",
        2001: "Fernando de la Rúa",
        2002: "Eduardo Duhalde",
        2003: "Eduardo Duhalde",
        2004: "Néstor Kirchner",
        2005: "Néstor Kirchner",
        2006: "Néstor Kirchner",
        2007: "Néstor Kirchner",
        2008: "Cristina Fernández",
        2009: "Cristina Fernández",
        2010: "Cristina Fernández",
        2011: "Cristina Fernández",
        2012: "Cristina Fernández",
        2013: "Cristina Fernández",
        2014: "Cristina Fernández",
        2015: "Mauricio Macri",
        2016: "Mauricio Macri",
        2017: "Mauricio Macri",
        2018: "Mauricio Macri",
        2019: "Alberto Fernández",
        2020: "Alberto Fernández",
        2021: "Alberto Fernández",
        2022: "Alberto Fernández",
        2023: "Javier Milei",
        2024: "Javier Milei",
        2025: "Javier Milei",
        2026: "Javier Milei",
        2027: "Javier Milei",
    }

    # Ordenar los datos por año
    datos_ordenados = sorted(datos, key=lambda x: x[0])
    años = [d[0].year for d in datos_ordenados]
    valores = [d[1] for d in datos_ordenados]

    # Obtener la fecha actual para mostrarla en el título
    hoy = datetime.now()
    fecha_actual = traducir_fecha(hoy)
    año_actual = hoy.year
    rango_años = f"{min(años)}-{max(años)}"  # Determinar el rango dinámico de años

    # Determinar el valor mínimo y máximo de los datos
    min_valor = min(valores)
    max_valor = max(valores)

    # Agregar un margen para que los puntos no estén pegados al borde
    margen = (max_valor - min_valor) * 0.1  # 10% del rango de datos
    rango_min = max(0, min_valor - margen)  # Asegurar que el rango mínimo no sea negativo
    rango_max = max_valor + margen

    # Ajuste dinámico del paso de los ticks del eje Y
    rango_total = rango_max - rango_min
    if rango_total <= 1000:
        step = 50
    elif rango_total <= 5000:
        step = 250
    else:
        step = 500

    # Crear el gráfico
    plt.figure(figsize=(12, 8))
    ax = plt.gca()

    # Fondo moderno
    ax.set_facecolor('#2b2b2b')  # Fondo oscuro
    plt.gcf().set_facecolor('#2b2b2b')  # Fondo completo

    # Línea de riesgo país
    # Dibujar la línea de riesgo país con colores dinámicos
    # Parte izquierda en verde
    plt.plot(años[:len(años)//2 + 1], valores[:len(años)//2 + 1], marker='o', color='#28a745', linestyle='-', linewidth=3, label="Riesgo País (bajó)")

    # Parte derecha en rojo
    plt.plot(años[len(años)//2:], valores[len(años)//2:], marker='o', color='#dc3545', linestyle='-', linewidth=3, label="Riesgo País (subió)")

    # Dibujar líneas verdes o rojas dependiendo del cambio de valor
    for i in range(1, len(años)):
        color = '#28a745' if valores[i] < valores[i - 1] else '#dc3545'  # Verde si bajó, rojo si subió
        plt.plot(años[i-1:i+1], valores[i-1:i+1], marker='o', color=color, linestyle='-', linewidth=3)

    # Sombreado dinámico debajo de la línea según cambio de valor
    for i in range(1, len(años)):
        color_sombra = '#28a745' if valores[i] < valores[i - 1] else '#dc3545'  # Verde si bajó, rojo si subió
        plt.fill_between(
            años[i-1:i+1],  # Rango del eje X
            valores[i-1:i+1],  # Valores del eje Y
            rango_min,  # Extiende hasta el límite inferior del gráfico
            color=color_sombra, 
            alpha=0.2  # Transparencia para no sobrecargar el diseño
        )

    # Título moderno
    plt.title(f"Riesgo País ({rango_años})\n(Valores del {fecha_actual} de cada año)",
              fontsize=18, fontweight='bold', color='white')

    # Etiquetas del eje Y
    plt.ylabel("Valor Riesgo País", fontsize=14, fontweight='bold', color='white')

    # Establecer los límites del eje Y
    plt.ylim(rango_min, rango_max)

    # Configurar los ticks del eje Y dinámicamente
    tick_inicio = math.floor(rango_min / step) * step
    tick_fin = math.ceil(rango_max / step) * step
    ticks_y = range(int(tick_inicio), int(tick_fin + step), int(step))
    plt.yticks(ticks_y, fontsize=12, color='white')

    # Configurar los ticks del eje X (años en negrita)
    plt.xticks(años, fontsize=12, fontweight='bold', color='white')
    ax.xaxis.label.set_visible(False)  # Ocultar texto del eje X

    # Posición fija para los nombres de presidentes debajo del gráfico
    posicion_presidentes = rango_min - (margen * 1.5)  # Mayor separación

    # Agregar nombres de presidentes debajo de cada año
    for año in años:
        presidente = presidentes.get(año, "N/A")
        nombre, apellido = presidente.split(" ", 1) if " " in presidente else (presidente, "")
        plt.text(año, posicion_presidentes, f"{nombre}\n{apellido}", 
                 fontsize=10, color='white', ha='center', va='top')

    # Rejilla
    plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.5)

    # Agregar etiquetas con los valores en cada punto
    for i, (año, valor) in enumerate(zip(años, valores)):
        if i == 0:  # Primer valor con solo borde, sin fondo
            plt.annotate(
                f"{int(valor)}",
                (años[i], valores[i]),
                textcoords="offset points",
                xytext=(0, 10),
                ha='center',
                fontsize=12,
                color='white',
                bbox=dict(boxstyle="round,pad=0.3", edgecolor='gray', facecolor='none', alpha=1)  # Solo borde
            )
        elif año == años[-1]:  # Último año (valor actual)
            # Recuadro especial para el valor actual con borde amarillo
            color_recuadro = '#28a745' if valores[i] < valores[i - 1] else '#dc3545'  # Verde si bajó, rojo si subió
            plt.annotate(
                f"{int(valor)}",
                (años[i], valores[i]),
                textcoords="offset points",
                xytext=(0, 10),
                ha='center',
                fontsize=14,
                color='white',
                bbox=dict(boxstyle="round,pad=0.3", edgecolor='#FFC300', facecolor=color_recuadro, linewidth=2, alpha=0.6)  # Más transparente
            )
        else:
            # Recuadro para otros valores basado en si subió o bajó
            color_recuadro = '#28a745' if valores[i] < valores[i - 1] else '#dc3545'
            plt.annotate(
                f"{int(valor)}",
                (años[i], valores[i]),
                textcoords="offset points",
                xytext=(0, 10),
                ha='center',
                fontsize=12,
                color='white',
                bbox=dict(boxstyle="round,pad=0.3", edgecolor=color_recuadro, facecolor=color_recuadro, alpha=0.6)  # Más transparente
            )

    # Leyenda moderna
    plt.legend(fontsize=12, loc='upper left', facecolor='#2b2b2b', edgecolor='white', labelcolor='white')

    # Guardar la imagen en un objeto BytesIO
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buffer.seek(0)  # Volver al inicio del buffer
    return buffer
    
def obtener_datos_historicos_para_grafico():
    """Obtiene los datos históricos necesarios para el gráfico."""
    historico = leer_historico_riesgo_pais()  # Datos del historial (fecha y valor)
    hoy = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
    
    datos = []
    for año in range(hoy.year - 10, hoy.year + 1):  # Iterar sobre los últimos 10 años
        fecha_objetivo = datetime(año, hoy.month, hoy.day)  # Usar el año de la iteración
        
        while fecha_objetivo.year == año:  # Asegurarse de no salir del año actual en la iteración
            # Buscar el valor más cercano para la fecha
            valor = next((v for f, v in historico if f.date() == fecha_objetivo.date()), None)
            if valor is not None:
                datos.append((fecha_objetivo, valor))
                break  # Salir del bucle si se encuentra un valor
            
            # Si no hay valor para esta fecha, retroceder un día
            fecha_objetivo -= timedelta(days=1)
        
        # Si no se encontró ningún valor para todo el año, agregar un dato faltante
        if not any(d[0].year == año for d in datos):
            print(f"⚠️ No se encontraron datos para el año {año}")
            datos.append((datetime(año, 1, 1), None))  # Marcar como vacío si no hay datos
    
    return datos

def obtener_datos_historicos_simulados_para_grafico():
    """Simula datos históricos reales del riesgo país desde 2014 hasta 2024."""
    datos_reales = [
        ("16-11-2024", 769),
        ("16-11-2023", 2397),
        ("16-11-2022", 2346),
        ("16-11-2021", 1707),
        ("16-11-2020", 1323),
        ("16-11-2019", 2442),
        ("16-11-2018", 656),
        ("16-11-2017", 373),
        ("16-11-2016", 487),
        ("16-11-2015", 485),
        ("16-11-2014", 664),
    ]

    # Convertir las fechas en objetos datetime y mantener los valores reales
    datos = [(datetime.strptime(fecha, "%d-%m-%Y"), valor) for fecha, valor in datos_reales]
    return datos

def postear_grafico():
    """Genera y postea un gráfico con los datos históricos de riesgo país."""
    datos = obtener_datos_historicos_para_grafico()
    # datos = obtener_datos_historicos_simulados_para_grafico()
    if not datos:
        print("No hay suficientes datos para generar el gráfico.")
        return

    # Generar gráfico en memoria
    imagen_buffer = generar_grafico_en_memoria(datos)

    # Subir la imagen con `api`
    media = api.media_upload(filename="grafico.png", file=imagen_buffer)

    # Obtener la fecha actual y los rangos de años
    hoy = datetime.now()
    fecha_actual = traducir_fecha(hoy)
    años = [dato[0].year for dato in datos]  # Extraer los años de los datos
    rango_años = f"{min(años)}-{max(años)}"  # Determinar el rango dinámicamente
    
    texto = (
        f"📊 #RiesgoPaís: {rango_años}\n"
        f"📅 Fecha: {fecha_actual}\n"
        "🇦🇷 #Argentina #Economía"
    )
    
    client.create_tweet(text=texto, media_ids=[media.media_id])
    print("Tweet con gráfico enviado.")    

def postear_tweet(nuevo_valor, ultimo_valor):
    """Postea un tweet indicando si el riesgo país subió o bajó."""
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_dt = datetime.now(tz)
    fecha_hora = ahora_dt.strftime('%Y-%m-%d %H:%M:%S')

    linea_referencia = ""
    
    if ultimo_valor is not None:
        diferencia = nuevo_valor - ultimo_valor
        # Calcular porcentaje respecto al valor del día anterior
        valor_dia_anterior = leer_valor_dia_anterior()
        porcentaje_cambio_diario = calcular_porcentaje_cambio_diario(nuevo_valor, valor_dia_anterior)
        if valor_dia_anterior is not None:
            diff_anterior = nuevo_valor - valor_dia_anterior
            txt_pts = "punto" if abs(diff_anterior) == 1 else "puntos"
            txt_cuando = "Viernes" if ahora_dt.weekday() == 0 else "Ayer"

            if diff_anterior > 0:
                linea_referencia = f"🔴 vs {txt_cuando}: Subió {diff_anterior} {txt_pts}"
            elif diff_anterior < 0:
                linea_referencia = f"🟢 vs {txt_cuando}: Bajó {abs(diff_anterior)} {txt_pts}"
            else:
                igual_txt = "ayer" if txt_cuando == "Ayer" else "el viernes"
                linea_referencia = f"📆⚖️ Igual que {igual_txt}"
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
        f"{linea_referencia}\n"
        f"🇦🇷 #RiesgoPaís #Argentina\n"
        f"🕒 {fecha_hora}"
    )
    client.create_tweet(text=tweet)
    print(f"Tweet enviado: {tweet}")
    
    # Guardar el nuevo valor del riesgo país después de postear el tweet
    guardar_valor_riesgo_pais(nuevo_valor)
    notificar_telegram(f"Tweet diario publicado: {nuevo_valor}")

def postear_resumen_diario():
    """Postea un tweet con el resumen diario del cambio del riesgo país."""
    valor_actual = leer_ultimo_valor_guardado()
    valor_dia_anterior = leer_valor_dia_anterior()
    historico = leer_historico_riesgo_pais()
    if valor_actual is not None and valor_dia_anterior is not None:
        diferencia = valor_actual - valor_dia_anterior
        puntos_texto = "punto" if abs(diferencia) == 1 else "puntos"
        porcentaje_cambio_diario = calcular_porcentaje_cambio_diario(valor_actual, valor_dia_anterior)
        if diferencia > 0:
            movimiento = f"😭 Subió {diferencia} {puntos_texto} hoy. ⬆️"
        elif diferencia < 0:
            movimiento = f"💪 Bajó {abs(diferencia)} {puntos_texto} hoy. ⬇️"
        else:
            movimiento = "ℹ️ El riesgo país no cambió hoy."
        
        fecha_actual = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime('%d/%m')
        tweet = (
            f"🔔 RESUMEN DEL DÍA {fecha_actual} 🔔\n"
            f"\n"
            f"📉 Riesgo País: {valor_actual}\n"
            f"{movimiento}\n"
            f"📊 Variación porcentual: {porcentaje_cambio_diario:.2f}%\n"
        )

        mejor_fecha, mejor_valor = obtener_mejor_valor_desde_fecha(valor_actual, historico)
        if mejor_fecha:
            mejor_fecha_str = mejor_fecha.strftime('%d/%m/%Y')
            tweet += f"🏆 Mejor desde {mejor_fecha_str} ({mejor_valor:.0f})\n"
        
        tweet += f"🇦🇷 #RiesgoPaís #Argentina"
        client.create_tweet(text=tweet)
        print(f"Tweet resumen diario enviado: {tweet}")
        notificar_telegram("Resumen diario publicado")

def postear_resumen_mensual():
    """Postea un resumen mensual del cambio del riesgo país."""
    hoy = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
    valor_anterior = leer_valor_ultimo_dia_mes_anterior()  # Valor del mes anterior
    valor_actual = leer_ultimo_valor_guardado()  # Valor actual (último día del mes)

    if valor_anterior is None or valor_actual is None:
        print("⚠️ No hay datos suficientes para el resumen mensual.")
        return

    # Calcular variación
    diferencia = valor_actual - valor_anterior
    porcentaje_cambio = calcular_porcentaje_cambio(valor_actual, valor_anterior)

    # Determinar si subió o bajó
    movimiento = f"💪 Bajó {abs(diferencia)} puntos ⬇️" if diferencia < 0 else f"😭 Subió {diferencia} puntos ⬆️"

    # Buscar el mejor valor desde el inicio del mes
    historico = leer_historico_riesgo_pais()
    mejor_fecha, mejor_valor = obtener_mejor_valor_desde_fecha(valor_actual, historico)

    # Traducción del mes al español
    meses_es = {
        "January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
        "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
        "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
    }
    mes_actual = hoy.strftime('%B')  # Nombre del mes en inglés
    mes_actual_es = meses_es.get(mes_actual, mes_actual)  # Traducción al español
    año_actual = hoy.year

    texto = (
        f"🔥🔥 RESUMEN {mes_actual_es.upper()} {año_actual} 🔥🔥\n\n"
        f"📉 Riesgo País: {valor_actual}\n"
        f"{movimiento}\n"
        f"📊 Variación porcentual: {porcentaje_cambio:.2f}%\n"
    )

    if mejor_fecha:
        mejor_fecha_str = mejor_fecha.strftime('%d/%m/%Y')
        texto += f"🏆 Mejor desde {mejor_fecha_str} ({mejor_valor})\n"

    texto += "🇦🇷 #RiesgoPaís #Argentina"

    # Publicar en Twitter
    client.create_tweet(text=texto)
    print(f"Tweet resumen mensual enviado: {texto}")

    # Guardar el valor actual como el último día del mes
    guardar_valor_ultimo_dia_mes_anterior(valor_actual)
    notificar_telegram("Resumen mensual publicado")

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

# Bucle principal
actualizado_hoy = False
resumen_diario_posteado = False
grafico_posteado = False
resumen_mensual_posteado = False

while True:
    try:
        # Obtener la hora y día actual en la zona horaria de Buenos Aires
        ahora = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
        hora_actual = ahora.time()
        dia_actual = ahora.weekday()  # 0 = Lunes, 6 = Domingo
        ultimo_dia_mes = (ahora + timedelta(days=1)).day == 1  # Verificar si es el último día del mes

        # Publicar resumen mensual el último día del mes a las 22:00
        if ultimo_dia_mes and hora_actual.hour == 22 and 10 <= hora_actual.minute <= 15 and not resumen_mensual_posteado:
            postear_resumen_mensual()
            resumen_mensual_posteado = True

        # Resetear indicador al inicio de un nuevo mes
        if ahora.day == 1 and hora_actual.hour == 0:
            resumen_mensual_posteado = False

        # Verificar si está dentro del horario permitido
        if dia_actual < 5 and (hora_actual >= datetime.strptime("08:00", "%H:%M").time() or hora_actual <= datetime.strptime("01:00", "%H:%M").time()):
            nuevo_valor = obtener_riesgo_pais()

            if nuevo_valor is None:
                print("No se obtuvo Riesgo País; reintentamos en 5 minutos.")
                time.sleep(300)
                continue

            if nuevo_valor != 0:
                ultimo_valor = leer_ultimo_valor_guardado()
                if ultimo_valor is None or (abs(nuevo_valor - ultimo_valor) > 400):
                    print(f"La diferencia entre los valores es demasiado grande ({abs(nuevo_valor - ultimo_valor)} puntos). No se publicará el tweet.")
                    notificar_telegram(f"Diferencia muy grande, no se publica: {abs(nuevo_valor - ultimo_valor)} pts")
                elif abs(nuevo_valor - ultimo_valor) != 0:
                    postear_tweet(nuevo_valor, ultimo_valor)
                else:
                    print(f"El riesgo país no cambió. Valor actual: {nuevo_valor}")

            # Verificar si la hora está entre 23:50 y 23:55 para actualizar el valor del día anterior
            if hora_actual.hour == 23 and 50 <= hora_actual.minute <= 55 and not actualizado_hoy:
                actualizar_valor_dia_anterior()
                guardar_historico_riesgo_pais(nuevo_valor)
                actualizado_hoy = True
                resumen_diario_posteado = False  # Permitir que se postee el resumen al día siguiente
                print("Valor del día anterior actualizado y Valor historico agregado.")

            # Postear el resumen diario a las 22:00
            if hora_actual.hour == 22 and not resumen_diario_posteado:
                postear_resumen_diario()
                resumen_diario_posteado = True

            # Resetear el indicador al inicio de un nuevo día
            if hora_actual.hour == 0:
                actualizado_hoy = False
                resumen_diario_posteado = False
                grafico_posteado = False
        else:
            print("Fuera del horario permitido. Bot en espera...")

        # Esperar 5 minutos antes de la próxima verificación
        time.sleep(300)  # 5 minutos = 300 segundos

    except Exception as e:
        print(f"Error en el loop principal: {e}. Reintentamos en 1 minuto.")
        notificar_telegram(f"Error en loop principal: {e}")
        time.sleep(60)
        continue
