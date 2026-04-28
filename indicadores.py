"""
Lógica de cálculo de indicadores M&E para Propel.

Esta es la lógica validada contra Cohorte 8. Cualquier cambio aquí debe
ser re-validado contra el PDF Indicadores_calculados_C8_tablas.pdf.

Referencia: Guía de cálculo de indicadores · Propel · 2025-2026
"""
import pandas as pd
import unicodedata
import re
from pareo import parear_baseline_endline


# ============================================================
# NORMALIZACIÓN Y MAPEOS
# ============================================================

def norm(s):
    """Normaliza un string: sin tildes, lowercase, espacios colapsados."""
    if pd.isna(s):
        return ''
    s = str(s).strip().lower()
    s = unicodedata.normalize('NFKD', s).encode('ascii', errors='ignore').decode('ascii')
    return re.sub(r'\s+', ' ', s)


# Mapeos de respuesta → puntaje (basados en la Guía de Propel)
def map_d1(v):
    """D1 — Cultura digital (Likert 0-3)."""
    if pd.isna(v): return None
    return {'Muy de acuerdo': 3, 'De acuerdo': 2, 'Neutral': 1,
            'En desacuerdo': 0, 'Muy en desacuerdo': 0}.get(v)


def map_d2(v):
    """D2 — Digitalización procesos (1-3). Detección por substring para
    tolerar variaciones de texto entre baseline y endline."""
    if pd.isna(v): return None
    s = str(v).lower()
    if 'pocos procesos' in s: return 1
    if 'mayoria' in s or 'mayoría' in s: return 2
    if 'totalmente digitalizados' in s: return 3
    return None


def map_d3(v):
    """D3 — Canales comunicación (1-3)."""
    if pd.isna(v): return None
    s = str(v).lower()
    if 'pocos canales' in s: return 1
    if 'varios canales' in s: return 2
    if any(x in s for x in ['integracion total', 'integración total',
                             'integracion completa', 'integración completa']):
        return 3
    return None


def map_d4(v):
    """D4 — Personalización (1-3)."""
    if pd.isna(v): return None
    s = str(v).lower()
    if 'iguales para todos' in s: return 1
    if 'personalizamos usando datos' in s: return 2
    if 'dinamicos y automaticos' in s or 'dinámicos y automáticos' in s: return 3
    return None


def map_d5(v):
    """D5 — Análisis de datos (1-3)."""
    if pd.isna(v): return None
    s = str(v).lower()
    if (any(x in s for x in ['excel', 'hojas simples', 'hojas de calculo', 'hojas de cálculo'])
            and ('reactiva' in s or 'sin sistema' in s)):
        return 1
    if ('dashboard' in s or 'crm' in s) and 'decisiones' in s:
        return 2
    if (any(x in s for x in ['predictivo', 'integrados', 'datos guian', 'datos guían'])
            and ('ia' in s or 'estrategia' in s)):
        return 3
    return None


def map_ai(v):
    """D6 / Net AI Adoption Score (0-3)."""
    if pd.isna(v): return None
    s = str(v).lower()
    if 'no usamos ia' in s: return 0
    if 'evaluando' in s: return 0
    if 'tareas simples' in s: return 1
    if 'automatizamos procesos' in s: return 2
    if 'desarrollamos' in s or 'personalizamos herramientas' in s: return 3
    return None


def map_likert5(v):
    """Likert 1-5 para AI Mindset."""
    if pd.isna(v): return None
    return {'Totalmente de acuerdo': 5, 'De acuerdo': 4, 'Neutral': 3,
            'En desacuerdo': 2, 'Totalmente en desacuerdo': 1}.get(v)


# Columnas de Digital Maturity en el formulario
DM_COLS = {
    'd1': '*Tu organización promueve el uso de herramientas digitales y la capacitación continua. *¿Qué tan de acuerdo estás?',
    'd2': '¿Qué nivel de digitalización tienen tus procesos?',
    'd3': '¿Cómo se comunica tu organización con sus beneficiarios?',
    'd4': '¿Qué nivel de personalización tienen tus comunicaciones?',
    'd5': '¿Cómo usan los datos en la toma de decisiones?',
    'd6': '¿Cómo usan la inteligencia artificial (IA) en tu organización?'
}

