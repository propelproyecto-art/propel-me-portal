"""
pareo.py — Pareo robusto baseline ↔ endline para los datos de Propel.

Estrategia en cascada (de más confiable a menos):
  1. Email exacto (cuando exista en ambos lados)
  2. Nombre normalizado exacto (sin tildes, sin mayúsculas, sin espacios extras)
  3. Nombre similar (≥75%) + MISMA organización
  4. Nombre similar (≥85%) sin requerir misma org

Se usa cuando los participantes escriben su nombre a mano en cada Typeform
y este nombre NO coincide exactamente entre baseline y endline.
"""
import pandas as pd
import unicodedata
from difflib import SequenceMatcher


def normalizar_texto(texto):
    """Normaliza un texto para comparación: minúsculas, sin tildes, sin espacios extras."""
    if pd.isna(texto):
        return ''
    s = str(texto).strip().lower()
    # Quitar tildes y caracteres especiales
    s = unicodedata.normalize('NFKD', s).encode('ascii', errors='ignore').decode('ascii')
    # Colapsar espacios múltiples
    s = ' '.join(s.split())
    return s


def calcular_similitud(a, b):
    """Devuelve similitud entre 0 y 1. 1.0 = idéntico, 0.0 = distinto."""
    return SequenceMatcher(None, a, b).ratio()


