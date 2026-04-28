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
    page_title="Propel M&E — Indicadores",
    page_icon="📊",
    layout="wide"
)

# Header
st.title("📊 Propel M&E — Calculadora de indicadores")
st.caption("Fase 2 del sistema automatizado de Monitoreo y Evaluación · Beca SER ANDI · Grupo 9")

# ============================================================
# Sidebar — selección de modo y parámetros
# ============================================================
with st.sidebar:
    st.header("⚙️ Configuración")

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

# ============================================================
# Pestañas principales
# ============================================================
tab_gestion, tab_calculo = st.tabs([
    "🎛️ Gestión de cohorte",
    "🎯 Calcular indicadores",
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
