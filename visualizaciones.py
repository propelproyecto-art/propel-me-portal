"""
visualizaciones.py — Gráficos para los indicadores M&E de Propel.

Cada función está diseñada para mostrarse con st.plotly_chart en Streamlit
y replica los gráficos sugeridos en el PDF de Indicadores Calculados de C8.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Paleta de colores institucional Propel
COLORS = {
    'primary': '#2E5C8A',      # azul institucional
    'success': '#52B788',      # verde mejoraron
    'warning': '#F4A261',      # naranja sin cambio
    'danger': '#E76F51',       # rojo bajaron
    'neutral': '#8E9AAF',      # gris
    'accent': '#9B5DE5',       # morado destacado
    'light_green': '#D4EDDA',
    'light_yellow': '#FFF3CD',
    'light_red': '#F8D7DA',
}


# ============================================================
# 1. SOCIODEMOGRAPHICS — Cards con métricas clave
# ============================================================
def cards_sociodemografico(num_participantes, num_orgs, num_orgs_no_oficiales=0):
    """Métricas clave de la cohorte. Para país/causa/alcance se requiere Salesforce."""
    cols = st.columns(4)
    with cols[0]:
        st.metric('Participantes', num_participantes)
    with cols[1]:
        st.metric('Organizaciones', num_orgs)
    with cols[2]:
        st.metric('Causas sociales', '—', help='Pendiente: enriquecer desde Salesforce')
    with cols[3]:
        st.metric('Países', '—', help='Pendiente: enriquecer desde Salesforce')

    if num_orgs_no_oficiales > 0:
        st.caption(
            f'⚠️ {num_orgs_no_oficiales} respuesta(s) corresponden a orgs no '
            f'reconocidas oficialmente (revisar contra Salesforce).'
        )


# ============================================================
# 2. NPS — Card grande con valor
# ============================================================
def card_nps(nps_value, n):
    """NPS con clasificación visual."""
    if nps_value >= 70:
        color = COLORS['success']
        label = 'Excelente'
    elif nps_value >= 30:
        color = COLORS['warning']
        label = 'Bueno'
    elif nps_value >= 0:
        color = COLORS['neutral']
        label = 'Aceptable'
    else:
        color = COLORS['danger']
        label = 'Crítico'

    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=nps_value,
        number={'font': {'size': 48, 'color': '#2C3E50'}},
        domain={'x': [0, 1], 'y': [0, 0.85]},
        title={
            'text': f'<b>NPS · Net Promoter Score</b><br>'
                    f'<span style="font-size:13px;color:#666">n={n} · {label}</span>',
            'font': {'size': 16},
        },
        gauge={
            'axis': {'range': [-100, 100], 'tickwidth': 1, 'tickfont': {'size': 11}},
            'bar': {'color': color, 'thickness': 0.7},
            'steps': [
                {'range': [-100, 0], 'color': COLORS['light_red']},
                {'range': [0, 30], 'color': '#F0F0F0'},
                {'range': [30, 70], 'color': COLORS['light_yellow']},
                {'range': [70, 100], 'color': COLORS['light_green']},
            ],
            'threshold': {
                'line': {'color': COLORS['primary'], 'width': 3},
                'thickness': 0.85,
                'value': nps_value,
            },
        },
    ))
    fig.update_layout(height=380, margin=dict(t=100, b=20, l=40, r=40))
    return fig


# ============================================================
# 3a. Eficiencia calculada — Donut con %
# ============================================================
def donut_eficiencia(pct_mejoraron, n_mejoraron, n_total, promedio_horas):
    """Donut con % de personas que mejoraron eficiencia + card con horas."""
    fig = go.Figure(data=[go.Pie(
        labels=['Mejoraron', 'No mejoraron'],
        values=[n_mejoraron, n_total - n_mejoraron],
        hole=0.65,
        marker=dict(colors=[COLORS['success'], '#E5E5E5']),
        textinfo='none',
        hoverinfo='label+value+percent',
    )])
    fig.add_annotation(
        text=f'<b style="font-size:32px">{pct_mejoraron:.0f}%</b><br>'
             f'<span style="font-size:13px">mejoraron</span>',
        x=0.5, y=0.5, showarrow=False,
    )
    fig.update_layout(
        title=f'<b>Eficiencia calculada (pre-post)</b><br>'
              f'<span style="font-size:0.8em">Promedio: {promedio_horas:.2f} hrs/sem · n={n_total}</span>',
        height=340,
        showlegend=True,
        legend=dict(orientation='h', y=-0.05),
        margin=dict(t=70, b=20, l=20, r=20),
    )
    return fig


# ============================================================
# 3b. Eficiencia proyectada — Distribución por rangos
# ============================================================
def bar_eficiencia_proyectada(n_1_2, n_3_4, n_5_plus, promedio):
    """Distribución de horas que se proyecta ahorrar."""
    total = n_1_2 + n_3_4 + n_5_plus
    if total == 0:
        return None
    pct = [n_1_2/total*100, n_3_4/total*100, n_5_plus/total*100]
    fig = go.Figure(data=[go.Bar(
        x=['Entre 1 y 2 hrs', 'Entre 3 y 4 hrs', 'Más de 5 hrs'],
        y=[n_1_2, n_3_4, n_5_plus],
        text=[f'{n_1_2}<br>{pct[0]:.0f}%', f'{n_3_4}<br>{pct[1]:.0f}%', f'{n_5_plus}<br>{pct[2]:.0f}%'],
        textposition='outside',
        marker=dict(color=[COLORS['warning'], COLORS['primary'], COLORS['success']]),
        hoverinfo='x+y',
    )])
    fig.update_layout(
        title=f'<b>Eficiencia proyectada a futuro</b><br>'
              f'<span style="font-size:0.8em">Promedio: {promedio:.2f} hrs/sem · n={total}</span>',
        yaxis=dict(title='Participantes'),
        height=340,
        margin=dict(t=70, b=40, l=40, r=20),
        showlegend=False,
    )
    return fig


# ============================================================
# 4. AI Adoption Level — Pie chart
# ============================================================
def pie_ai_adoption(dist_dict):
    """Distribución por nivel de adopción IA al cierre."""
    orden = ['Estratégico', 'Integrado', 'Activo', 'Explorando', 'Nada']
    labels = [k for k in orden if k in dist_dict and dist_dict[k] > 0]
    values = [dist_dict[k] for k in labels]
    colores_orden = {
        'Estratégico': COLORS['accent'],
        'Integrado': COLORS['success'],
        'Activo': COLORS['primary'],
        'Explorando': COLORS['warning'],
        'Nada': COLORS['danger'],
    }
    colores = [colores_orden[k] for k in labels]
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values,
        hole=0.4,
        marker=dict(colors=colores),
        textinfo='label+percent',
        textposition='outside',
    )])
    fig.update_layout(
        title='<b>Nivel de adopción IA al cierre</b>',
        height=400,
        showlegend=False,
        margin=dict(t=60, b=20, l=20, r=20),
    )
    return fig


# ============================================================
# 5a. Net AI Adoption — cambio (radial gauge con tres segmentos)
# ============================================================
def stacked_net_ai_adoption(n_mejoraron, n_mantuvo_max, n_bajaron, n_no_mejoro):
    """Stacked horizontal bar con cambio en Net AI Adoption."""
    total = n_mejoraron + n_mantuvo_max + n_bajaron + n_no_mejoro
    if total == 0:
        return None
    fig = go.Figure()
    if n_mejoraron > 0:
        fig.add_trace(go.Bar(
            y=['Net AI Adoption'], x=[n_mejoraron], name=f'Mejoraron ({n_mejoraron})',
            orientation='h', marker=dict(color=COLORS['success']),
            text=f'{n_mejoraron/total*100:.0f}%', textposition='inside',
        ))
    if n_mantuvo_max > 0:
        fig.add_trace(go.Bar(
            y=['Net AI Adoption'], x=[n_mantuvo_max], name=f'Mantuvo máximo ({n_mantuvo_max})',
            orientation='h', marker=dict(color=COLORS['primary']),
            text=f'{n_mantuvo_max/total*100:.0f}%', textposition='inside',
        ))
    if n_no_mejoro > 0:
        fig.add_trace(go.Bar(
            y=['Net AI Adoption'], x=[n_no_mejoro], name=f'No mejoraron ({n_no_mejoro})',
            orientation='h', marker=dict(color=COLORS['neutral']),
            text=f'{n_no_mejoro/total*100:.0f}%', textposition='inside',
        ))
    if n_bajaron > 0:
        fig.add_trace(go.Bar(
            y=['Net AI Adoption'], x=[n_bajaron], name=f'Bajaron ({n_bajaron})',
            orientation='h', marker=dict(color=COLORS['danger']),
            text=f'{n_bajaron/total*100:.0f}%', textposition='inside',
        ))
    fig.update_layout(
        title=f'<b>Cambio en Net AI Adoption (baseline → endline)</b><br>'
              f'<span style="font-size:0.8em">n={total} organizaciones</span>',
        barmode='stack', height=200,
        xaxis=dict(showticklabels=False),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation='h', y=-0.3),
        margin=dict(t=60, b=60, l=20, r=20),
    )
    return fig


# ============================================================
# 6. Uso Google AI — Pie chart
# ============================================================
def pie_uso_google_ai(dist_dict):
    """Frecuencia de uso de herramientas Google AI."""
    orden = ['Cada día', 'Varias veces por semana (2-4 veces)',
             'Una vez por semana o menos', 'No las he usado en las últimas 6 semanas']
    labels_short = ['Cada día', 'Varias por semana', 'Una o menos', 'No he usado']
    valores = []
    final_labels = []
    for orig, short in zip(orden, labels_short):
        v = dist_dict.get(orig, 0)
        if v > 0:
            valores.append(v)
            final_labels.append(short)
    colores = [COLORS['success'], COLORS['primary'], COLORS['warning'], COLORS['danger']][:len(valores)]
    fig = go.Figure(data=[go.Pie(
        labels=final_labels, values=valores,
        hole=0.4,
        marker=dict(colors=colores),
        textinfo='label+percent',
    )])
    fig.update_layout(
        title='<b>Frecuencia de uso · herramientas Google AI</b>',
        height=400,
        margin=dict(t=60, b=20, l=20, r=20),
    )
    return fig


# ============================================================
# 7. AI Mindset Index — Distribución
# ============================================================
def bar_ai_mindset(dist_dict):
    """Distribución de puntajes del AI Mindset Index."""
    items = sorted(dist_dict.items())
    labels = [f'{k}' for k, _ in items]
    valores = [v for _, v in items]
    total = sum(valores)
    pcts = [v/total*100 if total > 0 else 0 for v in valores]
    colores = [
        COLORS['danger'] if k < 3 else
        COLORS['warning'] if k < 4 else
        COLORS['primary'] if k < 4.5 else
        COLORS['success']
        for k, _ in items
    ]
    fig = go.Figure(data=[go.Bar(
        x=labels, y=valores,
        marker=dict(color=colores),
        text=[f'{v}<br>({p:.0f}%)' for v, p in zip(valores, pcts)],
        textposition='outside',
    )])
    fig.update_layout(
        title=f'<b>AI Mindset Index · Distribución</b><br>'
              f'<span style="font-size:0.8em">n={total} participantes</span>',
        xaxis=dict(title='Puntaje (1=bajo, 5=muy alto)'),
        yaxis=dict(title='Participantes'),
        height=380,
        showlegend=False,
        margin=dict(t=70, b=40, l=40, r=20),
    )
    return fig


# ============================================================
# 8. Tool Learning — Horizontal bar chart por área
# ============================================================
def bars_tool_learning(promedios_dict, pct_alto_dict):
    """Promedio (escala 1-5) y % alto por área de aprendizaje."""
    areas = list(promedios_dict.keys())
    promedios = [promedios_dict[a] for a in areas]
    pct_altos = [pct_alto_dict.get(a, 0) for a in areas]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=areas, x=promedios, name='Promedio (1-5)',
        orientation='h',
        marker=dict(color=COLORS['primary']),
        text=[f'{p:.2f}' for p in promedios],
        textposition='outside',
    ))
    fig.update_layout(
        title='<b>Tool Learning · Promedio por área (escala 1-5)</b>',
        xaxis=dict(title='Promedio', range=[0, 5]),
        height=320,
        showlegend=False,
        margin=dict(t=60, b=40, l=20, r=40),
    )
    return fig


def bars_tool_learning_pct(pct_alto_dict):
    """% de aprendizaje significativo (rating ≥4) por área."""
    areas = list(pct_alto_dict.keys())
    pcts = [pct_alto_dict[a] for a in areas]
    fig = go.Figure(data=[go.Bar(
        y=areas, x=pcts,
        orientation='h',
        marker=dict(color=COLORS['success']),
        text=[f'{p:.0f}%' for p in pcts],
        textposition='outside',
    )])
    fig.update_layout(
        title='<b>Tool Learning · % de aprendizaje significativo (≥4)</b>',
        xaxis=dict(title='%', range=[0, 110]),
        height=320,
        showlegend=False,
        margin=dict(t=60, b=40, l=20, r=40),
    )
    return fig


# ============================================================
# 9. Digital Maturity — Stacked bar por dimensión
# ============================================================
def stacked_digital_maturity(dimensiones_dict):
    """Stacked bar por dimensión D1-D6 con mejoraron/sin cambio/bajaron."""
    if not dimensiones_dict:
        return None
    nombres = {
        'd1': 'D1 · Cultura digital',
        'd2': 'D2 · Digitalización',
        'd3': 'D3 · Canales',
        'd4': 'D4 · Personalización',
        'd5': 'D5 · Uso de datos',
        'd6': 'D6 · Adopción IA',
    }
    dims = list(dimensiones_dict.keys())
    labels = [nombres.get(d, d) for d in dims]
    mejoraron = [dimensiones_dict[d].get('MEJORÓ', 0) for d in dims]
    mantuvo = [dimensiones_dict[d].get('MANTUVO MÁXIMO', 0) for d in dims]
    no_mej = [dimensiones_dict[d].get('NO MEJORÓ', 0) for d in dims]
    bajaron = [dimensiones_dict[d].get('BAJÓ', 0) for d in dims]

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Mejoraron', y=labels, x=mejoraron,
                        orientation='h', marker_color=COLORS['success']))
    fig.add_trace(go.Bar(name='Mantuvo máximo', y=labels, x=mantuvo,
                        orientation='h', marker_color=COLORS['primary']))
    fig.add_trace(go.Bar(name='No mejoraron', y=labels, x=no_mej,
                        orientation='h', marker_color=COLORS['neutral']))
    fig.add_trace(go.Bar(name='Bajaron', y=labels, x=bajaron,
                        orientation='h', marker_color=COLORS['danger']))
    fig.update_layout(
        title='<b>Digital Maturity · Cambio por dimensión (baseline → endline)</b>',
        barmode='stack',
        xaxis=dict(title='Organizaciones'),
        height=400,
        legend=dict(orientation='h', y=-0.15),
        margin=dict(t=60, b=80, l=120, r=20),
    )
    return fig


# ============================================================
# 10. Community Building — Pie chart
# ============================================================
def pie_community_building(dist_dict):
    """Tipo de contacto establecido."""
    items = list(dist_dict.items())
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    colores_map = {
        'Sí, y ya hemos colaborado': COLORS['success'],
        'Sí, pero aún no hemos trabajado juntos': COLORS['primary'],
        'No, pero he identificado posibles contactos': COLORS['warning'],
        'No, no he establecido nuevos contactos': COLORS['danger'],
    }
    colores = [colores_map.get(l, COLORS['neutral']) for l in labels]
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values,
        hole=0.4,
        marker=dict(colors=colores),
        textinfo='percent',
    )])
    fig.update_layout(
        title='<b>Community Building · Tipo de contacto</b>',
        height=400,
        margin=dict(t=60, b=20, l=20, r=20),
        legend=dict(orientation='h', y=-0.05),
    )
    return fig


# ============================================================
# 11. Confianza tecnología — Donut con %
# ============================================================
def donut_confianza(pct_aumento, n_total):
    """% que aumentó confianza tecnológica."""
    fig = go.Figure(data=[go.Pie(
        labels=['Aumentó confianza', 'Sin cambio'],
        values=[pct_aumento, 100 - pct_aumento],
        hole=0.65,
        marker=dict(colors=[COLORS['accent'], '#E5E5E5']),
        textinfo='none',
    )])
    fig.add_annotation(
        text=f'<b style="font-size:28px">{pct_aumento:.0f}%</b><br>'
             f'<span style="font-size:12px">↑ confianza</span>',
        x=0.5, y=0.5, showarrow=False,
    )
    fig.update_layout(
        title=f'<b>Confianza tecnológica</b><br>'
              f'<span style="font-size:0.8em">n={n_total}</span>',
        height=300,
        showlegend=False,
        margin=dict(t=70, b=20, l=20, r=20),
    )
    return fig