DM_MAPPERS = {
    'd1': map_d1, 'd2': map_d2, 'd3': map_d3,
    'd4': map_d4, 'd5': map_d5, 'd6': map_ai
}


# ============================================================
# REGLA DE AGREGACIÓN POR ORGANIZACIÓN
# ============================================================

def org_status(grupo, max_val):
    """Aplica la regla de agregación por organización.

    Args:
        grupo: DataFrame con columnas 'baseline' y 'endline' (puntajes
               de cada participante de una org).
        max_val: valor máximo posible del puntaje.

    Returns:
        'MEJORÓ' | 'MANTUVO MÁXIMO' | 'BAJÓ' | 'NO MEJORÓ'
    """
    if (grupo['endline'] > grupo['baseline']).any():
        return 'MEJORÓ'
    if ((grupo['baseline'] == max_val) & (grupo['endline'] == max_val)).any():
        return 'MANTUVO MÁXIMO'
    if (grupo['endline'] < grupo['baseline']).any():
        return 'BAJÓ'
    return 'NO MEJORÓ'


# ============================================================
# CÁLCULO DE INDICADORES
# ============================================================

def calcular_todos_los_indicadores(baseline, endline, cohorte, programa):
    """Calcula todos los indicadores y devuelve la tabla maestra.

    Args:
        baseline: DataFrame con respuestas de baseline
        endline: DataFrame con respuestas de endline (solo completed)
        cohorte: identificador de la cohorte (str)
        programa: 'Fellowship' o 'Impact Accelerator'

    Returns:
        DataFrame con columnas: cohorte, programa, indicador, valor, unidad, n, detalle
    """
    # Filtrar respuestas completas
    if 'Response Type' in endline.columns:
        endline = endline[endline['Response Type'] == 'completed'].copy()
    else:
        endline = endline.copy()

    if 'Response Type' in baseline.columns:
        baseline = baseline[baseline['Response Type'] == 'completed'].copy()
    else:
        baseline = baseline.copy()

    # Resetear índices para que iloc funcione correctamente con los pareos
    baseline = baseline.reset_index(drop=True)
    endline = endline.reset_index(drop=True)

    # Normalizar llaves de unión
    baseline['_pname'] = baseline['Por favor, ingresa tu nombre completo'].apply(norm)
    baseline['_org'] = baseline['Selecciona el nombre de tu organización'].apply(norm)
    endline['_pname'] = endline['Escribe tu nombre completo'].apply(norm)
    endline['_org'] = endline['Selecciona el nombre de tu organización'].apply(norm)

    # ============================================================
    # PAREO ROBUSTO baseline ↔ endline
    # ============================================================
    # En vez de hacer merge por nombre exacto (que falla cuando los participantes
    # escriben su nombre distinto en cada encuesta), usamos un algoritmo en cascada:
    #   1) email exacto cuando exista
    #   2) nombre normalizado exacto
    #   3) nombre similar (≥75%) + misma organización
    #   4) nombre muy similar (≥85%) sin requerir misma org
    pareos_df = parear_baseline_endline(
        baseline, endline,
        col_email_e='Email' if 'Email' in endline.columns else None,
    )

    # Construir mapeo idx_baseline → idx_endline para uso en parear()
    pareo_map = dict(zip(pareos_df['idx_baseline'], pareos_df['idx_endline']))

    # IMPORTANTE: indicadores endline-only se calculan solo sobre personas
    # PAREADAS con baseline. Esto refleja "participantes validados como parte del
    # programa" (no respuestas espontáneas de personas no inscritas).
    # Si una persona solo respondió endline sin baseline, se descarta.
    idx_endline_pareados = list(pareos_df['idx_endline'])
    endline_validado = endline.iloc[idx_endline_pareados].copy() if idx_endline_pareados else endline.copy()

    # Aplicar mapeos de Digital Maturity
    for df in [baseline, endline]:
        for k, col in DM_COLS.items():
            if col in df.columns:
                df[f'_{k}'] = df[col].apply(DM_MAPPERS[k])
        if all(f'_{k}' in df.columns for k in DM_COLS):
            df['_dm_total'] = df[[f'_{k}' for k in DM_COLS]].sum(axis=1, min_count=6)

    # Helpers locales
    resultados = []

    def add(nombre, valor, n, unidad='', detalle=''):
        resultados.append({
            'cohorte': cohorte,
            'programa': programa,
            'indicador': nombre,
            'valor': valor,
            'unidad': unidad,
            'n': n,
            'detalle': detalle
        })

    def parear(b_col, e_col=None):
        """
        Construye un DataFrame con baseline y endline pareados por persona.
        Usa el pareo robusto pre-calculado (no merge por nombre exacto).
        """
        if e_col is None:
            e_col = b_col
        if b_col not in baseline.columns or e_col not in endline.columns:
            return pd.DataFrame(columns=['_pname', '_org', 'baseline', 'endline'])
        rows = []
        for idx_b, idx_e in pareo_map.items():
            row_b = baseline.iloc[idx_b]
            row_e = endline.iloc[idx_e]
            v_b = row_b.get(b_col)
            v_e = row_e.get(e_col)
            if pd.notna(v_b) and pd.notna(v_e):
                rows.append({
                    '_pname': row_b['_pname'],
                    '_org': row_b['_org'],
                    'baseline': v_b,
                    'endline': v_e,
                })
        return pd.DataFrame(rows)

    # ---- 1. NPS ----
    nps_col = 'En una escala del 0 al 10, ¿qué tan probable es que recomiendes el Propel Fellowship a otras organizaciones sociales?'
    if nps_col in endline.columns:
        vals = endline_validado[nps_col].dropna()
        if len(vals):
            n = len(vals)
            promotores = (vals >= 9).sum()
            detractores = (vals <= 6).sum()
            nps = (promotores - detractores) / n * 100
            add('NPS', round(nps, 2), n, '', f'P:{promotores}|D:{detractores}')

    # ---- 2. Horas ahorradas ----
    horas_col = '¿Cuántas horas a la semana dedicas a procesos repetitivos o tareas administrativas que podrían automatizarse?'
    if horas_col in baseline.columns and horas_col in endline.columns:
        horas = parear(horas_col)
        if len(horas):
            horas['delta'] = horas['baseline'] - horas['endline']
            n = len(horas)
            add('Promedio horas ahorradas/semana (calculado pre-post)', round(horas['delta'].mean(), 2), n, ' hrs',
                'baseline - endline')
            n_mej = (horas['delta'] > 0).sum()
            add('% participantes mejoraron eficiencia', round(n_mej / n * 100, 2), n, '%', f'{n_mej}/{n}')

    # ---- 2b. Horas ahorradas PROYECTADAS (pregunta directa endline) ----
    # Esta es la fórmula oficial que Propel usa en sus reportes (replicada de
    # la tabla dinámica de Melissa). Cálculo por organización:
    #   - Para cada org, contar las CATEGORÍAS DISTINTAS de respuesta entre
    #     sus participantes (si dos personas responden lo mismo, cuenta 1;
    #     si responden distinto, cuenta 1 en cada categoría).
    #   - Asignar punto medio a cada categoría (1.5, 3.5, 5).
    #   - Sumar todas las horas y dividir por número de organizaciones únicas.
    proy_col = '¿Cuánto tiempo crees que podrías ahorrar *semanalmente* usando las herramientas y habilidades aprendidas?'
    if proy_col in endline.columns:
        def map_proyeccion(v):
            if pd.isna(v): return None
            s = str(v).lower()
            if 'entre 1 y 2' in s: return 1.5
            if 'entre 3 y 4' in s: return 3.5
            if 'mas de 5' in s or 'más de 5' in s: return 5.0
            return None
        endline['_h_proy'] = endline[proy_col].apply(map_proyeccion)

        suma_horas = 0.0
        n_1_2 = n_3_4 = n_5 = 0
        orgs_con_resp = []
        for org, grupo in endline.groupby('_org'):
            cats_unicas = grupo['_h_proy'].dropna().unique()
            if len(cats_unicas) == 0:
                continue
            orgs_con_resp.append(org)
            for v in cats_unicas:
                suma_horas += float(v)
                if v == 1.5: n_1_2 += 1
                elif v == 3.5: n_3_4 += 1
                elif v == 5.0: n_5 += 1
        n_orgs_proy = len(orgs_con_resp)
        if n_orgs_proy:
            promedio = suma_horas / n_orgs_proy
            add('Promedio horas ahorradas/semana (proyección endline)',
                round(promedio, 2), n_orgs_proy, ' hrs',
                f'1-2h:{n_1_2}|3-4h:{n_3_4}|5+h:{n_5}')

    # ---- 3. Net AI Adoption (pre-post org) ----
    if '_d6' in baseline.columns and '_d6' in endline.columns:
        ai_pareo = parear('_d6')
        if len(ai_pareo):
            orgs_ai = ai_pareo.groupby('_org').apply(lambda g: org_status(g, 3), include_groups=False)
            n = len(orgs_ai)
            n_mej = (orgs_ai == 'MEJORÓ').sum()
            add('% orgs aumentaron Net AI Adoption', round(n_mej / n * 100, 2), n, '%',
                str(orgs_ai.value_counts().to_dict()))

    # ---- 4. Net AI Adoption — % nivel Avanzado al cierre ----
    if '_d6' in endline.columns:
        ai_e = endline[['_org', '_d6']].dropna()
        if len(ai_e):
            orgs_avz = ai_e.groupby('_org')['_d6'].max() == 3
            n = len(orgs_avz)
            add('% orgs nivel Avanzado Net AI Adoption', round(orgs_avz.sum() / n * 100, 2), n, '%')

    # ---- 5. Digital Maturity total ----
    if '_dm_total' in baseline.columns and '_dm_total' in endline.columns:
        dm_pareo = parear('_dm_total')
        if len(dm_pareo):
            orgs_dm = dm_pareo.groupby('_org').apply(lambda g: org_status(g, 18), include_groups=False)
            n = len(orgs_dm)
            n_mej = (orgs_dm == 'MEJORÓ').sum()
            add('% orgs mejoraron Digital Maturity (total)', round(n_mej / n * 100, 2), n, '%',
                str(orgs_dm.value_counts().to_dict()))

    # ---- 6. Digital Maturity por dimensión ----
    for k in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']:
        if f'_{k}' in baseline.columns and f'_{k}' in endline.columns:
            pareo = parear(f'_{k}')
            if len(pareo):
                orgs_d = pareo.groupby('_org').apply(lambda g: org_status(g, 3), include_groups=False)
                n = len(orgs_d)
                n_mej = (orgs_d == 'MEJORÓ').sum()
                add(f'% orgs mejoraron DM dimensión {k.upper()}',
                    round(n_mej / n * 100, 2), n, '%', str(orgs_d.value_counts().to_dict()))

    # ---- 7. AI Mindset Index ----
    q1 = 'El Fellowship fortaleció significativamente mi *curiosidad y disposición* para probar los usos de la Inteligencia Artificial (IA) en el trabajo'
    q2 = 'El Fellowship me permitió evidenciar que el uso de IA es *clave* para amplificar el impacto del sector social. '
    if q1 in endline.columns and q2 in endline.columns:
        endline_validado['_mindset'] = (endline_validado[q1].apply(map_likert5) + endline_validado[q2].apply(map_likert5)) / 2
        vals = endline_validado['_mindset'].dropna()
        if len(vals):
            n = len(vals)
            n_alto = (vals >= 4).sum()
            # Distribución de puntajes para gráfico
            dist = vals.value_counts().sort_index().to_dict()
            detalle = '|'.join(f'{k}:{v}' for k, v in dist.items())
            add('% participantes con AI Mindset alto', round(n_alto / n * 100, 2), n, '%', detalle)

    # ---- 8. Uso diario Google AI ----
    freq_col = '¿Qué tan a menudo has usado esta(s) *herramientas de Google AI *en las últimas 6 semanas?'
    if freq_col in endline.columns:
        vals = endline_validado[freq_col].dropna()
        if len(vals):
            n = len(vals)
            n_d = (vals == 'Cada día').sum()
            # Distribución completa para gráfico
            dist = vals.value_counts().to_dict()
            detalle = '|'.join(f'{k}:{v}' for k, v in dist.items())
            add('% participantes uso diario Google AI', round(n_d / n * 100, 2), n, '%', detalle)

    # ---- 9. Tool Learning (4 áreas) ----
    areas = {
        'Marketing': 'Mejorar mi *marketing digital*',
        'Impacto': 'Medir el *impacto *de mi organización',
        'Eficiencia': 'Ser más *eficiente* en el día a día',
        'Fundraising': 'Optimizar mi *fundraising*'
    }
    for area, col in areas.items():
        if col in endline.columns:
            vals = endline_validado[col].dropna()
            if len(vals):
                n = len(vals)
                avg = vals.mean()
                pct = (vals >= 4).sum() / n * 100
                add(f'Tool Learning {area} - promedio', round(avg, 2), n, '/5')
                add(f'Tool Learning {area} - % aprendizaje sig.', round(pct, 2), n, '%')

    # ---- 10. Confianza en herramientas digitales ----
    conf_col = '¿En qué medida consideras que el Fellowship *aumentó tu confianza* para resolver retos o mejorar prácticas usando herramientas digitales?'
    if conf_col in endline.columns:
        vals = endline_validado[conf_col].dropna()
        if len(vals):
            n = len(vals)
            n_aum = vals.isin(['Aumentó mucho', 'Aumentó un poco']).sum()
            add('% participantes mayor confianza tecnología', round(n_aum / n * 100, 2), n, '%')

    # ---- 11. Nueva herramienta digital ----
    nh_col = '¿Gracias al programa empezaste a usar al menos una nueva herramienta digital para hacer tus tareas más fáciles o rápidas? '
    if nh_col in endline.columns:
        vals = endline_validado[nh_col].dropna()
        if len(vals):
            n = len(vals)
            n_si = (vals == 1).sum()
            add('% participantes adoptó nueva herramienta', round(n_si / n * 100, 2), n, '%')

    # ---- 12. AI Adoption Level percibido (5 niveles) ----
    adopt_col = 'Al concluir el programa, ¿cómo describirías el *nivel de uso* de IA en tu _organización_?'
    if adopt_col in endline.columns:
        vals = endline_validado[adopt_col].dropna()
        if len(vals):
            n = len(vals)

            def clasif(v):
                s = str(v).lower()
                if 'nada en absoluto' in s: return 'Nada'
                if 'explorando' in s: return 'Explorando'
                if 'activo' in s: return 'Activo'
                if 'integrado' in s: return 'Integrado'
                if 'estratégico' in s or 'estrategico' in s: return 'Estratégico'
                return 'Otro'

            dist = vals.apply(clasif).value_counts().to_dict()
            for nivel, cnt in dist.items():
                add(f'AI Adoption Level - {nivel}', round(cnt / n * 100, 2), n, '%')

    # ---- 13. Contactos útiles establecidos ----
    cont_col = '¿Gracias al programa estableciste al menos un nuevo *contacto útil *para tu trabajo?'
    if cont_col in endline.columns:
        vals = endline_validado[cont_col].dropna()
        if len(vals):
            n = len(vals)
            establ = vals.str.contains('Sí', regex=False, na=False).sum()
            add('% participantes establecieron contacto útil', round(establ / n * 100, 2), n, '%')

    return pd.DataFrame(resultados)
