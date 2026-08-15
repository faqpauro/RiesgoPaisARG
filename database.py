from __future__ import annotations
from datetime import datetime, timedelta
import pytz
from config import db

def leer_ultimo_valor_guardado() -> int | None:
    doc_ref = db.collection('riesgo_pais').document('ultimo_valor')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('valor')
    return None

def leer_valor_dia_anterior() -> int | None:
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

def leer_valor_ultimo_dia_mes_anterior() -> int | None:
    """Lee el valor del último día del mes anterior desde Firebase."""
    doc_ref = db.collection('riesgo_pais').document('ultimo_dia_mes_anterior')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('valor')
    return None

def guardar_valor_ultimo_dia_mes_anterior(valor: int):
    """Guarda el valor del último día del mes actual en Firebase."""
    doc_ref = db.collection('riesgo_pais').document('ultimo_dia_mes_anterior')
    doc_ref.set({'valor': valor})
    print(f"Valor del último día del mes actual guardado: {valor}")

def guardar_valor_riesgo_pais(valor: int):
    doc_ref = db.collection('riesgo_pais').document('ultimo_valor')
    doc_ref.set({'valor': valor})

def actualizar_valor_dia_anterior():
    """Actualizar el valor del día anterior al final del día."""
    valor_actual = leer_ultimo_valor_guardado()
    if valor_actual is not None:
        guardar_valor_dia_anterior(valor_actual)

def guardar_valor_dia_anterior(valor: int):
    doc_ref = db.collection('riesgo_pais').document('valor_dia_anterior')
    doc_ref.set({'valor': valor})

def guardar_historico_riesgo_pais(valor: int):
    """Guarda el valor del riesgo país para la fecha actual en Firestore."""
    # Obtener la fecha actual en el formato requerido
    fecha_actual = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime('%d-%m-%Y')
    
    # Referencia al documento usando la fecha como ID
    doc_ref = db.collection('historico_riesgo_pais').document(fecha_actual)
    
    # Escritura del valor sin verificar si ya existe (asumimos que se ejecuta solo una vez al día)
    doc_ref.set({'fecha': fecha_actual, 'valor': valor})
    print(f"Valor del riesgo país guardado para la fecha {fecha_actual}: {valor}")

def obtener_valor_cercano_fecha(fecha_base: datetime, max_dias_atras: int = 5) -> tuple[datetime, int] | tuple[None, None]:
    """Obtiene de forma eficiente el valor del riesgo país en o cerca de la fecha base."""
    for i in range(max_dias_atras):
        fecha_test = fecha_base - timedelta(days=i)
        doc_id = fecha_test.strftime('%d-%m-%Y')
        doc_ref = db.collection('historico_riesgo_pais').document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            valor = doc.to_dict().get('valor')
            if valor is not None:
                return fecha_test, int(valor)
    return None, None

def buscar_mejor_valor_historico(valor_actual: int) -> tuple[datetime, int] | tuple[None, None]:
    """Busca de forma ultra-eficiente el último registro histórico inferior al valor actual."""
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(tz)
    
    # 1. Intentar buscar en los últimos 30 días en un solo lote (batch read)
    doc_refs = []
    fechas_map = {}
    for i in range(1, 31):
        fecha_test = hoy - timedelta(days=i)
        doc_id = fecha_test.strftime('%d-%m-%Y')
        ref = db.collection('historico_riesgo_pais').document(doc_id)
        doc_refs.append(ref)
        fechas_map[doc_id] = fecha_test
        
    try:
        docs = db.get_all(doc_refs)
        encontrados = []
        for doc in docs:
            if doc.exists:
                data = doc.to_dict()
                valor = data.get('valor')
                fecha_str = data.get('fecha')
                fecha_dt = fechas_map.get(fecha_str)
                if valor is not None and valor < valor_actual:
                    encontrados.append((fecha_dt, valor))
        
        if encontrados:
            # Retornar el más reciente
            encontrados.sort(key=lambda x: x[0], reverse=True)
            return encontrados[0][0], encontrados[0][1]
    except Exception as e:
        print(f"Error en batch get_all de Firestore: {e}")

    # 2. Si no se encontró en los últimos 30 días, hacemos un query filtrado por valor
    try:
        docs = db.collection('historico_riesgo_pais').where('valor', '<', valor_actual).stream()
        mejor_fecha = None
        mejor_valor = None
        for doc in docs:
            data = doc.to_dict()
            fecha_str = data.get('fecha')
            valor = data.get('valor')
            fecha = datetime.strptime(fecha_str, '%d-%m-%Y')
            if mejor_fecha is None or fecha > mejor_fecha:
                mejor_fecha = fecha
                mejor_valor = valor
        return mejor_fecha, mejor_valor
    except Exception as e:
        print(f"Error al buscar histórico filtrado: {e}")
        return None, None

def leer_ranking_america() -> dict | None:
    """Lee el documento con el ranking de América desde Firestore."""
    try:
        doc_ref = db.collection('riesgo_pais').document('ranking_america')
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"Error al leer ranking de América desde Firestore: {e}")
    return None

def guardar_ranking_america(paises: list[dict], fecha_actualizacion: str | None = None):
    """Guarda el listado completo del ranking de América en Firestore."""
    try:
        if not fecha_actualizacion:
            tz = pytz.timezone('America/Argentina/Buenos_Aires')
            fecha_actualizacion = datetime.now(tz).strftime('%d/%m/%Y %H:%M')
        
        doc_ref = db.collection('riesgo_pais').document('ranking_america')
        data = {
            'paises': paises,
            'ultima_actualizacion': fecha_actualizacion
        }
        doc_ref.set(data)
        print(f"✅ Ranking de América guardado en Firestore ({len(paises)} países).")
    except Exception as e:
        print(f"❌ Error al guardar ranking de América en Firestore: {e}")