def parear_baseline_endline(
    baseline_df,
    endline_df,
    col_nombre_b='Por favor, ingresa tu nombre completo',
    col_nombre_e='Escribe tu nombre completo',
    col_org_b='Selecciona el nombre de tu organización',
    col_org_e='Selecciona el nombre de tu organización',
    col_email_b=None,
    col_email_e='Email',
    umbral_con_org=0.75,
    umbral_sin_org=0.85,
):
    """
    Parea cada fila de baseline con su correspondiente en endline.
    
    Retorna un DataFrame con columnas:
      - idx_baseline: índice de la fila en baseline_df
      - idx_endline:  índice de la fila en endline_df
      - metodo:       cómo se hizo el pareo (email/nombre_exacto/similar_org/similar_sin_org)
      - confianza:    0.0 a 1.0
      - nombre_baseline: nombre original tal como apareció en baseline
      - nombre_endline:  nombre original tal como apareció en endline
    
    Reglas de seguridad:
      - Cada fila de endline solo se parea UNA vez.
      - Si hay duplicados en baseline, todos pueden parearse (raro pero posible).
      - El método se anota para que el equipo pueda revisar pareos dudosos.
    """
    pareos = []
    endline_usados = set()
    
    # Copias normalizadas para comparación
    b = baseline_df.copy()
    e = endline_df.copy()
    b['_nombre_norm'] = b[col_nombre_b].apply(normalizar_texto)
    b['_org_norm'] = b[col_org_b].apply(normalizar_texto)
    e['_nombre_norm'] = e[col_nombre_e].apply(normalizar_texto)
    e['_org_norm'] = e[col_org_e].apply(normalizar_texto)
    
    if col_email_b and col_email_b in b.columns:
        b['_email_norm'] = b[col_email_b].apply(
            lambda x: normalizar_texto(x) if pd.notna(x) else None
        )
    else:
        b['_email_norm'] = None
    
    if col_email_e and col_email_e in e.columns:
        e['_email_norm'] = e[col_email_e].apply(
            lambda x: normalizar_texto(x) if pd.notna(x) else None
        )
    else:
        e['_email_norm'] = None
    
    # ============================================================
    # ESTRATEGIA 1: Email exacto (la más confiable)
    # ============================================================
    for idx_b, row_b in b.iterrows():
        if not row_b['_email_norm']:
            continue
        for idx_e, row_e in e.iterrows():
            if idx_e in endline_usados:
                continue
            if row_e['_email_norm'] and row_b['_email_norm'] == row_e['_email_norm']:
                pareos.append({
                    'idx_baseline': idx_b,
                    'idx_endline': idx_e,
                    'metodo': '1-email_exacto',
                    'confianza': 1.0,
                    'nombre_baseline': row_b[col_nombre_b],
                    'nombre_endline': row_e[col_nombre_e],
                })
                endline_usados.add(idx_e)
                break
    
    pareados_b = {p['idx_baseline'] for p in pareos}
    
    # ============================================================
    # ESTRATEGIA 2: Nombre normalizado exacto
    # ============================================================
    for idx_b, row_b in b.iterrows():
        if idx_b in pareados_b:
            continue
        if not row_b['_nombre_norm']:
            continue
        for idx_e, row_e in e.iterrows():
            if idx_e in endline_usados:
                continue
            if row_b['_nombre_norm'] == row_e['_nombre_norm']:
                pareos.append({
                    'idx_baseline': idx_b,
                    'idx_endline': idx_e,
                    'metodo': '2-nombre_exacto',
                    'confianza': 0.95,
                    'nombre_baseline': row_b[col_nombre_b],
                    'nombre_endline': row_e[col_nombre_e],
                })
                endline_usados.add(idx_e)
                pareados_b.add(idx_b)
                break
    
    # ============================================================
    # ESTRATEGIA 3: Nombre similar + MISMA organización
    # ============================================================
    for idx_b, row_b in b.iterrows():
        if idx_b in pareados_b:
            continue
        if not row_b['_nombre_norm']:
            continue
        mejor_match = None
        for idx_e, row_e in e.iterrows():
            if idx_e in endline_usados:
                continue
            if row_b['_org_norm'] != row_e['_org_norm']:
                continue
            sim = calcular_similitud(row_b['_nombre_norm'], row_e['_nombre_norm'])
            if sim >= umbral_con_org and (mejor_match is None or sim > mejor_match[1]):
                mejor_match = (idx_e, sim, row_e)
        if mejor_match:
            idx_e, sim, row_e = mejor_match
            pareos.append({
                'idx_baseline': idx_b,
                'idx_endline': idx_e,
                'metodo': '3-similar_misma_org',
                'confianza': round(sim, 2),
                'nombre_baseline': row_b[col_nombre_b],
                'nombre_endline': row_e[col_nombre_e],
            })
            endline_usados.add(idx_e)
            pareados_b.add(idx_b)
    
    # ============================================================
    # ESTRATEGIA 4: Nombre muy similar (sin requerir misma org)
    # ============================================================
    for idx_b, row_b in b.iterrows():
        if idx_b in pareados_b:
            continue
        if not row_b['_nombre_norm']:
            continue
        mejor_match = None
        for idx_e, row_e in e.iterrows():
            if idx_e in endline_usados:
                continue
            sim = calcular_similitud(row_b['_nombre_norm'], row_e['_nombre_norm'])
            if sim >= umbral_sin_org and (mejor_match is None or sim > mejor_match[1]):
                mejor_match = (idx_e, sim, row_e)
        if mejor_match:
            idx_e, sim, row_e = mejor_match
            pareos.append({
                'idx_baseline': idx_b,
                'idx_endline': idx_e,
                'metodo': '4-similar_sin_org',
                'confianza': round(sim * 0.9, 2),  # penalizar un poco
                'nombre_baseline': row_b[col_nombre_b],
                'nombre_endline': row_e[col_nombre_e],
            })
            endline_usados.add(idx_e)
            pareados_b.add(idx_b)

    # ============================================================
    # ESTRATEGIA 5: Subset palabra-por-palabra + misma org
    # ============================================================
    # Detecta casos donde una persona escribió su nombre completo en una
    # encuesta y una versión corta en la otra. Ejemplos reales:
    #   "Mariana Milagros Mascaró Varillas de Dentone" ↔ "Mariana Mascaró"
    #   "Enrique Arnaldo Matuschka Aycaguer" ↔ "Enrique Matuschka"
    #   "Wendy Juliana Fajardo Barragán" ↔ "Juliana Fajardo"
    # La similitud por caracteres en estos casos es baja, pero el conjunto
    # de palabras del nombre corto está ÍNTEGRAMENTE contenido en el largo.
    for idx_b, row_b in b.iterrows():
        if idx_b in pareados_b:
            continue
        if not row_b['_nombre_norm']:
            continue
        palabras_b = set(row_b['_nombre_norm'].split())
        if len(palabras_b) < 2:
            continue  # con una sola palabra es demasiado riesgoso
        mejor_match = None
        for idx_e, row_e in e.iterrows():
            if idx_e in endline_usados:
                continue
            if row_b['_org_norm'] != row_e['_org_norm']:
                continue  # exigimos misma org para reducir riesgo
            palabras_e = set(row_e['_nombre_norm'].split())
            if len(palabras_e) < 2:
                continue
            # Una es subset de la otra y comparten al menos 2 palabras
            comunes = palabras_b & palabras_e
            es_subset = palabras_b.issubset(palabras_e) or palabras_e.issubset(palabras_b)
            if es_subset and len(comunes) >= 2:
                # Score: ratio de palabras en común sobre el nombre más largo
                score = len(comunes) / max(len(palabras_b), len(palabras_e))
                if mejor_match is None or score > mejor_match[1]:
                    mejor_match = (idx_e, score, row_e)
        if mejor_match:
            idx_e, score, row_e = mejor_match
            pareos.append({
                'idx_baseline': idx_b,
                'idx_endline': idx_e,
                'metodo': '5-subset_misma_org',
                'confianza': round(score * 0.85, 2),
                'nombre_baseline': row_b[col_nombre_b],
                'nombre_endline': row_e[col_nombre_e],
            })
            endline_usados.add(idx_e)
            pareados_b.add(idx_b)

    return pd.DataFrame(pareos)


def construir_dataset_pareado(baseline_df, endline_df, pareos_df):
    """
    Toma los pareos y construye un único DataFrame con:
      - Datos del baseline (con sufijo _baseline)
      - Datos del endline correspondientes (con sufijo _endline)
    Solo incluye filas que se parearon exitosamente.
    
    Útil para calcular indicadores comparativos pre-post.
    """
    rows = []
    for _, p in pareos_df.iterrows():
        row_b = baseline_df.iloc[p['idx_baseline']].copy()
        row_e = endline_df.iloc[p['idx_endline']].copy()
        # Renombrar columnas para no chocar
        row_b = row_b.add_suffix('_baseline')
        row_e = row_e.add_suffix('_endline')
        combined = pd.concat([row_b, row_e])
        combined['_metodo_pareo'] = p['metodo']
        combined['_confianza_pareo'] = p['confianza']
        rows.append(combined)
    return pd.DataFrame(rows) if rows else pd.DataFrame()
