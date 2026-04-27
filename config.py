"""
Configuración del proyecto Propel M&E.

Las credenciales de Supabase NO están escritas en este archivo. Se leen
de dos posibles lugares (en este orden):

1. Streamlit secrets (cuando la app corre en Streamlit Cloud)
2. Archivo local .streamlit/secrets.toml (cuando corres en tu computadora)

El archivo .streamlit/secrets.toml NUNCA debe subirse a GitHub.
Está incluido en .gitignore para evitarlo accidentalmente.
"""
import streamlit as st


# ============================================================
# Supabase — leer credenciales desde secrets
# ============================================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error(
        "⚠️ Faltan las credenciales de Supabase.\n\n"
        "**Si corres local:** crea el archivo `.streamlit/secrets.toml` "
        "con `SUPABASE_URL` y `SUPABASE_KEY`. Mira el README para más detalle.\n\n"
        "**Si corres en Streamlit Cloud:** configura los secrets en "
        "Settings → Secrets de la app."
    )
    st.stop()


# ============================================================
# Programas y cohortes
# ============================================================
PROGRAMAS = ['Fellowship', 'Impact Accelerator']

# Lista de cohortes que aparecen en el dropdown.
COHORTES_DISPONIBLES = ['C8-prueba', 'C9', 'C10']


# ============================================================
# Mapping columnas Supabase → formato Typeform
# ============================================================
COL_MAPPING_SUPABASE_TO_TYPEFORM = {
    'd1': '*Tu organización promueve el uso de herramientas digitales y la capacitación continua. *¿Qué tan de acuerdo estás?',
    'd2': '¿Qué nivel de digitalización tienen tus procesos?',
    'd3': '¿Cómo se comunica tu organización con sus beneficiarios?',
    'd4': '¿Qué nivel de personalización tienen tus comunicaciones?',
    'd5': '¿Cómo usan los datos en la toma de decisiones?',
    'd6': '¿Cómo usan la inteligencia artificial (IA) en tu organización?',
    'horas_repetitivas': '¿Cuántas horas a la semana dedicas a procesos repetitivos o tareas administrativas que podrían automatizarse?',
    'nps_recomendacion': 'En una escala del 0 al 10, ¿qué tan probable es que recomiendes el Propel Fellowship a otras organizaciones sociales?',
    'mindset_curiosidad': 'El Fellowship fortaleció significativamente mi *curiosidad y disposición* para probar los usos de la Inteligencia Artificial (IA) en el trabajo',
    'mindset_impacto': 'El Fellowship me permitió evidenciar que el uso de IA es *clave* para amplificar el impacto del sector social. ',
    'frecuencia_google_ai': '¿Qué tan a menudo has usado esta(s) *herramientas de Google AI *en las últimas 6 semanas?',
    'aprendizaje_marketing': 'Mejorar mi *marketing digital*',
    'aprendizaje_impacto': 'Medir el *impacto *de mi organización',
    'aprendizaje_eficiencia': 'Ser más *eficiente* en el día a día',
    'aprendizaje_fundraising': 'Optimizar mi *fundraising*',
    'confianza_herramientas': '¿En qué medida consideras que el Fellowship *aumentó tu confianza* para resolver retos o mejorar prácticas usando herramientas digitales?',
    'nueva_herramienta_digital': '¿Gracias al programa empezaste a usar al menos una nueva herramienta digital para hacer tus tareas más fáciles o rápidas? ',
    'nivel_uso_ia_org': 'Al concluir el programa, ¿cómo describirías el *nivel de uso* de IA en tu _organización_?',
    'contacto_util': '¿Gracias al programa estableciste al menos un nuevo *contacto útil *para tu trabajo?',
    'organizacion': 'Selecciona el nombre de tu organización',
}
