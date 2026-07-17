from __future__ import annotations
from datetime import datetime
import pytz
from config import client, api
from database import (
    leer_ultimo_valor_guardado,
    leer_valor_dia_anterior,
    buscar_mejor_valor_historico,
    leer_valor_ultimo_dia_mes_anterior,
    guardar_valor_ultimo_dia_mes_anterior,
    guardar_valor_riesgo_pais
)
from charts import obtener_datos_historicos_para_grafico, generar_grafico_en_memoria
from utils import (
    notificar_telegram,
    calcular_porcentaje_cambio_diario,
    calcular_porcentaje_cambio,
    traducir_fecha
)

def postear_grafico_directo():
    """Genera y postea un gráfico con los datos históricos de riesgo país directamente a X."""
    datos = obtener_datos_historicos_para_grafico()
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

def postear_grafico_moderado():
    """Genera el gráfico, lo envía a Telegram para aprobación, y lo publica en X si es aprobado."""
    from utils import enviar_grafico_moderacion_telegram, esperar_decision_moderacion
    
    datos = obtener_datos_historicos_para_grafico()
    if not datos:
        print("No hay suficientes datos para generar el gráfico.")
        return

    # Generar gráfico en memoria
    imagen_buffer = generar_grafico_en_memoria(datos)
    
    # 1. Enviar a Telegram para moderación
    message_id = enviar_grafico_moderacion_telegram(imagen_buffer)
    if not message_id:
        print("No se pudo iniciar la moderación del gráfico por Telegram. Publicando de forma directa.")
        notificar_telegram("⚠️ Error al iniciar la moderación por Telegram. Se procede con publicación directa.")
        return postear_grafico_directo()
        
    # 2. Esperar decisión (por defecto hasta 12 horas / 720 minutos)
    aprobado = esperar_decision_moderacion(message_id, timeout_minutos=720)
    
    if aprobado:
        imagen_buffer.seek(0)
        try:
            # Subir la imagen con `api`
            media = api.media_upload(filename="grafico.png", file=imagen_buffer)

            # Obtener la fecha actual y los rangos de años
            hoy = datetime.now()
            fecha_actual = traducir_fecha(hoy)
            años = [dato[0].year for dato in datos]
            rango_años = f"{min(años)}-{max(años)}"
            
            texto = (
                f"📊 #RiesgoPaís: {rango_años}\n"
                f"📅 Fecha: {fecha_actual}\n"
                "🇦🇷 #Argentina #Economía"
            )
            
            client.create_tweet(text=texto, media_ids=[media.media_id])
            print("Tweet con gráfico enviado tras aprobación.")
            notificar_telegram("✅ Gráfico histórico publicado con éxito en X (Twitter).")
        except Exception as e:
            print(f"Error al publicar gráfico aprobado: {e}")
            notificar_telegram(f"❌ Error al publicar gráfico aprobado en X: {e}")
    else:
        print("Publicación del gráfico cancelada (rechazada o expirada).")

def postear_grafico():
    """Genera y postea el gráfico histórico (soporta moderación por Telegram)."""
    import os
    moderacion = os.environ.get('MODERACION_GRAFICO', 'true').lower() == 'true'
    
    if moderacion:
        return postear_grafico_moderado()
    else:
        return postear_grafico_directo()

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
                linea_referencia = f"⚖️ Igual que {igual_txt}"
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

        mejor_fecha, mejor_valor = buscar_mejor_valor_historico(valor_actual)
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
    mejor_fecha, mejor_valor = buscar_mejor_valor_historico(valor_actual)

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
