"""
llm_client.py — Cliente OpenAI para generar insights de M&E.

Genera insights interpretativos por indicador siguiendo la estructura definida
por Propel (4 componentes: qué muestra, comparación, significado, implicación).
"""
from openai import OpenAI
from config import OPENAI_API_KEY

MODEL = "gpt-4o-mini"  # barato y suficiente para insights de texto

# ============================================================
# CONTEXTO DEL PROGRAMA (sirve como background para el LLM)
# ============================================================
CONTEXTO_PROPEL = """
Propel es una organización latinoamericana sin fines de lucro que fortalece las
capacidades digitales y de inteligencia artificial de organizaciones del sector
social. Sus dos programas principales son:

- Fellowship: programa intensivo de 6 semanas para líderes de ONGs, enfocado en
  fortalecer competencias digitales aplicadas (marketing digital, medición de
  impacto, fundraising, eficiencia operativa).

- Impact Accelerator: programa de 8 meses orientado al desarrollo e
  implementación de soluciones de IA dentro de organizaciones del sector social.

Los reportes de M&E se entregan a donantes institucionales como Google. El tono
debe ser profesional, sobrio, basado en evidencia, sin sobre-atribuciones ni
adjetivos hiperbólicos. La voz es la de un especialista en monitoreo y evaluación
del sector social en Latinoamérica.
""".strip()


# ============================================================
# PROMPT PARA UN INSIGHT INDIVIDUAL
# ============================================================
def _prompt_insight(indicador, valor, unidad, n, detalle, cohorte, programa):
    return f"""Eres especialista en monitoreo y evaluación del sector social en Latinoamérica.
{CONTEXTO_PROPEL}

Tu tarea: generar UN insight interpretativo para el siguiente indicador de la
cohorte "{cohorte}" del programa "{programa}".

INDICADOR:
- Nombre: {indicador}
- Valor: {valor}{unidad}
- N (muestra): {n}
- Detalle adicional: {detalle if detalle else 'no disponible'}

ESTRUCTURA del insight (en máximo 3 oraciones, prosa fluida en español):
1. Qué muestra el dato (descripción objetiva del resultado).
2. Si aplica, cómo se compara entre baseline y endline.
3. Qué significa estratégicamente para Propel y los donantes (so-what).
4. Si corresponde, una implicación o recomendación breve.

REGLAS ESTRICTAS:
- No inventes números, contexto ni atribuciones que no estén en los datos dados.
- No uses adjetivos hiperbólicos (espectacular, increíble, etc.).
- No uses "espectaculares resultados", "logros sin precedentes" ni similares.
- Tono profesional y sobrio, como en reportes a donantes institucionales.
- Máximo 3 oraciones, sin viñetas.
- Devuelve SOLO el texto del insight, sin encabezados ni etiquetas.
"""


# ============================================================
# PROMPT PARA EL RESUMEN EJECUTIVO
# ============================================================
def _prompt_resumen(indicadores_clave, cohorte, programa, n_part, n_orgs):
    bullet_indicadores = '\n'.join(
        f'- {ind["indicador"]}: {ind["valor"]}{ind["unidad"]} (n={ind["n"]})'
        for ind in indicadores_clave
    )
    return f"""Eres especialista en monitoreo y evaluación del sector social en Latinoamérica.
{CONTEXTO_PROPEL}

Tu tarea: redactar un RESUMEN EJECUTIVO de 2 párrafos para el reporte de la
cohorte "{cohorte}" del programa "{programa}", dirigido a donantes institucionales.

DATOS DE LA COHORTE:
- Participantes: {n_part}
- Organizaciones: {n_orgs}

INDICADORES PRINCIPALES:
{bullet_indicadores}

ESTRUCTURA:
- Párrafo 1: contexto de la cohorte (cuántos participantes, cuántas orgs) y los
  2-3 logros más relevantes en cifras.
- Párrafo 2: lectura estratégica de los resultados (qué significan para la
  misión de Propel y para el sector social) y, si corresponde, una mirada hacia
  el siguiente paso.

REGLAS ESTRICTAS:
- No inventes números ni contexto fuera de los datos dados.
- Tono profesional y sobrio. Sin hipérboles.
- Español neutro, profesional.
- Devuelve SOLO el texto del resumen, dos párrafos separados por línea en blanco.
"""


# ============================================================
# CLIENTE
# ============================================================
def _get_client():
    if not OPENAI_API_KEY:
        raise ValueError(
            "Falta OPENAI_API_KEY en st.secrets. Configúrala en Streamlit Cloud "
            "(Settings → Secrets) o en .streamlit/secrets.toml local."
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def generar_insight(indicador, valor, unidad, n, detalle, cohorte, programa):
    """Genera un insight interpretativo para un indicador específico."""
    client = _get_client()
    prompt = _prompt_insight(indicador, valor, unidad, n, detalle, cohorte, programa)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


def generar_resumen_ejecutivo(indicadores_clave, cohorte, programa, n_part, n_orgs):
    """Genera el resumen ejecutivo del reporte."""
    client = _get_client()
    prompt = _prompt_resumen(indicadores_clave, cohorte, programa, n_part, n_orgs)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()
