"""
Propel M&E — Calculadora automática de indicadores
Fase 2 del sistema integrado de Monitoreo y Evaluación.

Lee datos crudos de baseline y endline (desde Supabase o CSVs), aplica las
fórmulas oficiales de la Guía de cálculo de indicadores de Propel, y produce
una tabla maestra con todos los indicadores listos para reporte.

Uso:
    streamlit run app.py

Validado contra la Cohorte 8 — los resultados coinciden con el cálculo manual
de Melissa (con pequeñas diferencias en N por filtrado contra Salesforce que
no aplica en producción donde se usa email como llave estable).
"""

import streamlit as st
import pandas as pd
import unicodedata
import re
from datetime import datetime

from indicadores import calcular_todos_los_indicadores
from data_sources import (
    cargar_desde_supabase,
    cargar_desde_csv,
    guardar_resultados_supabase,
    consultar_estado_cohorte,
    habilitar_endline_cohorte,
    actualizar_endline_emails,
)
from config import COHORTES_DISPONIBLES, PROGRAMAS

# ============================================================
# Configuración de la página
# ============================================================
st.set_page_config(
    page_title="Propel M&E — Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CSS institucional Propel — estilos custom inyectados
# ============================================================
PROPEL_CSS = """
<style>
/* ----- Fuentes ----- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, .stTextInput, .stSelectbox, p, h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* Reducir el padding superior del contenido principal */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1200px;
}

/* ----- Header institucional ----- */
.propel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0 24px 0;
    border-bottom: 1px solid #e8e8e0;
    margin-bottom: 32px;
    flex-wrap: wrap;
    gap: 16px;
}
.propel-header-left {
    display: flex;
    align-items: center;
    gap: 20px;
}
.propel-header-logo {
    width: 110px;
    height: auto;
    flex-shrink: 0;
}
.propel-header-divider {
    width: 1px;
    height: 36px;
    background: #d0d0c8;
}
.propel-header-title {
    font-size: 18px;
    font-weight: 600;
    color: #1d4d4d;
    line-height: 1.2;
    letter-spacing: -0.01em;
}
.propel-header-subtitle {
    font-size: 13px;
    color: #6b7575;
    font-weight: 400;
    margin-top: 2px;
}
.propel-header-right {
    text-align: right;
    font-size: 12px;
    color: #6b7575;
    line-height: 1.5;
}
.propel-header-badge {
    display: inline-block;
    padding: 4px 10px;
    background: #1d4d4d;
    color: white;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    margin-bottom: 4px;
}

/* ----- Sidebar pulida ----- */
section[data-testid="stSidebar"] {
    background: #f5f5f0;
    border-right: 1px solid #e8e8e0;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem !important;
}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #1d4d4d;
    font-weight: 700;
    letter-spacing: -0.01em;
}

/* Sidebar header con logo pequeño */
.sidebar-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0 20px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid #e8e8e0;
}
.sidebar-header-logo { width: 28px; height: 28px; flex-shrink: 0; }
.sidebar-header-text {
    font-size: 13px;
    font-weight: 700;
    color: #1d4d4d;
    letter-spacing: -0.01em;
}

/* ----- Tabs modernas ----- */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid #e8e8e0;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    height: 44px;
    padding: 0 18px;
    background: transparent;
    border-radius: 8px 8px 0 0;
    font-weight: 500;
    color: #6b7575;
    border-bottom: 2px solid transparent;
    transition: all 0.15s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #1d4d4d;
    background: rgba(29, 77, 77, 0.04);
}
.stTabs [aria-selected="true"] {
    color: #1d4d4d !important;
    font-weight: 600;
    border-bottom: 2px solid #1d4d4d !important;
}

/* ----- Métricas (st.metric) con look más profesional ----- */
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e8e8e0;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    transition: box-shadow 0.15s ease;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 2px 8px rgba(29, 77, 77, 0.06);
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #6b7575 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #1d4d4d !important;
    letter-spacing: -0.02em;
}

/* ----- Botones primarios con verde Propel ----- */
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: #1d4d4d;
    color: white;
    border: 1px solid #1d4d4d;
    font-weight: 600;
    letter-spacing: 0.01em;
    transition: all 0.15s ease;
    border-radius: 8px;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    background: #143838;
    border-color: #143838;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(29, 77, 77, 0.25);
}
.stButton > button[kind="primary"]:active {
    transform: translateY(0);
}

/* Botones secundarios */
.stButton > button[kind="secondary"],
.stDownloadButton > button[kind="secondary"] {
    background: white;
    color: #1d4d4d;
    border: 1px solid #d0d0c8;
    font-weight: 500;
    border-radius: 8px;
    transition: all 0.15s ease;
}
.stButton > button[kind="secondary"]:hover,
.stDownloadButton > button[kind="secondary"]:hover {
    border-color: #1d4d4d;
    background: #f5f5f0;
}

/* ----- Banners de estado (success/warning/info/error) ----- */
[data-testid="stAlert"] {
    border-radius: 10px;
    border-left-width: 4px !important;
    padding: 12px 16px;
}

/* ----- Inputs ----- */
.stTextInput > div > div > input,
.stTextArea textarea,
.stNumberInput input {
    border-radius: 8px;
    border: 1px solid #d0d0c8;
    transition: border 0.15s ease;
}
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus,
.stNumberInput input:focus {
    border-color: #1d4d4d;
    box-shadow: 0 0 0 3px rgba(29, 77, 77, 0.08);
}

/* ----- Expanders ----- */
.streamlit-expanderHeader {
    background: white;
    border: 1px solid #e8e8e0;
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.15s ease;
}
.streamlit-expanderHeader:hover {
    border-color: #1d4d4d;
}

/* ----- Gráficos Plotly con marco elegante ----- */
[data-testid="stPlotlyChart"] {
    background: white;
    border: 1px solid #e8e8e0;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    transition: box-shadow 0.2s ease;
}
[data-testid="stPlotlyChart"]:hover {
    box-shadow: 0 4px 12px rgba(29, 77, 77, 0.08);
    border-color: #d0d0c8;
}

/* Imágenes con marco también (mapa, etc.) */
[data-testid="stImage"] img {
    border-radius: 8px;
    border: 1px solid #e8e8e0;
}

/* DataFrames con bordes consistentes */
[data-testid="stDataFrame"] {
    border: 1px solid #e8e8e0;
    border-radius: 8px;
    overflow: hidden;
}

/* ----- Footer institucional ----- */
.propel-footer {
    margin-top: 64px;
    padding-top: 24px;
    border-top: 1px solid #e8e8e0;
    text-align: center;
    color: #9ba3a3;
    font-size: 12px;
    line-height: 1.6;
}
.propel-footer strong { color: #1d4d4d; font-weight: 600; }

/* ----- Headings con jerarquía clara ----- */
h1 { color: #1d4d4d; font-weight: 700; letter-spacing: -0.025em; }
h2 { color: #1d4d4d; font-weight: 600; letter-spacing: -0.02em; margin-top: 1.5em !important; }
h3 { color: #1a2e35; font-weight: 600; letter-spacing: -0.01em; }

/* Quitar el "Made with Streamlit" del footer */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
"""

# Logo Propel SVG embebido (descargado desde Webflow). Vive en el código para
# no depender de URLs externas y que cargue al instante.
PROPEL_LOGO_SVG = '''<svg class="propel-header-logo" width="145" height="44" viewBox="0 0 145 44" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M33.3632 8.84209C31.8967 10.4698 30.422 12.0975 28.9474 13.7252C20.0756 23.564 11.2118 33.4028 2.33194 43.2335C2.08214 43.5075 1.78399 43.7895 1.45362 43.9265C0.817036 44.1844 0.124052 43.7331 0.0273568 43.0482C-0.0129331 42.7903 0.00318381 42.5244 0.00318381 42.2585C0.00318381 34.2892 0.00318381 26.3198 0.00318381 18.3505C0.00318381 9.0113 6.91693 1.24341 16.2158 0.131412C26.0063 -1.04505 34.9829 5.80422 36.4897 15.6027C37.8918 24.7163 32.2915 33.427 23.3874 35.9813C22.7509 36.1667 22.074 36.4487 21.526 35.8041C20.9781 35.1675 21.3488 34.5551 21.6389 33.9427C25.4664 25.8686 29.2939 17.7945 33.1215 9.72041C33.2423 9.47061 33.3471 9.20469 33.4599 8.94684C33.4277 8.91461 33.3874 8.87432 33.3552 8.84209" fill="#FD6A44"/><path d="M49.6486 23.9267C51.4697 23.9589 53.2263 24.112 54.9104 23.4029C56.0788 22.9114 56.522 21.9686 56.5704 20.7599C56.6187 19.527 56.2964 18.4634 55.12 17.8993C53.3633 17.0613 51.51 17.1338 49.6486 17.4078V23.9186V23.9267ZM49.5841 28.5519V34.4504C49.5841 36.0942 49.5519 36.1264 47.9322 36.1264C47.1264 36.1264 46.3206 36.1264 45.5068 36.1264C44.8299 36.1264 44.4512 35.8525 44.4512 35.1111C44.4592 28.1974 44.4512 21.2756 44.4512 14.3618C44.4512 13.8139 44.6043 13.3949 45.1925 13.3143C48.9717 12.8389 52.767 12.4763 56.5059 13.4916C61.7114 14.9179 63.7662 21.195 60.4221 25.3771C59.1087 27.0209 57.2392 27.7139 55.265 28.0201C53.4439 28.3021 51.5906 28.3747 49.5761 28.5519" fill="#1D4D4D"/><path d="M103.758 22.4198C103.758 25.4658 103.758 28.2377 103.774 31.0016C103.774 31.195 103.927 31.4609 104.088 31.5656C106.224 33.008 109.1 31.9282 109.721 29.4544C110.067 28.0765 110.067 26.6744 109.68 25.3046C109.229 23.7011 108.23 22.6293 106.522 22.436C105.643 22.3393 104.749 22.4198 103.766 22.4198M103.758 35.5866C103.758 37.3513 103.758 39.0112 103.758 40.6792C103.758 41.9201 103.693 41.9766 102.42 41.9846C101.582 41.9846 100.744 41.9524 99.9061 41.9927C99.1326 42.0249 98.8344 41.7106 98.8425 40.9371C98.8666 38.3424 98.8425 35.7397 98.8425 33.145C98.8425 28.8743 98.8666 24.6035 98.8263 20.3328C98.8183 19.4384 99.1326 19.0435 99.9948 18.8824C102.71 18.3908 105.418 17.9396 108.174 18.4392C111.912 19.1161 114.394 21.7349 114.829 25.5302C115.087 27.8106 114.975 30.0588 113.967 32.1861C112.364 35.5705 108.826 37.0209 104.878 35.9008C104.539 35.8041 104.209 35.7074 103.742 35.5785" fill="#1D4D4D"/><path d="M129.245 25.4496C129.229 23.3868 127.875 22.0975 125.949 22.2023C124.209 22.299 122.847 23.8139 123.041 25.4496H129.245ZM122.912 28.8501C122.944 29.954 123.46 30.6793 124.233 31.2514C125.353 32.0733 126.667 32.2586 127.988 32.17C129.14 32.0975 130.301 31.896 131.437 31.6462C132.146 31.4931 132.468 31.7349 132.589 32.3714C132.702 32.9597 132.767 33.5479 132.863 34.1361C133.057 35.3126 133.016 35.4335 131.904 35.7155C129.269 36.3924 126.61 36.6905 123.927 36.0136C120.543 35.1595 118.391 32.6776 117.94 29.2127C117.505 25.8203 117.996 22.6535 120.639 20.2522C123.282 17.851 126.441 17.5206 129.68 18.8501C132.895 20.1636 133.935 22.9758 134.048 26.1587C134.169 29.4142 134.201 28.8018 131.493 28.834C128.979 28.8662 126.465 28.834 123.959 28.834H122.912V28.8501Z" fill="#1D4D4D"/><path d="M84.0557 30.5745C84.5553 31.7107 85.6189 32.1942 86.8357 32.178C88.1008 32.1619 89.0677 31.5737 89.6076 30.3972C90.5423 28.3666 90.5504 26.2877 89.6882 24.249C89.1886 23.0725 88.2297 22.3957 86.8921 22.3715C85.5303 22.3393 84.4666 22.9033 83.9428 24.1362C83.0242 26.2877 83.0242 28.4472 84.0557 30.5745ZM78.2217 27.4077C78.3748 23.4754 79.6963 20.3892 83.3707 18.834C88.1169 16.8276 94.8936 18.971 95.2804 26.6583C95.4335 29.7284 94.7164 32.5568 92.1942 34.6035C87.1983 38.6486 79.5593 35.78 78.4634 29.4625C78.3345 28.7292 78.3587 28.4391 78.2217 27.4077Z" fill="#1D4D4D"/><path d="M142.299 19.801C142.299 22.8469 142.315 25.8928 142.299 28.9307C142.283 30.4859 142.541 31.7913 144.378 32.178C144.588 32.2264 144.846 32.7824 144.829 33.0805C144.773 33.9105 144.644 34.7485 144.419 35.5463C144.346 35.8122 143.863 36.1909 143.621 36.1506C142.34 35.9492 141.01 35.788 139.817 35.3207C138.246 34.7082 137.642 33.2739 137.497 31.6623C137.424 30.8646 137.424 30.0507 137.424 29.2449C137.424 24.112 137.424 18.9791 137.408 13.8461C137.408 13.1129 137.61 12.5327 138.117 12.0009C138.979 11.0903 139.761 10.0992 140.647 9.22086C140.913 8.95495 141.461 8.76962 141.792 8.85826C142.033 8.92272 142.275 9.50289 142.275 9.85744C142.315 13.1693 142.299 16.4811 142.299 19.7929" fill="#1D4D4D"/><path d="M65.4099 27.5931C65.4099 25.1676 65.4099 22.7422 65.4099 20.3167C65.4099 19.7849 65.5066 19.382 66.0949 19.1966C69.2697 18.1813 72.4768 17.7865 75.7886 18.4714C76.6186 18.6406 76.8603 19.0355 76.6911 19.801C76.5461 20.4537 76.3849 21.0983 76.2882 21.7591C76.1673 22.6455 75.6839 22.7744 74.87 22.6696C73.7419 22.5165 72.5896 22.5246 71.4454 22.4601C70.6315 22.4198 70.3737 22.7744 70.3817 23.6044C70.4301 27.303 70.4059 31.0016 70.3978 34.7083C70.3978 35.9895 70.2608 36.1184 68.9957 36.1264C68.1738 36.1264 67.3519 36.1184 66.5381 36.1264C65.7403 36.1345 65.3938 35.78 65.4099 34.9661C65.4341 32.5084 65.418 30.0507 65.418 27.5931" fill="#1D4D4D"/></svg>'''

st.markdown(PROPEL_CSS, unsafe_allow_html=True)

# ============================================================
# Header institucional con logo Propel
# ============================================================
from datetime import datetime as _dt
_fecha_hoy = _dt.now().strftime('%d/%m/%Y')

st.markdown(f"""
<div class="propel-header">
    <div class="propel-header-left">
        {PROPEL_LOGO_SVG}
        <div class="propel-header-divider"></div>
        <div>
            <div class="propel-header-title">M&E Portal</div>
            <div class="propel-header-subtitle">Sistema de Monitoreo y Evaluación</div>
        </div>
    </div>
    <div class="propel-header-right">
        <span class="propel-header-badge">Beca SER ANDI · Grupo 9</span><br>
        <span>{_fecha_hoy}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# Sidebar — selección de modo y parámetros
# ============================================================
with st.sidebar:
    # Mini-header de la sidebar con logo
    st.markdown(f"""
    <div class="sidebar-header">
        <svg width="28" height="28" viewBox="0 0 37 44" fill="none" xmlns="http://www.w3.org/2000/svg" class="sidebar-header-logo">
            <path d="M33.3632 8.84209C31.8967 10.4698 30.422 12.0975 28.9474 13.7252C20.0756 23.564 11.2118 33.4028 2.33194 43.2335C2.08214 43.5075 1.78399 43.7895 1.45362 43.9265C0.817036 44.1844 0.124052 43.7331 0.0273568 43.0482C-0.0129331 42.7903 0.00318381 42.5244 0.00318381 42.2585C0.00318381 34.2892 0.00318381 26.3198 0.00318381 18.3505C0.00318381 9.0113 6.91693 1.24341 16.2158 0.131412C26.0063 -1.04505 34.9829 5.80422 36.4897 15.6027C37.8918 24.7163 32.2915 33.427 23.3874 35.9813C22.7509 36.1667 22.074 36.4487 21.526 35.8041C20.9781 35.1675 21.3488 34.5551 21.6389 33.9427C25.4664 25.8686 29.2939 17.7945 33.1215 9.72041C33.2423 9.47061 33.3471 9.20469 33.4599 8.94684C33.4277 8.91461 33.3874 8.87432 33.3552 8.84209" fill="#FD6A44"/>
        </svg>
        <span class="sidebar-header-text">Propel M&E</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("##### ⚙️ Configuración")

    modo = st.radio(
        "Origen de los datos",
        options=["Supabase (producción)", "Subir CSVs (pruebas)"],
        help="Supabase lee los datos en vivo. CSVs sirve para probar con cohortes "
             "históricas como C8 que no están en la base de datos."
    )

    programa = st.selectbox(
        "Programa",
        options=PROGRAMAS,
        index=0
    )

    if modo == "Supabase (producción)":
        cohorte = st.selectbox(
            "Cohorte",
            options=COHORTES_DISPONIBLES,
            help="Cohortes registradas en Supabase. Puedes editarlas en config.py"
        )
    else:
        cohorte = st.text_input(
            "Identificador de cohorte",
            value="C8",
            help="Solo para etiquetar los resultados. Ej: 'C8', 'C9', etc."
        )

    st.divider()
    guardar_supabase = st.checkbox(
        "Guardar resultados en Supabase",
        value=False,
        help="Si está activo, guarda la tabla maestra en la tabla 'indicators_master'"
    )

    # Footer de sidebar
    st.markdown("""
    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #e8e8e0;
                font-size: 11px; color: #9ba3a3; line-height: 1.5;">
        <strong style="color: #1d4d4d; font-weight: 600;">Sistema integrado de M&E</strong><br>
        Fase 1 · n8n recordatorios<br>
        Fase 2 · Cálculo automático<br>
        Fase 3 · Asistente IA
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# Pestañas principales
# ============================================================
tab_gestion, tab_calculo, tab_reporte = st.tabs([
    "🎛️  Gestión de cohorte",
    "🎯  Calcular indicadores",
    "🤖  Generar reporte",
])

# ============================================================
# Pestaña 1 — Gestión de cohorte (habilitar endline)
# ============================================================
with tab_gestion:
    st.subheader("Gestión de cohorte")
    st.caption(
        "Activa el endline cuando termine el programa. "
        "Esto hace que Fase 1 (recordatorios automáticos en n8n) empiece a "
        "enviar correos invitando a los participantes a llenar la encuesta de salida."
    )

    if modo != "Supabase (producción)":
        st.info(
            "🔧 La gestión de cohorte solo está disponible en modo Supabase. "
            "Cambia el origen de datos en la barra lateral para usarla."
        )
    else:
        # Mostrar estado actual
        col_a, col_b = st.columns([3, 1])
        with col_b:
            refrescar = st.button("🔄 Refrescar", use_container_width=True)
        with col_a:
            st.markdown(f"**Cohorte seleccionada:** `{cohorte}`")

        try:
            # Forzar invalidación si el usuario pidió refrescar
            if refrescar and hasattr(consultar_estado_cohorte, 'clear'):
                consultar_estado_cohorte.clear()

            estado = consultar_estado_cohorte(cohorte)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Total participantes", estado['total'])
            with c2:
                st.metric("Endline habilitado", estado['endline_habilitado'])
            with c3:
                st.metric("Endline pendiente", estado['endline_pendiente'])

            st.divider()

            if estado['total'] == 0:
                st.warning("Esta cohorte no tiene participantes registrados todavía.")
            else:
                # ==========================================
                # OPCIÓN A — Habilitación masiva
                # ==========================================
                st.markdown("### 🚀 Opción A — Habilitar todos los pendientes")

                if estado['endline_pendiente'] == 0:
                    st.info(
                        "✅ Todos los participantes ya tienen el endline habilitado. "
                        "Si quieres deshabilitar a alguien, usa la Opción B abajo."
                    )
                else:
                    clave_confirmacion = f'confirmar_endline_{cohorte}'

                    if not st.session_state.get(clave_confirmacion):
                        st.write(
                            f"Habilita el endline para **los {estado['endline_pendiente']} "
                            "participantes pendientes** de un solo clic."
                        )
                        if st.button(
                            "▶️ Habilitar todos los pendientes",
                            type="primary",
                            use_container_width=True,
                            key='btn_masivo',
                        ):
                            st.session_state[clave_confirmacion] = True
                            st.rerun()
                    else:
                        st.warning(
                            f"⚠️ **¿Confirmas?**\n\n"
                            f"Vas a habilitar el endline para **{estado['endline_pendiente']} "
                            f"participantes** de la cohorte `{cohorte}`. "
                            f"Fase 1 enviará correos automáticos en los próximos cortes."
                        )
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("✅ Sí, habilitar todos",
                                         type="primary",
                                         use_container_width=True,
                                         key='btn_masivo_si'):
                                try:
                                    with st.spinner("Habilitando endline..."):
                                        n = habilitar_endline_cohorte(cohorte)
                                    st.session_state[clave_confirmacion] = False
                                    st.success(f"✅ {n} participantes actualizados.")
                                    if hasattr(consultar_estado_cohorte, 'clear'):
                                        consultar_estado_cohorte.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                                    st.session_state[clave_confirmacion] = False
                        with cc2:
                            if st.button("❌ Cancelar",
                                         use_container_width=True,
                                         key='btn_masivo_no'):
                                st.session_state[clave_confirmacion] = False
                                st.rerun()

                st.divider()

                # ==========================================
                # OPCIÓN B — Selección individual con checkboxes
                # ==========================================
                st.markdown("### ✏️ Opción B — Selección individual")
                st.caption(
                    "Marca o desmarca participantes específicos. Cuando termines, "
                    "da clic en **Aplicar cambios** abajo de la tabla."
                )

                # Preparar tabla editable con columna de checkbox
                df_editable = estado['participantes'].copy()
                # Asegurar que endline_habilitado sea booleano (Supabase a veces devuelve None)
                df_editable['endline_habilitado'] = df_editable['endline_habilitado'].fillna(False).astype(bool)

                # Reordenar columnas para que la checkbox quede a la izquierda
                cols_orden = ['endline_habilitado', 'email', 'nombre', 'apellido', 'organizacion']
                cols_disponibles = [c for c in cols_orden if c in df_editable.columns]
                df_editable = df_editable[cols_disponibles]

                df_editado = st.data_editor(
                    df_editable,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'endline_habilitado': st.column_config.CheckboxColumn(
                            'Endline habilitado',
                            help="Marca para habilitar, desmarca para deshabilitar",
                            default=False,
                        ),
                        'email': st.column_config.TextColumn('Email', disabled=True),
                        'nombre': st.column_config.TextColumn('Nombre', disabled=True),
                        'apellido': st.column_config.TextColumn('Apellido', disabled=True),
                        'organizacion': st.column_config.TextColumn('Organización', disabled=True),
                    },
                    disabled=['email', 'nombre', 'apellido', 'organizacion'],
                    key=f'editor_{cohorte}',
                )

                # Detectar cambios comparando el original con el editado
                # Ambos están ordenados igual y con el mismo índice
                cambios = df_editado.compare(df_editable)

                if not cambios.empty:
                    # Sacar los emails que cambiaron y a qué valor
                    n_cambios = len(cambios)
                    nuevos_habilitar = []
                    nuevos_deshabilitar = []
                    for idx in cambios.index:
                        email = df_editado.loc[idx, 'email']
                        nuevo_estado = df_editado.loc[idx, 'endline_habilitado']
                        if nuevo_estado:
                            nuevos_habilitar.append(email)
                        else:
                            nuevos_deshabilitar.append(email)

                    msg_partes = []
                    if nuevos_habilitar:
                        msg_partes.append(f"**{len(nuevos_habilitar)} a habilitar**")
                    if nuevos_deshabilitar:
                        msg_partes.append(f"**{len(nuevos_deshabilitar)} a deshabilitar**")
                    st.info(f"📝 Cambios detectados: {' · '.join(msg_partes)}")

                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button(
                            f"💾 Aplicar {n_cambios} cambio(s)",
                            type="primary",
                            use_container_width=True,
                            key='btn_individual',
                        ):
                            try:
                                total = 0
                                with st.spinner("Aplicando cambios..."):
                                    if nuevos_habilitar:
                                        total += actualizar_endline_emails(
                                            cohorte, nuevos_habilitar, habilitar=True
                                        )
                                    if nuevos_deshabilitar:
                                        total += actualizar_endline_emails(
                                            cohorte, nuevos_deshabilitar, habilitar=False
                                        )
                                st.success(f"✅ {total} participantes actualizados.")
                                if hasattr(consultar_estado_cohorte, 'clear'):
                                    consultar_estado_cohorte.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al aplicar cambios: {e}")
                    with cc2:
                        if st.button(
                            "🔄 Descartar cambios",
                            use_container_width=True,
                            key='btn_individual_cancel',
                        ):
                            st.rerun()
                else:
                    st.caption("_Sin cambios pendientes._")

        except Exception as e:
            st.error(f"Error al consultar estado: {e}")
            st.info("Verifica las credenciales de Supabase en config.py")


# ============================================================
# Pestaña 2 — Cálculo de indicadores (lo que ya existía)
# ============================================================
with tab_calculo:
    baseline = None
    endline = None

    if modo == "Supabase (producción)":
        st.subheader("🔌 Cargar datos desde Supabase")
        if st.button("Conectar y cargar", type="primary"):
            with st.spinner(f"Cargando datos de cohorte {cohorte}..."):
                try:
                    baseline, endline = cargar_desde_supabase(cohorte)
                    st.session_state['baseline'] = baseline
                    st.session_state['endline'] = endline
                    st.success(f"✅ Cargados: {len(baseline)} respuestas baseline · {len(endline)} respuestas endline")
                except Exception as e:
                    st.error(f"Error al conectar con Supabase: {e}")
                    st.info("Verifica credenciales en config.py")

    else:  # CSV
        st.subheader("📁 Subir CSVs de Typeform")
        col1, col2 = st.columns(2)
        with col1:
            csv_baseline = st.file_uploader(
                "RAW_baseline.csv",
                type='csv',
                help="Exportado de Typeform"
            )
        with col2:
            csv_endline = st.file_uploader(
                "RAW_endline.csv",
                type='csv',
                help="Exportado de Typeform"
            )

        if csv_baseline and csv_endline:
            try:
                baseline, endline = cargar_desde_csv(csv_baseline, csv_endline)
                st.session_state['baseline'] = baseline
                st.session_state['endline'] = endline
                st.success(f"✅ Cargados: {len(baseline)} baseline · {len(endline)} endline")
            except Exception as e:
                st.error(f"Error al leer CSVs: {e}")

    # Recuperar de session_state si ya están cargados
    if 'baseline' in st.session_state and baseline is None:
        baseline = st.session_state['baseline']
        endline = st.session_state['endline']

    # ---- Cálculo ----
    if baseline is not None and endline is not None:
        st.divider()
        st.subheader("🚀 Calcular indicadores")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.metric("Respuestas Baseline", len(baseline))
        with col2:
            st.metric("Respuestas Endline", len(endline))
        with col3:
            st.metric("Cohorte", cohorte)

        if st.button("🎯 Calcular todos los indicadores", type="primary", use_container_width=True):
            with st.spinner("Calculando indicadores..."):
                try:
                    tabla_maestra = calcular_todos_los_indicadores(
                        baseline=baseline,
                        endline=endline,
                        cohorte=cohorte,
                        programa=programa
                    )
                    st.session_state['tabla_maestra'] = tabla_maestra

                    # Guardar lista de orgs reales de esta cohorte para
                    # enriquecer el reporte con datos sociodemográficos.
                    # Preferimos endline (más reciente); si está vacío, usamos baseline.
                    orgs_lista = []
                    col_org = 'Selecciona el nombre de tu organización'
                    for df in [endline, baseline]:
                        if df is not None and col_org in df.columns:
                            orgs_lista = df[col_org].dropna().unique().tolist()
                            if orgs_lista:
                                break
                    st.session_state['orgs_lista'] = orgs_lista

                    st.success(f"✅ {len(tabla_maestra)} indicadores calculados")

                    if guardar_supabase:
                        try:
                            guardar_resultados_supabase(tabla_maestra)
                            st.success("✅ Resultados guardados en Supabase")
                        except Exception as e:
                            st.warning(f"No se pudo guardar en Supabase: {e}")

                except Exception as e:
                    st.error(f"Error en cálculo: {e}")
                    import traceback
                    with st.expander("Detalle del error"):
                        st.code(traceback.format_exc())

    # ---- Resultados ----
    if 'tabla_maestra' in st.session_state:
        st.divider()
        st.subheader("📋 Tabla maestra de resultados")

        tabla = st.session_state['tabla_maestra']

        metricas_clave = tabla[tabla['indicador'].isin([
            'NPS',
            '% participantes con AI Mindset alto',
            '% orgs aumentaron Net AI Adoption',
            '% orgs mejoraron Digital Maturity (total)'
        ])]
        if not metricas_clave.empty:
            cols = st.columns(len(metricas_clave))
            for i, (_, row) in enumerate(metricas_clave.iterrows()):
                with cols[i]:
                    st.metric(
                        label=row['indicador'],
                        value=f"{row['valor']}{row['unidad']}",
                        delta=f"n={row['n']}"
                    )

        st.dataframe(tabla, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            csv = tabla.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Descargar CSV",
                csv,
                f"tabla_maestra_{cohorte}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv",
                use_container_width=True
            )
        with col2:
            st.link_button(
                "📊 Abrir Looker Studio",
                "https://lookerstudio.google.com",
                use_container_width=True,
                help="Configura aquí el dashboard conectado a Supabase"
            )

        # ============================================================
        # SECCIÓN DE VISUALIZACIONES (basadas en el PDF de Indicadores C8)
        # ============================================================
        st.divider()
        st.subheader("📊 Visualizaciones para reporte")
        st.caption(
            "Gráficos sugeridos según el PDF de Indicadores Calculados de Propel. "
            "Listos para incluir en reportes a donantes."
        )

        from visualizaciones import (
            cards_sociodemografico, card_nps, donut_eficiencia,
            bar_eficiencia_proyectada, pie_ai_adoption, stacked_net_ai_adoption,
            pie_uso_google_ai, bar_ai_mindset, bars_tool_learning,
            bars_tool_learning_pct, stacked_digital_maturity,
            pie_community_building, donut_confianza,
        )
        import ast

        # Helpers para extraer datos de la tabla maestra
        def get_val(nombre_indicador, default=None):
            r = tabla[tabla['indicador'] == nombre_indicador]
            return r.iloc[0]['valor'] if not r.empty else default

        def get_n(nombre_indicador, default=0):
            r = tabla[tabla['indicador'] == nombre_indicador]
            return r.iloc[0]['n'] if not r.empty else default

        def get_detalle(nombre_indicador, default=''):
            r = tabla[tabla['indicador'] == nombre_indicador]
            return r.iloc[0]['detalle'] if not r.empty else default

        def parse_dist(detalle):
            """Parsea un detalle en formato dict-string o 'k:v|k:v' a dict."""
            if not detalle: return {}
            s = str(detalle).strip()
            # Formato: {'MEJORÓ': 7, 'NO MEJORÓ': 14}
            if s.startswith('{'):
                try:
                    return ast.literal_eval(s)
                except (ValueError, SyntaxError):
                    return {}
            # Formato: clave:valor|clave:valor
            d = {}
            for part in s.split('|'):
                if ':' in part:
                    k, v = part.rsplit(':', 1)
                    try:
                        d[k.strip()] = int(v.strip())
                    except ValueError:
                        try:
                            d[k.strip()] = float(v.strip())
                        except ValueError:
                            d[k.strip()] = v.strip()
            return d

        # === 1. Sociodemográfico ===
        st.markdown("#### 1. Sociodemográfico")
        n_part = int(get_n('NPS', 0))
        n_orgs = int(get_n('% orgs aumentaron Net AI Adoption', 0))
        cards_sociodemografico(n_part, n_orgs)

        st.markdown("")

        # === 2. NPS y Confianza ===
        col_a, col_b = st.columns(2)
        with col_a:
            nps_val = get_val('NPS')
            if nps_val is not None:
                st.plotly_chart(card_nps(nps_val, get_n('NPS')),
                                use_container_width=True)
        with col_b:
            conf_val = get_val('% participantes mayor confianza tecnología')
            if conf_val is not None:
                st.plotly_chart(
                    donut_confianza(conf_val, get_n('% participantes mayor confianza tecnología')),
                    use_container_width=True
                )

        # === 3. Eficiencia ===
        st.markdown("#### 3. Eficiencia")
        col_c, col_d = st.columns(2)
        with col_c:
            pct_mejor = get_val('% participantes mejoraron eficiencia')
            prom_calc = get_val('Promedio horas ahorradas/semana (calculado pre-post)')
            n_horas = int(get_n('% participantes mejoraron eficiencia'))
            n_mejoraron = int(round((pct_mejor or 0) / 100 * n_horas)) if n_horas else 0
            if pct_mejor is not None:
                st.plotly_chart(
                    donut_eficiencia(pct_mejor, n_mejoraron, n_horas, prom_calc or 0),
                    use_container_width=True
                )
        with col_d:
            prom_proy = get_val('Promedio horas ahorradas/semana (proyección endline)')
            det_proy = parse_dist(get_detalle('Promedio horas ahorradas/semana (proyección endline)'))
            n_1_2 = det_proy.get('1-2h', 0)
            n_3_4 = det_proy.get('3-4h', 0)
            n_5_plus = det_proy.get('5+h', 0)
            if (n_1_2 + n_3_4 + n_5_plus) > 0:
                fig = bar_eficiencia_proyectada(n_1_2, n_3_4, n_5_plus, prom_proy or 0)
                if fig: st.plotly_chart(fig, use_container_width=True)

        # === 4. AI Adoption Level ===
        st.markdown("#### 4. AI Adoption Level (percibido al cierre)")
        ai_levels = {}
        for nivel in ['Estratégico', 'Integrado', 'Activo', 'Explorando', 'Nada']:
            v = get_val(f'AI Adoption Level - {nivel}')
            n_lvl = get_n(f'AI Adoption Level - {nivel}')
            if v is not None and n_lvl:
                ai_levels[nivel] = int(round(v / 100 * n_lvl))
        if ai_levels:
            st.plotly_chart(pie_ai_adoption(ai_levels), use_container_width=True)
        else:
            st.info("AI Adoption Level no disponible para esta cohorte.")

        # === 5. Net AI Adoption (cambio) ===
        st.markdown("#### 5. Net AI Adoption · Cambio organización")
        estados_ai = parse_dist(get_detalle('% orgs aumentaron Net AI Adoption'))
        if estados_ai:
            fig = stacked_net_ai_adoption(
                estados_ai.get('MEJORÓ', 0),
                estados_ai.get('MANTUVO MÁXIMO', 0),
                estados_ai.get('BAJÓ', 0),
                estados_ai.get('NO MEJORÓ', 0),
            )
            if fig: st.plotly_chart(fig, use_container_width=True)

        # === 6. Uso Google AI ===
        st.markdown("#### 6. Uso de herramientas Google AI")
        google_dist = parse_dist(get_detalle('% participantes uso diario Google AI'))
        if google_dist and not all(isinstance(v, str) for v in google_dist.values()):
            st.plotly_chart(pie_uso_google_ai(google_dist), use_container_width=True)
        else:
            v_diario = get_val('% participantes uso diario Google AI')
            if v_diario is not None:
                st.metric('% uso diario Google AI', f'{v_diario}%',
                          delta=f'n={get_n("% participantes uso diario Google AI")}')

        # === 7. AI Mindset Index ===
        st.markdown("#### 7. AI Mindset Index")
        mindset_dist = parse_dist(get_detalle('% participantes con AI Mindset alto'))
        # Filtrar a solo claves numéricas
        mindset_numeric = {}
        for k, v in mindset_dist.items():
            try:
                mindset_numeric[float(k)] = int(v)
            except (ValueError, TypeError):
                continue
        if mindset_numeric:
            st.plotly_chart(bar_ai_mindset(mindset_numeric), use_container_width=True)
        else:
            v_alto = get_val('% participantes con AI Mindset alto')
            if v_alto is not None:
                st.metric('% AI Mindset alto', f'{v_alto}%',
                          delta=f'n={get_n("% participantes con AI Mindset alto")}')

        # === 8. Tool Learning ===
        st.markdown("#### 8. Tool Learning · Aprendizaje por área")
        prom_areas = {}
        pct_areas = {}
        for area in ['Marketing', 'Impacto', 'Eficiencia', 'Fundraising']:
            p = get_val(f'Tool Learning {area} - promedio')
            pa = get_val(f'Tool Learning {area} - % aprendizaje sig.')
            if p is not None: prom_areas[area] = p
            if pa is not None: pct_areas[area] = pa
        col_e, col_f = st.columns(2)
        with col_e:
            if prom_areas:
                st.plotly_chart(bars_tool_learning(prom_areas, pct_areas),
                                use_container_width=True)
        with col_f:
            if pct_areas:
                st.plotly_chart(bars_tool_learning_pct(pct_areas),
                                use_container_width=True)

        # === 9. Digital Maturity por dimensión ===
        st.markdown("#### 9. Digital Maturity · Cambio por dimensión")
        dim_data = {}
        for d in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']:
            est = parse_dist(get_detalle(f'% orgs mejoraron DM dimensión {d.upper()}'))
            if est:
                dim_data[d] = est
        if dim_data:
            fig = stacked_digital_maturity(dim_data)
            if fig: st.plotly_chart(fig, use_container_width=True)

        # === 10. Community Building ===
        st.markdown("#### 10. Community Building")
        v_contacto = get_val('% participantes establecieron contacto útil')
        if v_contacto is not None:
            n_c = int(get_n('% participantes establecieron contacto útil'))
            n_si = int(round(v_contacto / 100 * n_c))
            n_no = n_c - n_si
            simple_dist = {
                'Sí, estableció contacto': n_si,
                'No estableció': n_no,
            }
            st.plotly_chart(pie_community_building(simple_dist), use_container_width=True)

        st.caption("ℹ️ Los gráficos usan los datos de la tabla maestra arriba. "
                   "Si recalculas con otros datos, los gráficos se actualizan automáticamente.")

# ============================================================
# Pestaña 3 — Generar reporte con IA (Fase 3)
# ============================================================
with tab_reporte:
    st.subheader("🤖 Generar borrador de reporte con IA")
    st.caption(
        "Esta pestaña usa OpenAI para interpretar los indicadores calculados y "
        "genera un borrador editable de reporte en español, listo para revisar "
        "y mandar a donantes."
    )

    if 'tabla_maestra' not in st.session_state:
        st.info(
            "👈 Primero calcula los indicadores en la pestaña **🎯 Calcular indicadores**. "
            "Una vez que tengas la tabla maestra, vuelve acá para generar el reporte."
        )
    else:
        from config import OPENAI_API_KEY, GOOGLE_SERVICE_ACCOUNT_JSON

        # Estado de credenciales
        col_status1, col_status2 = st.columns(2)
        with col_status1:
            if OPENAI_API_KEY:
                st.success("✅ OpenAI configurado")
            else:
                st.error("❌ OpenAI no configurado — agrega `OPENAI_API_KEY` a secrets")
        with col_status2:
            if GOOGLE_SERVICE_ACCOUNT_JSON:
                st.success("✅ Google Docs configurado")
            else:
                st.warning(
                    "⚠️ Google Docs no configurado — podrás descargar Word/Markdown",
                    icon="⚠️"
                )

        st.divider()

        tabla_actual = st.session_state['tabla_maestra']
        cohorte_actual = tabla_actual['cohorte'].iloc[0] if not tabla_actual.empty else cohorte
        programa_actual = tabla_actual['programa'].iloc[0] if not tabla_actual.empty else 'Fellowship'

        st.markdown(f"**Cohorte cargada:** {cohorte_actual} · "
                    f"**Programa:** {programa_actual} · "
                    f"**Indicadores:** {len(tabla_actual)}")

        # Botón generar
        col_gen, _ = st.columns([1, 2])
        with col_gen:
            generar = st.button(
                "✨ Generar borrador",
                type="primary",
                use_container_width=True,
                disabled=not OPENAI_API_KEY,
            )

        if generar:
            from reportes import (
                generar_todos_los_insights, generar_resumen_ejecutivo,
                ensamblar_reporte
            )

            progress_bar = st.progress(0, text="Generando insights...")
            status_text = st.empty()

            def update_progress(completados, total, indicador):
                progress_bar.progress(
                    completados / total,
                    text=f"Generando insights... {completados}/{total} — último: {indicador[:50]}"
                )

            try:
                insights, errores = generar_todos_los_insights(
                    tabla_actual, cohorte_actual, programa_actual,
                    progress_callback=update_progress
                )

                progress_bar.progress(1.0, text="Generando resumen ejecutivo...")
                resumen = generar_resumen_ejecutivo(
                    tabla_actual, cohorte_actual, programa_actual
                )

                reporte = ensamblar_reporte(
                    tabla_actual, insights, resumen,
                    cohorte_actual, programa_actual
                )
                st.session_state['reporte_generado'] = reporte
                st.session_state['reporte_errores'] = errores
                progress_bar.empty()
                status_text.empty()
                st.success(f"✅ Reporte generado · {len(insights)} insights")
                if errores:
                    st.warning(f"⚠️ {len(errores)} indicadores fallaron en la generación")
                    with st.expander("Ver errores"):
                        for ind, err in errores.items():
                            st.code(f"{ind}\n{err}")
            except Exception as e:
                progress_bar.empty()
                st.error(f"Error generando reporte: {e}")

        # Mostrar reporte generado
        if 'reporte_generado' in st.session_state:
            reporte = st.session_state['reporte_generado']
            st.divider()

            # Resumen ejecutivo (editable)
            st.markdown("### 📄 Resumen ejecutivo")
            resumen_editado = st.text_area(
                "Edita el resumen si quieres",
                value=reporte['resumen_ejecutivo'],
                height=200,
                label_visibility='collapsed',
            )
            reporte['resumen_ejecutivo'] = resumen_editado

            # Insights por sección (con previsualización)
            st.markdown("### 📊 Insights por indicador")
            for seccion in reporte['secciones']:
                with st.expander(f"**{seccion['titulo']}** "
                                 f"({len([c for c in seccion['contenido'] if c['tipo']=='indicador'])} indicadores)"):
                    for item in seccion['contenido']:
                        if item['tipo'] == 'indicador':
                            st.markdown(f"**{item['nombre']}** · "
                                        f"{item['valor']}{item['unidad']} (n={item['n']})")
                            insight_editado = st.text_area(
                                f"Insight para {item['nombre']}",
                                value=item['insight'],
                                key=f"insight_{item['nombre']}",
                                height=100,
                                label_visibility='collapsed',
                            )
                            item['insight'] = insight_editado
                            st.markdown("---")
                        elif item['tipo'] == 'metadata':
                            for k, v in item['datos'].items():
                                st.markdown(f"- **{k}:** {v}")

            # ============================================================
            # CAPA 2: EDICIÓN DE CONTENIDO DEL REPORTE VISUAL
            # ============================================================
            st.divider()
            st.markdown("### 🎨 Personalizar contenido del reporte visual")
            st.caption(
                "Edita los textos del reporte HTML que se mandará al donante. "
                "La estructura visual (logo, colores, layout) está fija como plantilla "
                "institucional. Aquí editas solo el contenido que cambia entre cohortes."
            )

            from reporte_visual import obtener_contenido_default

            # Inicializar contenido del reporte en session_state
            if 'reporte_contenido' not in st.session_state:
                st.session_state['reporte_contenido'] = obtener_contenido_default()

            cont = st.session_state['reporte_contenido']

            # ---- Header ----
            with st.expander("✏️ Header — Tagline del reporte", expanded=False):
                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    cont['tagline_pre'] = st.text_input(
                        "Texto previo (color blanco)",
                        value=cont.get('tagline_pre', 'Accelerating impact with'),
                    )
                with col_h2:
                    cont['tagline_post'] = st.text_input(
                        "Texto destacado (color amarillo)",
                        value=cont.get('tagline_post', 'the power of AI.'),
                    )

            # ---- Lead inicial ----
            with st.expander("✏️ Texto introductorio (lead)", expanded=False):
                cont['lead_inicial'] = st.text_area(
                    "Lead inicial (puedes usar {n_part} para insertar el número de participantes)",
                    value=cont.get('lead_inicial', ''),
                    height=100,
                )
                cont['cohort_glance_lead'] = st.text_area(
                    "Subtítulo de 'Cohort X at a glance' "
                    "(usa {num_causas}, {num_paises}, {num_orgs})",
                    value=cont.get('cohort_glance_lead', ''),
                    height=80,
                )

            # ---- What we accomplished together ----
            with st.expander("✏️ 'What we accomplished together' (sección de logros)", expanded=False):
                cont['accomplish_titulo'] = st.text_input(
                    "Título de la sección",
                    value=cont.get('accomplish_titulo', ''),
                )
                cont['accomplish_intro'] = st.text_area(
                    "Texto introductorio",
                    value=cont.get('accomplish_intro', ''),
                    height=80,
                )
                cont['accomplish_outro'] = st.text_area(
                    "Texto de cierre",
                    value=cont.get('accomplish_outro', ''),
                    height=80,
                )

                # Uploader de imagen de cohorte
                st.markdown("**📷 Imagen de cohorte** (foto grupal o representativa)")
                if cont.get('accomplish_imagen_base64'):
                    col_ai1, col_ai2 = st.columns([3, 1])
                    with col_ai1:
                        st.image(cont['accomplish_imagen_base64'], width=240)
                    with col_ai2:
                        if st.button("🗑️ Quitar",
                                      key='rm_accomplish_img',
                                      use_container_width=True):
                            cont['accomplish_imagen_base64'] = None
                            st.rerun()
                else:
                    uploaded_acc = st.file_uploader(
                        "Subir imagen (JPG/PNG)",
                        type=['png', 'jpg', 'jpeg'],
                        key='accomplish_img',
                        label_visibility='collapsed',
                    )
                    if uploaded_acc is not None:
                        from reporte_visual import imagen_a_data_uri
                        file_bytes = uploaded_acc.read()
                        cont['accomplish_imagen_base64'] = imagen_a_data_uri(file_bytes)
                        st.rerun()

            # ---- Closing bar (con NPS, ratings) ----
            with st.expander("✏️ Barra de cierre (con NPS y ratings)", expanded=False):
                cont['closing_text'] = st.text_area(
                    "Texto descriptivo (usa {programa})",
                    value=cont.get('closing_text', ''),
                    height=80,
                )
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    cont['closing_session_rating'] = st.text_input(
                        "Average session rating",
                        value=cont.get('closing_session_rating', '4.7'),
                    )
                with col_c2:
                    cont['closing_live_hours'] = st.text_input(
                        "Live sessions delivered",
                        value=cont.get('closing_live_hours', '+21h'),
                    )

            # ---- Heroes destacados ----
            with st.expander("✏️ Meet the heroes — 3 organizaciones destacadas", expanded=False):
                st.caption(
                    "Edita los datos de los 3 héroes. La org puede ser cualquier "
                    "texto (no necesariamente debe estar en la lista de orgs)."
                )

                # Asegurar que tenemos 3 heroes
                while len(cont.get('heroes', [])) < 3:
                    cont.setdefault('heroes', []).append({
                        'nombre': '', 'descripcion': '', 'plan_digital': '',
                        'progreso': '', 'quote': '', 'autor': '',
                    })

                tabs_h = st.tabs([f"Hero {i+1}" for i in range(3)])
                for i, tab in enumerate(tabs_h):
                    with tab:
                        h = cont['heroes'][i]
                        h['nombre'] = st.text_input(
                            "Nombre de la organización",
                            value=h.get('nombre', ''),
                            key=f'hero_nombre_{i}',
                        )
                        h['descripcion'] = st.text_area(
                            "Descripción de la organización",
                            value=h.get('descripcion', ''),
                            height=60,
                            key=f'hero_desc_{i}',
                        )
                        h['plan_digital'] = st.text_area(
                            "Plan digital / lo que están haciendo",
                            value=h.get('plan_digital', ''),
                            height=80,
                            key=f'hero_plan_{i}',
                        )
                        h['progreso'] = st.text_area(
                            "Progreso (lo que han logrado)",
                            value=h.get('progreso', ''),
                            height=80,
                            key=f'hero_prog_{i}',
                        )
                        h['quote'] = st.text_area(
                            "Quote / testimonio",
                            value=h.get('quote', ''),
                            height=80,
                            key=f'hero_quote_{i}',
                        )
                        h['autor'] = st.text_input(
                            "Autor del quote (Nombre, País)",
                            value=h.get('autor', ''),
                            key=f'hero_autor_{i}',
                        )

                        # Uploader de imagen del hero
                        st.markdown("**📷 Foto del hero**")
                        if h.get('imagen_base64'):
                            col_img1, col_img2 = st.columns([3, 1])
                            with col_img1:
                                st.image(h['imagen_base64'], width=200)
                            with col_img2:
                                if st.button("🗑️ Quitar",
                                              key=f'rm_hero_img_{i}',
                                              use_container_width=True):
                                    h['imagen_base64'] = None
                                    st.rerun()
                        else:
                            uploaded_img = st.file_uploader(
                                "Subir foto (JPG/PNG)",
                                type=['png', 'jpg', 'jpeg'],
                                key=f'hero_img_{i}',
                                label_visibility='collapsed',
                            )
                            if uploaded_img is not None:
                                from reporte_visual import imagen_a_data_uri
                                file_bytes = uploaded_img.read()
                                h['imagen_base64'] = imagen_a_data_uri(file_bytes)
                                st.rerun()

            # ---- Footer ----
            with st.expander("✏️ Footer del reporte", expanded=False):
                cont['footer_quote'] = st.text_input(
                    "Quote del footer (color destacado)",
                    value=cont.get('footer_quote', ''),
                )
                cont['footer_subtext'] = st.text_input(
                    "Subtexto del footer (color blanco)",
                    value=cont.get('footer_subtext', ''),
                )

            # Botón para resetear a defaults
            if st.button("🔄 Restaurar valores por defecto", help="Vuelve al contenido original"):
                st.session_state['reporte_contenido'] = obtener_contenido_default()
                st.rerun()

            # Guardar el contenido editado en session_state
            st.session_state['reporte_contenido'] = cont

            # Botones de descarga / exportación
            st.divider()
            st.markdown("### ⬇️ Exportar reporte")
            st.caption(
                "Dos opciones: **HTML visual** (estilo plantilla institucional, "
                "para mandar al donante) o **Google Docs** (editable colaborativamente). "
                "Si necesitas PDF, exporta desde Google Docs (Archivo → Descargar → PDF)."
            )

            from reporte_visual import generar_html_reporte
            import tempfile, os

            col_html, col_gdoc = st.columns(2)

            with col_html:
                html_visual = generar_html_reporte(
                    tabla_actual, cohorte=cohorte_actual, programa=programa_actual,
                    contenido=st.session_state['reporte_contenido'],
                )
                st.download_button(
                    "🌐 Descargar HTML visual",
                    html_visual.encode('utf-8'),
                    f"propel_{cohorte_actual}_reporte_{datetime.now().strftime('%Y%m%d')}.html",
                    "text/html",
                    use_container_width=True,
                    type="primary",
                    help="HTML auto-contenido con gráficos interactivos (mapa + pie chart). "
                         "Se abre en cualquier navegador."
                )

            with col_gdoc:
                if GOOGLE_SERVICE_ACCOUNT_JSON:
                    if st.button("📑 Crear Google Doc editable",
                                  use_container_width=True, type="primary"):
                        from google_docs_client import create_google_doc
                        try:
                            with st.spinner("Creando Google Doc (esto puede "
                                             "tardar 30-60 segundos)..."):
                                resultado = create_google_doc(
                                    reporte,
                                    tabla_maestra=tabla_actual,
                                    programa=programa_actual,
                                    orgs_lista=st.session_state.get('orgs_lista'),
                                )
                            st.success("✅ Google Doc creado y compartido públicamente "
                                       "(cualquiera con el link puede editar)")
                            st.link_button(
                                "Abrir Google Doc",
                                resultado['url'],
                                use_container_width=True,
                            )
                        except Exception as e:
                            st.error(f"Error creando Google Doc: {e}")
                else:
                    st.button(
                        "📑 Crear Google Doc editable",
                        use_container_width=True,
                        disabled=True,
                        help="Requiere configurar GOOGLE_SERVICE_ACCOUNT_JSON en "
                             "Streamlit secrets. Mientras tanto, descarga el HTML."
                    )

            # Opciones avanzadas (Word/Markdown) en un expander oculto por defecto
            with st.expander("Opciones avanzadas (Word, Markdown)"):
                st.caption(
                    "Estos formatos son texto puro sin gráficos. Útiles si quieres "
                    "trabajar el contenido fuera del portal antes de pasarlo a HTML/Docs."
                )
                from reportes import reporte_a_markdown, reporte_a_docx
                col_md, col_docx = st.columns(2)
                with col_md:
                    md_content = reporte_a_markdown(reporte)
                    st.download_button(
                        "📝 Markdown",
                        md_content.encode('utf-8'),
                        f"reporte_{cohorte_actual}_{datetime.now().strftime('%Y%m%d')}.md",
                        "text/markdown",
                        use_container_width=True,
                    )
                with col_docx:
                    tmp_path = os.path.join(tempfile.gettempdir(),
                                             f"reporte_{cohorte_actual}.docx")
                    reporte_a_docx(reporte, tmp_path)
                    with open(tmp_path, 'rb') as f:
                        st.download_button(
                            "📄 Word",
                            f.read(),
                            f"reporte_{cohorte_actual}_{datetime.now().strftime('%Y%m%d')}.docx",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )

# ============================================================
# Footer
# ============================================================
st.divider()
with st.expander("ℹ️ Sobre esta herramienta"):
    st.markdown("""
    Esta herramienta automatiza el cálculo de indicadores de M&E para los programas de Propel
    siguiendo las fórmulas definidas en la *Guía de cálculo de indicadores* (versión ToC + Google Grant).

    **Indicadores cubiertos:**
    - NPS (Net Promoter Score)
    - Horas ahorradas / semana (comparativo pre-post participante)
    - Net AI Adoption Score (comparativo pre-post organización + nivel Avanzado al cierre)
    - Digital Maturity Index (total + 6 dimensiones, comparativo pre-post organización)
    - AI Mindset Index
    - Uso diario de Google AI tools
    - Tool Learning (4 áreas: Marketing, Impacto, Eficiencia, Fundraising)
    - Confianza en herramientas digitales
    - Adopción de nuevas herramientas
    - AI Adoption Level percibido (5 niveles)
    - Establecimiento de contactos útiles

    **Validación:** los resultados fueron validados contra el cálculo manual de la Cohorte 8 (Fellowship).
    """)

# Footer institucional al pie de página
st.markdown("""
<div class="propel-footer">
    <strong>Sistema integrado de Monitoreo y Evaluación · Propel</strong><br>
    Beca SER ANDI · Grupo 9 · 2026<br>
    <span style="font-size: 11px;">Fase 1 (n8n) · Fase 2 (Streamlit + Supabase) · Fase 3 (OpenAI + Google Docs)</span>
</div>
""", unsafe_allow_html=True)
