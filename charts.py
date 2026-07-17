from __future__ import annotations
import math
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
import pytz
from database import obtener_valor_cercano_fecha
from utils import traducir_fecha

def obtener_presidente_por_fecha(fecha: datetime) -> str:
    """Retorna el apellido del presidente de Argentina en funciones en la fecha dada."""
    dt = fecha.date() if isinstance(fecha, datetime) else fecha
    if dt < datetime(1999, 12, 10).date():
        return "Menem"
    elif dt < datetime(2001, 12, 21).date():
        return "De la Rúa"
    elif dt < datetime(2002, 1, 2).date():
        return "Duhalde"
    elif dt < datetime(2003, 5, 25).date():
        return "Duhalde"
    elif dt < datetime(2007, 12, 10).date():
        return "Kirchner"
    elif dt < datetime(2015, 12, 10).date():
        return "C. Kirchner"
    elif dt < datetime(2019, 12, 10).date():
        return "Macri"
    elif dt < datetime(2023, 12, 10).date():
        return "Fernández"
    else:
        return "Milei"

def generar_grafico_en_memoria(datos):
    """Genera un gráfico visualmente moderno desde 1999 para el riesgo país."""
    # Ordenar los datos por año
    datos_ordenados = sorted(datos, key=lambda x: x[0])
    años = [d[0].year for d in datos_ordenados]
    valores = [d[1] for d in datos_ordenados]

    # Obtener la fecha actual para mostrarla en el título
    hoy = datetime.now()
    fecha_actual = traducir_fecha(hoy)
    
    # Configurar estilo visual premium (oscuro)
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 7.8), dpi=120)  # Más ancho y un poco más alto para alojar las llaves escalonadas
    fig.patch.set_facecolor('#0f172a')  # Slate 900
    ax.set_facecolor('#0f172a')
    
    # Rejilla sutil
    ax.grid(True, color='#334155', linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)
    
    min_valores = min(valores)
    
    # Graficar segmento por segmento con color dinámico
    for i in range(1, len(años)):
        went_down = valores[i] < valores[i-1]
        color = '#10b981' if went_down else '#ef4444'  # Verde esmeralda si bajó, Rojo si subió
        
        # Graficar línea de segmento
        ax.plot(años[i-1:i+1], valores[i-1:i+1], color=color, linewidth=3.5, zorder=2)
        
        # Graficar degradado translúcido de fondo para el segmento
        for alpha_val in [0.15, 0.08, 0.03]:
            ax.fill_between(años[i-1:i+1], valores[i-1:i+1], min_valores * 0.5, color=color, alpha=alpha_val, zorder=1)

    # Graficar marcadores al final (con color de borde según su tendencia)
    for i in range(len(años)):
        if i == 0:
            color = '#10b981' if valores[1] < valores[0] else '#ef4444'
        else:
            color = '#10b981' if valores[i] < valores[i-1] else '#ef4444'
            
        ax.plot(años[i], valores[i], marker='o', markersize=6, markerfacecolor='#ffffff', 
                markeredgecolor=color, markeredgewidth=1.8, zorder=3)

    # Configuración de límites y ticks del eje Y (forzamos bottom en 0)
    min_valor = min(valores)
    max_valor = max(valores)
    margen = (max_valor - min_valor) * 0.15
    ax.set_ylim(0, max_valor + margen)
    ax.tick_params(colors='#94a3b8', labelsize=10)
    
    # Ocultar bordes innecesarios
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#334155')
    ax.spines['bottom'].set_color('#334155')
    
    ax.set_ylabel("Puntos Básicos", color='#94a3b8', fontsize=11, labelpad=10)
    
    # Ocultar etiquetas estándar del eje X (las dibujaremos manualmente abajo)
    ax.set_xticks(años)
    ax.set_xticklabels([]) 
    
    # Obtener límites reales del gráfico para dibujar las llaves abajo
    y_min, y_max = ax.get_ylim()
    y_range = y_max - y_min
    
    # Definir coordenadas relativas abajo del eje X (y_min)
    y_years = y_min - y_range * 0.05       # Años justo abajo de la línea del eje
    y_bracket = y_min - y_range * 0.12     # Línea horizontal de la llave
    y_tick_limit = y_min - y_range * 0.09  # Topes verticales apuntando hacia arriba (a los años)
    
    # Dibujar etiquetas de años en horizontal corto (ej: '18)
    for yr in años:
        year_short = f"'{str(yr)[2:]}"
        ax.text(yr, y_years, year_short, color='#94a3b8', fontsize=10.5, fontweight='bold', 
                ha='center', va='top', clip_on=False)
    
    # Agrupar años consecutivos por presidente
    terms = []
    current_president = None
    start_yr = None
    for d, val in datos_ordenados:
        pres = obtener_presidente_por_fecha(d)
        if pres != current_president:
            if current_president is not None:
                terms.append((start_yr, last_yr, current_president))
            current_president = pres
            start_yr = d.year
        last_yr = d.year
    if current_president is not None:
        terms.append((start_yr, last_yr, current_president))
        
    # Dibujar llave y apellido una sola vez por mandato
    for idx, (x_start, x_end, president) in enumerate(terms):
        # Escalonamos la posición vertical de las etiquetas de texto y marcas centrales para evitar solapamientos entre mandatos cortos continuos
        is_even = (idx % 2 == 0)
        offset_tick = 0.15 if is_even else 0.22
        offset_text = 0.18 if is_even else 0.25
        
        y_center_tick = y_min - y_range * offset_tick
        y_text = y_min - y_range * offset_text
        
        # Usamos scaley=False para evitar que ax.plot agrande los límites reales del eje Y.
        if x_start == x_end:
            # Si el mandato tiene un solo año en el gráfico, dibujamos una sola línea vertical
            ax.plot([x_start, x_start], [y_bracket, y_center_tick], color='#475569', linewidth=1.5, clip_on=False, scaley=False)
        else:
            # Línea horizontal del corchete/llave
            ax.plot([x_start, x_end], [y_bracket, y_bracket], color='#475569', linewidth=1.5, clip_on=False, scaley=False)
            # Topes en los extremos apuntando hacia arriba (a los años)
            ax.plot([x_start, x_start], [y_bracket, y_bracket + y_range * 0.02], color='#475569', linewidth=1.5, clip_on=False, scaley=False)
            ax.plot([x_end, x_end], [y_bracket, y_bracket + y_range * 0.02], color='#475569', linewidth=1.5, clip_on=False, scaley=False)
            # Tilde/punta en el centro apuntando hacia abajo (al nombre del presidente)
            x_mid = (x_start + x_end) / 2
            ax.plot([x_mid, x_mid], [y_bracket, y_center_tick], color='#475569', linewidth=1.5, clip_on=False, scaley=False)
        
        # Apellido del presidente
        x_mid = (x_start + x_end) / 2
        ax.text(x_mid, y_text, president.upper(), color='#f8fafc', fontsize=9.0, fontweight='bold', 
                ha='center', va='top', clip_on=False)
    
    # Anotaciones de puntos clave (Mínimo, Máximo, y Último Valor)
    min_idx = np.argmin(valores)
    max_idx = np.argmax(valores)
    last_idx = len(valores) - 1
    
    # Anotación del valor Mínimo
    ax.annotate(f"Mín: {valores[min_idx]}", 
                xy=(años[min_idx], valores[min_idx]),
                xytext=(0, -18), textcoords='offset points', ha='center',
                color='#10b981', fontweight='bold', fontsize=9.5,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#0f172a', edgecolor='#10b981', alpha=0.8))

    # Anotación del valor Máximo
    ax.annotate(f"Máx: {valores[max_idx]}", 
                xy=(años[max_idx], valores[max_idx]),
                xytext=(0, 12), textcoords='offset points', ha='center',
                color='#ef4444', fontweight='bold', fontsize=9.5,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#0f172a', edgecolor='#ef4444', alpha=0.8))

    # Anotación del valor Actual (Badge destacado)
    last_went_down = valores[last_idx] < valores[last_idx-1]
    last_color = '#10b981' if last_went_down else '#ef4444'
    
    ax.annotate(f"Actual: {valores[last_idx]}", 
                xy=(años[last_idx], valores[last_idx]),
                xytext=(-15, 20), textcoords='offset points', ha='center',
                color='#ffffff', fontweight='bold', fontsize=11,
                bbox=dict(boxstyle='round,pad=0.3', facecolor=last_color, edgecolor=last_color, alpha=0.9),
                arrowprops=dict(arrowstyle="->", color='#ffffff', connectionstyle="arc3,rad=-0.2"))

    # Título del gráfico
    plt.title(f"Evolución Histórica - Riesgo País Argentino\n(Valores al {fecha_actual} de cada año)", 
              fontsize=14, fontweight='bold', color='#f8fafc', pad=20)
    
    # Guardar en memoria
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', facecolor='#0f172a')
    plt.close()
    buffer.seek(0)
    return buffer

def obtener_datos_historicos_para_grafico():
    """Obtiene los datos históricos necesarios para el gráfico de forma ultra-eficiente desde 1999."""
    hoy = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
    
    datos = []
    for año in range(1999, hoy.year + 1):  # Iterar desde 1999 hasta el año actual
        fecha_objetivo = datetime(año, hoy.month, hoy.day)
        
        # Retroceder hasta 5 días para saltear fines de semana y feriados
        fecha_encontrada, valor = obtener_valor_cercano_fecha(fecha_objetivo, max_dias_atras=5)
        if valor is not None:
            datos.append((fecha_encontrada, valor))
        else:
            print(f"⚠️ No se encontraron datos para el año {año}")
            
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
    datos = [(datetime.strptime(fecha, "%d-%m-%Y"), valor) for fecha, valor in datos_reales]
    return datos
