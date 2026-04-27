"""
Conexiones a fuentes de datos: Supabase (producción) y CSVs (pruebas).

Los CSVs de Typeform tienen la estructura nativa de exportación con columnas
en español como '¿Cuántas horas a la semana...?'.

Supabase tiene los datos en una estructura más limpia (tabla `responses`)
con columnas como d1, d2, d3, etc. Para que ambas fuentes alimenten el mismo
módulo de cálculo, los datos de Supabase se transforman al formato Typeform.
"""
import pandas as pd
import streamlit as st
from config import SUPABASE_URL, SUPABASE_KEY, COL_MAPPING_SUPABASE_TO_TYPEFORM


@st.cache_data(ttl=300)
def cargar_desde_csv(csv_baseline, csv_endline):
    """Lee los CSVs de Typeform y devuelve dos DataFrames listos para calcular."""
    baseline = pd.read_csv(csv_baseline)
    endline = pd.read_csv(csv_endline)
    return baseline, endline


@st.cache_data(ttl=60)
def cargar_desde_supabase(cohorte):
    """Lee respuestas de Supabase y las transforma al formato del notebook.

    Args:
        cohorte: identificador de cohorte (ej. 'C9')

    Returns:
        (baseline_df, endline_df) en formato compatible con calcular_todos_los_indicadores
    """
    try:
        from supabase import create_client
    except ImportError:
        raise RuntimeError(
            "Falta la librería supabase. Instálala con: pip install supabase"
        )

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Leer respuestas de la cohorte
    resp = sb.table('responses').select('*').eq('cohorte', cohorte).execute()
    df = pd.DataFrame(resp.data)

    if df.empty:
        raise ValueError(f"No hay respuestas para la cohorte {cohorte}")

    baseline_raw = df[df['tipo_encuesta'] == 'baseline'].copy()
    endline_raw = df[df['tipo_encuesta'] == 'endline'].copy()

    # Transformar al formato Typeform que espera el módulo de cálculo
    baseline = _transformar_supabase_a_typeform(baseline_raw, es_baseline=True)
    endline = _transformar_supabase_a_typeform(endline_raw, es_baseline=False)

    return baseline, endline


def _transformar_supabase_a_typeform(df, es_baseline):
    """Renombra columnas de Supabase a las columnas largas de Typeform.

    El módulo de cálculo fue diseñado para consumir el formato Typeform
    (las columnas largas con '*'). En Supabase las columnas son cortas (d1, d2...).
    Esta función traduce.
    """
    if df.empty:
        return df

    # Aplicar mapping de columnas
    rename_dict = {}
    for col_supabase, col_typeform in COL_MAPPING_SUPABASE_TO_TYPEFORM.items():
        if col_supabase in df.columns:
            rename_dict[col_supabase] = col_typeform

    df = df.rename(columns=rename_dict)

    # Crear las columnas que el módulo espera ver
    # Nombre completo: en Supabase está partido en nombre/apellido o en una sola
    if 'nombre' in df.columns and 'apellido' in df.columns:
        df['Por favor, ingresa tu nombre completo'] = df['nombre'].astype(str) + ' ' + df['apellido'].astype(str)
        df['Escribe tu nombre completo'] = df['Por favor, ingresa tu nombre completo']

    # Asegurar que existe la columna 'Response Type' (Supabase no la tiene, todo es completed)
    if 'Response Type' not in df.columns:
        df['Response Type'] = 'completed'

    return df


def consultar_estado_cohorte(cohorte):
    """Consulta el estado actual de los participantes de una cohorte.

    Devuelve un diccionario con totales útiles para mostrar antes de
    habilitar el endline.

    Args:
        cohorte: identificador de cohorte (ej. 'C8-prueba')

    Returns:
        dict con keys:
          - total: total de participantes en la cohorte
          - endline_habilitado: cuántos ya tienen la flag en true
          - endline_pendiente: cuántos están en false
          - participantes: DataFrame con la lista completa
    """
    try:
        from supabase import create_client
    except ImportError:
        raise RuntimeError("Falta supabase. Instala con: pip install supabase")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    resp = sb.table('participants') \
             .select('email,nombre,apellido,organizacion,endline_habilitado') \
             .eq('cohorte', cohorte) \
             .execute()

    df = pd.DataFrame(resp.data)

    if df.empty:
        return {
            'total': 0,
            'endline_habilitado': 0,
            'endline_pendiente': 0,
            'participantes': df
        }

    habilitados = df['endline_habilitado'].fillna(False).sum()
    return {
        'total': len(df),
        'endline_habilitado': int(habilitados),
        'endline_pendiente': len(df) - int(habilitados),
        'participantes': df
    }


def habilitar_endline_cohorte(cohorte):
    """Cambia endline_habilitado = true para todos los participantes de la cohorte.

    Equivale al SQL manual:
        UPDATE participants SET endline_habilitado = true WHERE cohorte = '...';

    Args:
        cohorte: identificador de cohorte

    Returns:
        número de filas afectadas
    """
    try:
        from supabase import create_client
    except ImportError:
        raise RuntimeError("Falta supabase. Instala con: pip install supabase")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    resp = sb.table('participants') \
             .update({'endline_habilitado': True}) \
             .eq('cohorte', cohorte) \
             .execute()

    # Limpiar caché para que la próxima consulta refleje el cambio
    consultar_estado_cohorte.clear() if hasattr(consultar_estado_cohorte, 'clear') else None

    return len(resp.data) if resp.data else 0


def actualizar_endline_emails(cohorte, emails, habilitar=True):
    """Habilita o deshabilita el endline para una lista específica de participantes.

    Args:
        cohorte: identificador de cohorte
        emails: lista de emails a actualizar
        habilitar: True para habilitar, False para deshabilitar

    Returns:
        número de filas afectadas
    """
    try:
        from supabase import create_client
    except ImportError:
        raise RuntimeError("Falta supabase. Instala con: pip install supabase")

    if not emails:
        return 0

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    resp = sb.table('participants') \
             .update({'endline_habilitado': habilitar}) \
             .eq('cohorte', cohorte) \
             .in_('email', emails) \
             .execute()

    # Limpiar caché
    if hasattr(consultar_estado_cohorte, 'clear'):
        consultar_estado_cohorte.clear()

    return len(resp.data) if resp.data else 0


def guardar_resultados_supabase(tabla_maestra):
    """Guarda la tabla maestra en la tabla 'indicators_master' de Supabase.

    Si la tabla no existe, hay que crearla primero con este SQL:

        create table indicators_master (
          id bigserial primary key,
          cohorte text,
          programa text,
          indicador text,
          valor numeric,
          unidad text,
          n integer,
          detalle text,
          calculado_at timestamptz default now()
        );
    """
    try:
        from supabase import create_client
    except ImportError:
        raise RuntimeError("Falta supabase. Instala con: pip install supabase")

    from datetime import datetime

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    registros = tabla_maestra.copy()
    registros['calculado_at'] = datetime.utcnow().isoformat()
    registros = registros.to_dict(orient='records')

    sb.table('indicators_master').insert(registros).execute()
