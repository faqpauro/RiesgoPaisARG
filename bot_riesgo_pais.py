from __future__ import annotations
import time
from datetime import datetime, timedelta
import pytz

from database import (
    leer_ultimo_valor_guardado,
    actualizar_valor_dia_anterior,
    guardar_historico_riesgo_pais
)
from scraper import obtener_riesgo_pais
from publisher import (
    postear_tweet,
    postear_resumen_diario,
    postear_resumen_mensual,
    postear_grafico
)
from utils import notificar_telegram
from ranking_manager import (
    ejecutar_flujo_ranking_telegram,
    sincronizar_ranking_automatico,
    verificar_comando_telegram
)

def esperar_con_escucha(segundos: int = 300, intervalo: int = 10):
    """Espera una cantidad de segundos pero verifica periódicamente comandos de Telegram."""
    transcurrido = 0
    while transcurrido < segundos:
        if verificar_comando_telegram():
            print("📩 Comando /ranking recibido por Telegram. Iniciando cuestionario...")
            ejecutar_flujo_ranking_telegram()
        time.sleep(intervalo)
        transcurrido += intervalo

if __name__ == '__main__':
    # Bucle principal
    actualizado_hoy = False
    resumen_diario_posteado = False
    grafico_posteado = False
    resumen_mensual_posteado = False
    ranking_preguntado = False

    print("🤖 Bot de Riesgo País iniciado correctamente...")
    notificar_telegram("Bot de Riesgo País iniciado correctamente")

    while True:
        try:
            # Obtener la hora y día actual en la zona horaria de Buenos Aires
            ahora = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
            hora_actual = ahora.time()
            dia_actual = ahora.weekday()  # 0 = Lunes, 5 = Sábado, 6 = Domingo
            ultimo_dia_mes = (ahora + timedelta(days=1)).day == 1  # Verificar si es el último día del mes

            # Publicar resumen mensual el último día del mes a las 22:00
            if ultimo_dia_mes and hora_actual.hour == 22 and 10 <= hora_actual.minute <= 15 and not resumen_mensual_posteado:
                postear_resumen_mensual()
                resumen_mensual_posteado = True

            # Resetear indicador al inicio de un nuevo mes
            if ahora.day == 1 and hora_actual.hour == 0:
                resumen_mensual_posteado = False

            # Publicar gráfico histórico los sábados a las 14:00 PM
            if dia_actual == 5 and hora_actual.hour == 14 and not grafico_posteado:
                postear_grafico()
                grafico_posteado = True

            # Actualizar ranking de América interactivo por Telegram los domingos a las 14:00 PM
            if dia_actual == 6 and hora_actual.hour == 14 and not ranking_preguntado:
                ejecutar_flujo_ranking_telegram()
                ranking_preguntado = True

            # Verificar si está dentro del horario permitido de mercado (Lunes a Viernes)
            if dia_actual < 5 and (hora_actual >= datetime.strptime("08:00", "%H:%M").time() or hora_actual <= datetime.strptime("01:00", "%H:%M").time()):
                nuevo_valor = obtener_riesgo_pais()

                if nuevo_valor is None:
                    print("No se obtuvo Riesgo País; reintentamos en 5 minutos.")
                    esperar_con_escucha(300)
                    continue

                if nuevo_valor != 0:
                    ultimo_valor = leer_ultimo_valor_guardado()
                    if ultimo_valor is None:
                        # Si no hay valor anterior guardado, posteamos el valor inicial directo
                        postear_tweet(nuevo_valor, ultimo_valor)
                    else:
                        diferencia = nuevo_valor - ultimo_valor
                        if abs(diferencia) > 400:
                            print(f"La diferencia entre los valores es demasiado grande ({abs(diferencia)} puntos). No se publicará el tweet.")
                            notificar_telegram(f"Diferencia muy grande, no se publica: {abs(diferencia)} pts")
                        elif diferencia != 0:
                            postear_tweet(nuevo_valor, ultimo_valor)
                        else:
                            print(f"El riesgo país no cambió. Valor actual: {nuevo_valor}")

                # Verificar si la hora está entre 23:50 y 23:55 para actualizar el valor del día anterior
                if hora_actual.hour == 23 and 50 <= hora_actual.minute <= 55 and not actualizado_hoy:
                    actualizar_valor_dia_anterior()
                    guardar_historico_riesgo_pais(nuevo_valor)
                    sincronizar_ranking_automatico()
                    actualizado_hoy = True
                    resumen_diario_posteado = False  # Permitir que se postee el resumen al día siguiente
                    print("Valor del día anterior actualizado, histórico guardado y ranking sincronizado.")

                # Postear el resumen diario a las 22:00
                if hora_actual.hour == 22 and not resumen_diario_posteado:
                    postear_resumen_diario()
                    resumen_diario_posteado = True

                # Resetear el indicador al inicio de un nuevo día
                if hora_actual.hour == 0:
                    actualizado_hoy = False
                    resumen_diario_posteado = False
                    grafico_posteado = False
                    ranking_preguntado = False

                # Esperar 5 minutos antes de la próxima verificación
                esperar_con_escucha(300)
            else:
                # Resetear flags a medianoche en fines de semana
                if hora_actual.hour == 0:
                    actualizado_hoy = False
                    resumen_diario_posteado = False
                    grafico_posteado = False
                    ranking_preguntado = False

                print("Fuera del horario de mercado. Bot en espera...")
                esperar_con_escucha(300)

        except Exception as e:
            print(f"Error en el loop principal: {e}. Reintentamos en 1 minuto.")
            notificar_telegram(f"Error en loop principal: {e}")
            time.sleep(60)
            continue
