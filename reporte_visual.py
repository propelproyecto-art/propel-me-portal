"""
reporte_visual.py — Genera el reporte visual estilo Canva.

Dos formatos de salida:
  - HTML con Plotly (interactivo, perfecto visualmente) → para mandar al donante
  - PNGs estáticos de los gráficos → para insertar en Google Docs

NO genera PDF. Si Propel necesita PDF, lo exportan desde Google Docs.

CAPA 2 (contenido editable): los textos del reporte se pueden personalizar a
través del dict `contenido` que se pasa a `generar_html_reporte()`. Si no se
pasa, se usan los defaults definidos en CONTENIDO_DEFAULT.
"""
import io
import json
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from datos_sinteticos import enriquecer_orgs, agregar_metadata, CODIGOS_PAIS


# ============================================================
# COLORES INSTITUCIONALES (Capa 3 — fija, no editable desde el portal)
# ============================================================
COLORES_FELLOWSHIP = {
    'header_bg': '#1d4d4d',
    'accent': '#e76f51',
    'accent_yellow': '#f4d35e',
    'text_dark': '#1a2e35',
    'bg_light': '#f5f5f0',
    'pie_palette': ['#1d4d4d', '#2c5f5d', '#e76f51', '#f4a261',
                    '#d0d0c8', '#a3b8b8', '#7da39f', '#4a8a7e'],
    'map_colorscale': [[0, '#d0d0c8'], [0.5, '#7da39f'], [1, '#1d4d4d']],
}

COLORES_ACCELERATOR = {
    'header_bg': '#3949ab',
    'accent': '#e76f51',
    'accent_yellow': '#f4d35e',
    'text_dark': '#1a2e35',
    'bg_light': '#f5f5f0',
    'pie_palette': ['#3949ab', '#5c6bc0', '#e76f51', '#f4a261',
                    '#9fa8da', '#7986cb', '#3f51b5', '#283593'],
    'map_colorscale': [[0, '#e0e3f5'], [0.5, '#7986cb'], [1, '#283593']],
}


# ============================================================
# CAPA 2 — CONTENIDO POR DEFECTO (editable desde el portal)
# ============================================================
CONTENIDO_DEFAULT = {
    # Header
    'tagline_pre': 'Accelerating impact with',
    'tagline_post': 'the power of AI.',

    # Lead inicial (después del header)
    'lead_inicial': (
        'Your investment equipped {n_part} social leaders across Latin America '
        'with the digital and AI tools to measure results, strengthen their '
        'organizations, and raise more funds.'
    ),

    # Subtítulo de "Cohort X at a glance"
    'cohort_glance_lead': (
        'A diverse cohort working across {num_causas} social causes, '
        'reaching communities at scale.'
    ),

    # Sección "What we accomplished together"
    'accomplish_titulo': 'What we accomplished together:',
    'accomplish_intro': (
        'In just six weeks, Fellows moved from intention to action, launching '
        'digital strategies that are already changing how their organizations operate.'
    ),
    'accomplish_outro': (
        'This shift translates into more time for mission, better decisions, '
        'and stronger organizations.'
    ),
    'accomplish_imagen_base64': None,  # imagen de cohorte (data URI)

    # Closing bar (con NPS, ratings, etc.)
    'closing_text': (
        'Participants describe the {programa} as energizing, practical, '
        'and immediately applicable to their work.'
    ),
    'closing_session_rating': '4.7',
    'closing_live_hours': '+21h',

    # Heroes destacados (3 organizaciones)
    'heroes': [
        {
            'nombre': 'Déficit Cero',
            'descripcion': 'Improves housing access for over 37K across Chile.',
            'plan_digital': ('Their Digital Plan aims to build a system to track the impact '
                             'of 100+ organizations driving housing policy.'),
            'progreso': ('Digital plan framework completed. Piloting digital form to capture '
                         'Housing Policy information.'),
            'quote': ('I came feeling isolated in our mission. But here, despite different '
                      'goals, we found a community. We\'re no longer alone.'),
            'autor': 'Enrique Matuschka, Chile',
            'imagen_base64': None,
        },
        {
            'nombre': 'Sociedad Ornitológica de Córdoba',
            'descripcion': 'Advances bird conservation and eco-tourism, reaching over 3K people in rural areas.',
            'plan_digital': ('Will implement their Digital Plan to raise $20K by 2026 to support '
                             'conservation and 13 cocoa-producing families.'),
            'progreso': ('Digital plan framework completed. Building a donor platform for '
                         'segmented tiers by Q1 2026.'),
            'quote': ('We adopted new practices to optimize processes, improve data '
                      'management, and drive impact.'),
            'autor': 'Arturo Torres, Argentina',
            'imagen_base64': None,
        },
        {
            'nombre': 'SHEnampa',
            'descripcion': 'Closes gender gaps and brings technology to rural women in México.',
            'plan_digital': ('Reaches 7,000 women through workshops and mentorship across Mexico City.'),
            'progreso': ('Launched their digital communications strategy and onboarded '
                         '25 new mentors in the past quarter.'),
            'quote': ('I now see a clear path for digital transformation to close gender '
                      'gaps and bring technology to rural women.'),
            'autor': 'Jimena Silva, México',
            'imagen_base64': None,
        },
    ],

    # Footer
    'footer_quote': 'The {programa} is building a stronger, more resilient social sector —',
    'footer_subtext': 'one leader, one organization, and one digital leap at a time.',
}


def obtener_contenido_default():
    """Devuelve una copia profunda del contenido default (para inicializar editor)."""
    import copy
    return copy.deepcopy(CONTENIDO_DEFAULT)


# ============================================================
# UTILIDADES
# ============================================================
def _get_val(tabla, indicador, default=None):
    if tabla is None: return default
    r = tabla[tabla['indicador'] == indicador]
    return r.iloc[0]['valor'] if not r.empty else default


def _get_n(tabla, indicador, default=0):
    if tabla is None: return default
    r = tabla[tabla['indicador'] == indicador]
    return int(r.iloc[0]['n']) if not r.empty else default


def _calc_pct_3plus(tabla):
    if tabla is None: return 78
    r = tabla[tabla['indicador'] == 'Promedio horas ahorradas/semana (proyección endline)']
    if r.empty: return 78
    detalle = str(r.iloc[0]['detalle'])
    n_3_4 = n_5 = total = 0
    for part in detalle.split('|'):
        if part.strip().startswith('3-4h:'):
            n_3_4 = int(part.split(':')[1])
        elif part.strip().startswith('5+h:'):
            n_5 = int(part.split(':')[1])
        if ':' in part:
            try: total += int(part.rsplit(':', 1)[1])
            except ValueError: pass
    return round((n_3_4 + n_5) / total * 100) if total else 78


def _formato_alcance(num):
    if num >= 1_000_000:
        valor = num / 1_000_000
        return f'+{valor:.1f}M' if valor % 1 else f'+{int(valor)}M'
    return f'+{num//1000}K' if num >= 1000 else str(num)


# ============================================================
# GENERACIÓN DEL HTML CON PLOTLY (interactivo, perfecto)
# ============================================================
def generar_html_reporte(tabla_maestra, cohorte='C8', programa='Fellowship',
                         orgs_lista=None, contenido=None):
    """
    HTML completo del reporte visual estilo Canva con Plotly choropleth + pie chart.

    Args:
      tabla_maestra: DataFrame con los indicadores calculados
      cohorte: ej. 'C8'
      programa: 'Fellowship' o 'Impact Accelerator'
      orgs_lista: lista de orgs (default: las de C8)
      contenido: dict con textos editables (Capa 2). Si None, usa CONTENIDO_DEFAULT.
                 Ver obtener_contenido_default() para la estructura completa.

    Returns: string HTML auto-contenido.
    """
    # Capa 2: contenido editable (con fallback al default)
    if contenido is None:
        contenido = CONTENIDO_DEFAULT
    # Asegurar que tenga todas las claves (merge con defaults)
    cont = {**CONTENIDO_DEFAULT, **contenido}

    paleta = COLORES_FELLOWSHIP if programa == 'Fellowship' else COLORES_ACCELERATOR

    if orgs_lista is None:
        from datos_sinteticos import ORGS_C8
        orgs_lista = list(ORGS_C8.keys())
    orgs_enriq = enriquecer_orgs(orgs_lista)
    meta = agregar_metadata(orgs_enriq)

    n_part = _get_n(tabla_maestra, 'NPS', 33)
    nps = _get_val(tabla_maestra, 'NPS', 78.79)
    ai_mindset = _get_val(tabla_maestra, '% participantes con AI Mindset alto', 93.94)
    nueva_herr = _get_val(tabla_maestra, '% participantes adoptó nueva herramienta', 93.94)
    confianza = _get_val(tabla_maestra, '% participantes mayor confianza tecnología', 96.97)
    pct_3plus = _calc_pct_3plus(tabla_maestra)

    causas_items = sorted(meta['causas'].items(), key=lambda x: -x[1])
    pie_data = [{'label': c, 'value': n} for c, n in causas_items]

    mapa_data = []
    for pais, count in meta['paises'].items():
        if pais in CODIGOS_PAIS:
            mapa_data.append({'pais': pais, 'iso': CODIGOS_PAIS[pais], 'count': count})

    # Heroes (usar los del contenido editable)
    heroes = cont.get('heroes', CONTENIDO_DEFAULT['heroes'])

    heroes_html = ''
    for i, h in enumerate(heroes):
        info_block = f'''
            <div class="hero-info">
              <h4>{h['nombre']}</h4>
              <p>{h['descripcion']}</p>
              <p>{h['plan_digital']}</p>
              <p><strong>Progress:</strong> {h['progreso']}</p>
              <div class="hero-quote">"{h['quote']}"</div>
              <div class="hero-quote-author">— {h['autor']}.</div>
            </div>'''
        # Imagen real si está, placeholder si no
        if h.get('imagen_base64'):
            img_block = (f'<img src="{h["imagen_base64"]}" '
                         f'class="hero-img-real" alt="{h["nombre"]}">')
        else:
            img_block = (f'<div class="hero-img-placeholder">'
                         f'[ Foto {h["nombre"]} ]</div>')
        row = info_block + img_block if i % 2 == 0 else img_block + info_block
        heroes_html += f'<div class="hero-row">{row}</div>\n'

    # Imagen de cohorte (sección "What we accomplished")
    if cont.get('accomplish_imagen_base64'):
        accomplish_img_html = (f'<img src="{cont["accomplish_imagen_base64"]}" '
                                f'class="accomplish-img-real" alt="Cohorte">')
    else:
        accomplish_img_html = (f'<div class="accomplish-img">'
                                f'[ Imagen de cohorte ]</div>')

    # Resolver placeholders en los textos editables
    fmt_vars = {
        'n_part': n_part,
        'num_orgs': meta['num_orgs'],
        'num_paises': meta['num_paises'],
        'num_causas': meta['num_causas'],
        'programa': programa,
        'cohorte': cohorte,
    }

    def fmt(text):
        try:
            return text.format(**fmt_vars)
        except (KeyError, IndexError):
            return text

    bg_color = paleta['header_bg']
    accent = paleta['accent']
    accent_yellow = paleta['accent_yellow']
    pie_colors_json = json.dumps(paleta['pie_palette'])
    map_scale_json = json.dumps(paleta['map_colorscale'])

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Propel {programa} · Cohort {cohorte} Report</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
         color: {paleta['text_dark']}; background: {paleta['bg_light']}; line-height: 1.5; }}

  .header {{ background: {bg_color}; color: white; padding: 60px 80px 80px;
             display: flex; justify-content: space-between; align-items: center;
             flex-wrap: wrap; gap: 40px; }}
  .logo-block {{ display: flex; align-items: center; gap: 20px; }}
  .logo-icon {{ width: 50px; height: 50px; background: {accent};
                clip-path: polygon(50% 0%, 80% 30%, 70% 80%, 30% 80%, 20% 30%); }}
  .logo-text {{ font-size: 32px; font-weight: 700; letter-spacing: -0.5px; }}
  .logo-divider {{ width: 1px; height: 40px; background: rgba(255,255,255,0.4); }}
  .logo-program {{ font-size: 26px; font-weight: 400; }}
  .header-tagline {{ font-size: 28px; font-weight: 400; line-height: 1.3; text-align: right; }}
  .header-tagline strong {{ color: {accent_yellow}; font-weight: 600; }}

  .section {{ padding: 60px 80px; max-width: 1400px; margin: 0 auto; }}
  .section h2 {{ color: {accent}; font-size: 24px; font-weight: 700; margin-bottom: 12px; }}
  .section .lead {{ font-size: 18px; margin-bottom: 40px; max-width: 850px; }}

  .metrics-card {{ background: white; padding: 40px 50px; display: flex;
                   gap: 50px; border-radius: 4px; margin-bottom: 60px;
                   max-width: fit-content;
                   box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
  .metric {{ text-align: center; }}
  .metric-value {{ font-size: 56px; color: {accent}; font-weight: 700; line-height: 1; }}
  .metric-label {{ font-size: 15px; margin-top: 4px; }}

  .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px;
                 align-items: start; }}
  .chart-block h3 {{ font-size: 20px; font-weight: 700; margin-bottom: 20px; }}

  .accomplish {{ display: grid; grid-template-columns: 320px 1fr; gap: 60px;
                 align-items: center; }}
  .accomplish-img {{ background: linear-gradient(135deg, {accent}, #f4a261);
                     height: 320px; border-radius: 4px;
                     display: flex; align-items: center; justify-content: center;
                     color: white; font-size: 14px; }}
  .big-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px 50px; }}
  .big-stat-num {{ font-size: 78px; color: {accent}; font-weight: 700; line-height: 1; }}
  .big-stat-label {{ font-size: 16px; margin-top: 6px; }}

  .closing-bar {{ background: {bg_color}; color: white; padding: 50px 80px;
                  display: flex; justify-content: space-between; align-items: center;
                  flex-wrap: wrap; gap: 40px; }}
  .closing-text {{ font-size: 18px; max-width: 480px; }}
  .closing-stats {{ background: rgba(255,255,255,0.08); padding: 24px 32px;
                    display: flex; gap: 50px; border-radius: 4px; }}
  .cs-num {{ font-size: 42px; font-weight: 700; line-height: 1; }}
  .cs-label {{ font-size: 13px; opacity: 0.85; margin-top: 4px; max-width: 100px; }}

  .heroes-bar {{ background: {bg_color}; color: white; padding: 16px 80px;
                 font-weight: 600; text-align: center; font-size: 18px; }}
  .hero-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 60px;
               padding: 50px 80px; border-bottom: 1px solid #d0d0c8;
               align-items: center; }}
  .hero-row:last-child {{ border-bottom: none; }}
  .hero-info h4 {{ font-size: 22px; font-weight: 700; margin-bottom: 16px; }}
  .hero-info p {{ margin-bottom: 12px; font-size: 16px; }}
  .hero-quote {{ font-weight: 600; font-style: italic; margin: 16px 0; }}
  .hero-quote-author {{ font-size: 14px; color: #666; }}
  .hero-img-placeholder {{ background: #c8d3d6; height: 280px; border-radius: 4px;
                           display: flex; align-items: center; justify-content: center;
                           color: #4a6670; font-size: 13px; }}
  .hero-img-real {{ width: 100%; height: 280px; object-fit: cover;
                    border-radius: 4px; display: block; }}
  .accomplish-img-real {{ width: 320px; height: 320px; object-fit: cover;
                          border-radius: 4px; display: block; }}

  .footer {{ background: {bg_color}; color: white; padding: 40px 80px; text-align: center; }}
  .footer .quote {{ font-size: 18px; font-style: italic; margin-bottom: 8px; color: {accent}; }}

  #pie-causas, #map-paises {{ height: 380px; }}

  @media (max-width: 900px) {{
    .header, .section, .closing-bar, .heroes-bar, .hero-row {{ padding: 40px 24px; }}
    .charts-row, .accomplish, .hero-row {{ grid-template-columns: 1fr; }}
    .big-stats {{ grid-template-columns: 1fr 1fr; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="logo-block">
    <span class="logo-icon"></span>
    <span class="logo-text">Propel</span>
    <span class="logo-divider"></span>
    <span class="logo-program">{programa}</span>
  </div>
  <div class="header-tagline">
    {cont['tagline_pre']}<br>
    <strong>{cont['tagline_post']}</strong>
  </div>
</div>

<div class="section">
  <p class="lead">
    {fmt(cont['lead_inicial'])}
  </p>

  <h2>Cohort {cohorte} at a glance:</h2>
  <p class="lead">
    {fmt(cont['cohort_glance_lead'])}
  </p>

  <div class="metrics-card">
    <div class="metric">
      <div class="metric-value">{meta['num_orgs']}</div>
      <div class="metric-label">Organizations</div>
    </div>
    <div class="metric">
      <div class="metric-value">{meta['num_paises']}</div>
      <div class="metric-label">Countries</div>
    </div>
    <div class="metric">
      <div class="metric-value">{_formato_alcance(meta['alcance_total'])}</div>
      <div class="metric-label">Annual reach</div>
    </div>
  </div>

  <div class="charts-row">
    <div class="chart-block">
      <h3>Across Latin America</h3>
      <div id="map-paises"></div>
    </div>
    <div class="chart-block">
      <h3>A diversified portfolio of social impact</h3>
      <div id="pie-causas"></div>
    </div>
  </div>
</div>

<div class="section" style="background: white;">
  <div class="accomplish">
    {accomplish_img_html}
    <div>
      <h3 style="font-size: 22px; margin-bottom: 16px;">{cont['accomplish_titulo']}</h3>
      <p style="margin-bottom: 32px; font-size: 17px;">
        {fmt(cont['accomplish_intro'])}
      </p>
      <div class="big-stats">
        <div>
          <div class="big-stat-num">{ai_mindset:.0f}%</div>
          <div class="big-stat-label">embraced a digital mindset.</div>
        </div>
        <div>
          <div class="big-stat-num">{nueva_herr:.0f}%</div>
          <div class="big-stat-label">adopted new digital tools.</div>
        </div>
        <div>
          <div class="big-stat-num">{confianza:.0f}%</div>
          <div class="big-stat-label">are more confident using technology.</div>
        </div>
        <div>
          <div class="big-stat-num">{pct_3plus}%</div>
          <div class="big-stat-label">expect to save 3+ hours/week.</div>
        </div>
      </div>
      <p style="margin-top: 32px; font-size: 17px;">
        {fmt(cont['accomplish_outro'])}
      </p>
    </div>
  </div>
</div>

<div class="closing-bar">
  <div class="closing-text">
    {fmt(cont['closing_text'])}
  </div>
  <div class="closing-stats">
    <div>
      <div class="cs-num">{nps:.0f}</div>
      <div class="cs-label">NPS</div>
    </div>
    <div>
      <div class="cs-num">{cont['closing_session_rating']}</div>
      <div class="cs-label">Average session rating</div>
    </div>
    <div>
      <div class="cs-num">{cont['closing_live_hours']}</div>
      <div class="cs-label">Live sessions delivered</div>
    </div>
  </div>
</div>

<div class="heroes-bar">Meet the heroes</div>
<div class="section" style="padding: 0;">
{heroes_html}
</div>

<div class="footer">
  <div class="quote">{fmt(cont['footer_quote'])}</div>
  <div>{cont['footer_subtext']}</div>
</div>

<script>
const causas = {json.dumps(pie_data, ensure_ascii=False)};
Plotly.newPlot('pie-causas', [{{
  values: causas.map(c => c.value),
  labels: causas.map(c => c.label),
  type: 'pie',
  textinfo: 'percent',
  textposition: 'inside',
  marker: {{ colors: {pie_colors_json} }},
}}], {{
  margin: {{t: 10, b: 10, l: 10, r: 10}},
  showlegend: true,
  legend: {{orientation: 'v', x: 1, y: 0.5, font: {{size: 12}}}},
  font: {{family: '-apple-system, sans-serif'}},
  paper_bgcolor: 'rgba(0,0,0,0)',
}}, {{displayModeBar: false, responsive: true}});

const mapa = {json.dumps(mapa_data, ensure_ascii=False)};
Plotly.newPlot('map-paises', [{{
  type: 'choropleth',
  locations: mapa.map(m => m.iso),
  z: mapa.map(m => m.count),
  text: mapa.map(m => m.pais + ': ' + m.count + (m.count > 1 ? ' organizations' : ' organization')),
  hoverinfo: 'text',
  colorscale: {map_scale_json},
  showscale: false,
  marker: {{line: {{color: 'white', width: 1}}}},
}}], {{
  geo: {{
    scope: 'world',
    showcoastlines: false, showframe: false,
    projection: {{type: 'mercator'}},
    lataxis: {{range: [-58, 35]}},
    lonaxis: {{range: [-120, -30]}},
    showcountries: true, countrycolor: '#aaa',
    showland: true, landcolor: '#f5f5f0',
    showocean: false, bgcolor: 'rgba(0,0,0,0)',
  }},
  margin: {{t: 0, b: 0, l: 0, r: 0}},
  paper_bgcolor: 'rgba(0,0,0,0)',
}}, {{displayModeBar: false, responsive: true}});
</script>

</body>
</html>"""

    return html


# ============================================================
# GENERAR PNGs PARA INSERTAR EN GOOGLE DOCS
# ============================================================
def _png_pie_causas(causas_dict, paleta):
    """Pie chart de causas con Plotly + kaleido (más moderno que matplotlib)."""
    items = sorted(causas_dict.items(), key=lambda x: -x[1])
    labels = [c for c, _ in items]
    values = [n for _, n in items]
    total = sum(values)

    try:
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Pie(
            labels=[f'{l}  ({v / total * 100:.1f}%)' for l, v in zip(labels, values)],
            values=values,
            marker=dict(colors=paleta[:len(labels)],
                        line=dict(color='white', width=2)),
            textposition='inside',
            textinfo='percent',
            textfont=dict(size=14, color='white', family='Arial'),
            hoverinfo='skip',
        )])
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation='v', x=1.02, y=0.5,
                        font=dict(size=14, family='Arial')),
            font=dict(family='Arial', size=13),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor='white',
        )
        return fig.to_image(format='png', width=900, height=480, scale=2)
    except Exception:
        # Fallback a matplotlib si kaleido falla
        fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
        wedges, _ = ax.pie(values, colors=paleta[:len(labels)],
                           startangle=90, counterclock=False,
                           wedgeprops={'edgecolor': 'white', 'linewidth': 2})
        legend_labels = [f'{l}  ({v / total * 100:.1f}%)' for l, v in zip(labels, values)]
        ax.legend(wedges, legend_labels, loc='center left',
                  bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=11)
        ax.axis('equal')
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight',
                    facecolor='white', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()


# ============================================================
# UTILS — extracción de datos de la tabla maestra para los gráficos
# ============================================================
def _parse_dict_str(detalle):
    """Parsea '{'A': 1, 'B': 2}' o similar a dict."""
    import ast
    if not detalle:
        return {}
    try:
        return ast.literal_eval(str(detalle))
    except (ValueError, SyntaxError):
        return {}


def _parse_pipes(detalle):
    """Parsea 'A:5|B:10|C:3' a dict."""
    result = {}
    if not detalle:
        return result
    for part in str(detalle).split('|'):
        if ':' in part:
            k, v = part.rsplit(':', 1)
            try:
                result[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return result


def _plotly_a_png(fig, width=900, height=500, scale=2):
    """Convierte figura Plotly a PNG bytes vía kaleido. Devuelve None si falla."""
    try:
        fig.update_layout(paper_bgcolor='white', plot_bgcolor='white',
                          font=dict(family='Arial'))
        return fig.to_image(format='png', width=width, height=height, scale=scale)
    except Exception as e:
        print(f'Warning: no se pudo generar PNG con Plotly/kaleido: {e}')
        return None


def _png_indicadores_clave(tabla_maestra):
    """
    Genera PNGs Plotly de los gráficos clave por indicador.
    Devuelve dict con bytes PNG por cada gráfico (puede tener None si falla alguno).
    """
    import visualizaciones as viz

    pngs = {}

    def _val(ind, default=None):
        r = tabla_maestra[tabla_maestra['indicador'] == ind]
        return float(r.iloc[0]['valor']) if not r.empty else default

    def _n(ind, default=0):
        r = tabla_maestra[tabla_maestra['indicador'] == ind]
        return int(r.iloc[0]['n']) if not r.empty else default

    def _det(ind):
        r = tabla_maestra[tabla_maestra['indicador'] == ind]
        return str(r.iloc[0]['detalle']) if not r.empty else ''

    # --- NPS gauge ---
    nps_v = _val('NPS')
    if nps_v is not None:
        try:
            fig = viz.card_nps(nps_v, _n('NPS'))
            pngs['nps_gauge'] = _plotly_a_png(fig, width=900, height=480)
        except Exception as e:
            print(f'NPS gauge fallo: {e}')

    # --- Eficiencia donut + bar proyección ---
    pct_ef = _val('% participantes mejoraron eficiencia')
    if pct_ef is not None:
        n_total = _n('% participantes mejoraron eficiencia')
        n_mej = round(pct_ef * n_total / 100)
        prom = _val('Promedio horas ahorradas/semana (calculado pre-post)') or 0
        try:
            fig = viz.donut_eficiencia(pct_ef, n_mej, n_total, prom)
            pngs['eficiencia_donut'] = _plotly_a_png(fig, width=900, height=460)
        except Exception as e:
            print(f'Eficiencia donut fallo: {e}')

    # Bar eficiencia proyectada
    proj_det = _parse_pipes(_det('Promedio horas ahorradas/semana (proyección endline)'))
    if proj_det:
        n12 = proj_det.get('1-2h', 0)
        n34 = proj_det.get('3-4h', 0)
        n5 = proj_det.get('5+h', 0)
        prom_proj = _val('Promedio horas ahorradas/semana (proyección endline)') or 0
        try:
            fig = viz.bar_eficiencia_proyectada(n12, n34, n5, prom_proj)
            if fig is not None:
                pngs['eficiencia_bar'] = _plotly_a_png(fig, width=900, height=460)
        except Exception as e:
            print(f'Eficiencia bar fallo: {e}')

    # --- AI Adoption pie ---
    niveles = {}
    for nivel in ['Estratégico', 'Integrado', 'Activo', 'Explorando']:
        v = _val(f'AI Adoption Level - {nivel}')
        n_lvl = _n(f'AI Adoption Level - {nivel}')
        if v is not None:
            niveles[nivel] = round(v * n_lvl / 100)
    if niveles:
        try:
            fig = viz.pie_ai_adoption(niveles)
            pngs['ai_adoption_pie'] = _plotly_a_png(fig, width=900, height=520)
        except Exception as e:
            print(f'AI Adoption pie fallo: {e}')

    # --- Net AI Adoption change (stacked) ---
    cambio = _parse_dict_str(_det('% orgs aumentaron Net AI Adoption'))
    if cambio:
        try:
            fig = viz.stacked_net_ai_adoption(
                cambio.get('MEJORÓ', 0),
                cambio.get('MANTUVO MÁXIMO', 0),
                cambio.get('BAJÓ', 0),
                cambio.get('NO MEJORÓ', 0),
            )
            if fig is not None:
                pngs['ai_adoption_change'] = _plotly_a_png(fig, width=900, height=260)
        except Exception as e:
            print(f'AI Adoption change fallo: {e}')

    # --- Google AI use pie ---
    google_dist = _parse_pipes(_det('% participantes uso diario Google AI'))
    if google_dist:
        try:
            fig = viz.pie_uso_google_ai(google_dist)
            pngs['google_ai_pie'] = _plotly_a_png(fig, width=900, height=480)
        except Exception as e:
            print(f'Google AI pie fallo: {e}')

    # --- AI Mindset distribución ---
    mindset_dist = {}
    raw_mindset = _det('% participantes con AI Mindset alto')
    for part in raw_mindset.split('|'):
        if ':' in part:
            k, v = part.rsplit(':', 1)
            try:
                mindset_dist[float(k.strip())] = int(v.strip())
            except ValueError:
                pass
    if mindset_dist:
        try:
            fig = viz.bar_ai_mindset(mindset_dist)
            pngs['mindset_bar'] = _plotly_a_png(fig, width=900, height=460)
        except Exception as e:
            print(f'Mindset bar fallo: {e}')

    # --- Tool Learning bars ---
    promedios = {}
    pct_alto = {}
    for area in ['Marketing', 'Impacto', 'Eficiencia', 'Fundraising']:
        p = _val(f'Tool Learning {area} - promedio')
        pct = _val(f'Tool Learning {area} - % aprendizaje sig.')
        if p is not None:
            promedios[area] = p
        if pct is not None:
            pct_alto[area] = pct
    if promedios:
        try:
            fig = viz.bars_tool_learning(promedios, pct_alto)
            pngs['tool_learning_avg'] = _plotly_a_png(fig, width=900, height=400)
        except Exception as e:
            print(f'Tool Learning avg fallo: {e}')
    if pct_alto:
        try:
            fig = viz.bars_tool_learning_pct(pct_alto)
            pngs['tool_learning_pct'] = _plotly_a_png(fig, width=900, height=400)
        except Exception as e:
            print(f'Tool Learning pct fallo: {e}')

    # --- Digital Maturity stacked ---
    dimensiones = {}
    for d in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']:
        det = _parse_dict_str(_det(f'% orgs mejoraron DM dimensión {d.upper()}'))
        if det:
            dimensiones[d] = det
    if dimensiones:
        try:
            fig = viz.stacked_digital_maturity(dimensiones)
            if fig is not None:
                pngs['digital_maturity'] = _plotly_a_png(fig, width=900, height=480)
        except Exception as e:
            print(f'Digital Maturity fallo: {e}')

    # --- Confianza tecnología donut ---
    conf = _val('% participantes mayor confianza tecnología')
    if conf is not None:
        try:
            fig = viz.donut_confianza(conf, _n('% participantes mayor confianza tecnología'))
            pngs['confianza_donut'] = _plotly_a_png(fig, width=900, height=380)
        except Exception as e:
            print(f'Confianza donut fallo: {e}')

    # filtrar None
    return {k: v for k, v in pngs.items() if v is not None}


def _png_mapa_choropleth(paises_dict, paleta):
    """
    Mapa choropleth de LATAM con Plotly (mismo del HTML del portal).
    Pinta los países reales con sus contornos verdaderos.
    Requiere internet para descargar el topojson de países (~30 KB).
    """
    from datos_sinteticos import CODIGOS_PAIS

    mapa_data = []
    for pais, count in paises_dict.items():
        iso = CODIGOS_PAIS.get(pais)
        if iso:
            mapa_data.append({'pais': pais, 'iso': iso, 'count': count})

    if not mapa_data:
        return None

    import plotly.graph_objects as go

    fig = go.Figure(go.Choropleth(
        locations=[m['iso'] for m in mapa_data],
        z=[m['count'] for m in mapa_data],
        text=[f"{m['pais']}: {m['count']} organization{'s' if m['count'] > 1 else ''}"
              for m in mapa_data],
        hoverinfo='text',
        colorscale=paleta.get('map_colorscale',
                              [[0, '#d0d0c8'], [0.5, '#7da39f'], [1, '#1d4d4d']]),
        showscale=False,
        marker=dict(line=dict(color='white', width=1.5)),
    ))
    fig.update_layout(
        geo=dict(
            scope='world',
            showcoastlines=False, showframe=False,
            projection=dict(type='mercator'),
            lataxis=dict(range=[-58, 35]),
            lonaxis=dict(range=[-120, -30]),
            showcountries=True, countrycolor='#c8d3d3',
            showland=True, landcolor='#f5f5f0',
            showocean=False,
            bgcolor='rgba(0,0,0,0)',
        ),
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor='white',
        font=dict(family='Arial'),
    )

    return fig.to_image(format='png', width=900, height=700, scale=2)


def _png_mapa_bubble(paises_dict, paleta):
    """Mapa LATAM moderno con burbujas + halos suaves + etiquetas en cápsulas."""
    import numpy as np
    import matplotlib.patheffects as pe

    COORDS = {
        'México': (-102, 23), 'Estados Unidos': (-98, 38),
        'Guatemala': (-91, 15.5), 'Honduras': (-87, 14.5),
        'El Salvador': (-89, 13.5), 'Nicaragua': (-85, 13),
        'Costa Rica': (-84, 10), 'Panamá': (-80, 8.5),
        'Colombia': (-74, 4), 'Venezuela': (-66, 7),
        'Ecuador': (-78, -1.5), 'Perú': (-76, -10),
        'Bolivia': (-65, -17), 'Brasil': (-52, -10),
        'Paraguay': (-58, -23), 'Chile': (-71, -35),
        'Argentina': (-64, -36), 'Uruguay': (-56, -33),
    }
    LABEL_OFFSET = {
        'Estados Unidos': (0, 22, 'center', 'bottom'),
        'México': (-14, 0, 'right', 'center'),
        'Guatemala': (-14, 2, 'right', 'center'),
        'Honduras': (15, 5, 'left', 'bottom'),
        'El Salvador': (-14, -3, 'right', 'top'),
        'Panamá': (-14, -3, 'right', 'top'),
        'Colombia': (16, 0, 'left', 'center'),
        'Venezuela': (16, 0, 'left', 'center'),
        'Ecuador': (-15, 0, 'right', 'center'),
        'Perú': (-16, 0, 'right', 'center'),
        'Bolivia': (15, 0, 'left', 'center'),
        'Brasil': (15, 0, 'left', 'center'),
        'Paraguay': (-15, 0, 'right', 'center'),
        'Chile': (-16, 0, 'right', 'center'),
        'Argentina': (16, 0, 'left', 'center'),
        'Uruguay': (16, 0, 'left', 'center'),
    }

    primary = paleta[0] if paleta else '#1d4d4d'
    LAND = '#eef0e8'
    LAND_EDGE = '#9ba8a8'
    TEXT_DARK = '#1a2e35'

    fig, ax = plt.subplots(figsize=(9, 8), dpi=180)
    ax.set_xlim(-128, -28)
    ax.set_ylim(-58, 52)
    ax.set_facecolor('white')

    norte = np.array([
        (-124, 49), (-115, 49), (-95, 49), (-87, 47), (-83, 42),
        (-80, 40), (-76, 38), (-77, 35), (-79, 33), (-81, 31),
        (-81, 27), (-80, 25), (-83, 25), (-86, 22), (-89, 21),
        (-91, 18), (-94, 16), (-97, 16), (-100, 16), (-103, 18),
        (-105, 20), (-107, 23), (-110, 24), (-113, 27), (-114, 30),
        (-116, 32), (-117, 32), (-119, 33), (-122, 35),
        (-124, 38), (-124, 42), (-124, 46), (-124, 49),
    ])
    sur = np.array([
        (-77, 8), (-72, 12), (-68, 12), (-65, 11), (-62, 9),
        (-58, 6), (-55, 4), (-52, 1), (-50, -2), (-48, -1),
        (-46, -1), (-43, -2), (-40, -5), (-38, -8), (-36, -10),
        (-37, -14), (-39, -18), (-41, -22), (-44, -25), (-48, -28),
        (-50, -30), (-53, -32), (-56, -33), (-58, -34), (-60, -36),
        (-62, -38), (-65, -41), (-66, -45), (-68, -50), (-69, -53),
        (-67, -55), (-69, -55), (-72, -54), (-74, -52), (-74, -47),
        (-73, -42), (-72, -36), (-71, -32), (-71, -25), (-71, -18),
        (-77, -12), (-79, -8), (-81, -4), (-81, 0), (-79, 2),
        (-77, 5), (-77, 8),
    ])

    # Sombra muy suave debajo de los polígonos
    for poly in [norte, sur]:
        ax.fill(poly[:, 0], poly[:, 1] - 0.4, facecolor='#cdcfc8',
                alpha=0.4, zorder=1)

    # Tierra con borde elegante
    for poly in [norte, sur]:
        ax.fill(poly[:, 0], poly[:, 1], facecolor=LAND,
                edgecolor=LAND_EDGE, linewidth=1.2, zorder=2)

    if paises_dict:
        max_count = max(paises_dict.values())
        for pais, cantidad in sorted(paises_dict.items(), key=lambda x: -x[1]):
            if pais not in COORDS:
                continue
            lon, lat = COORDS[pais]
            base_size = 700
            size = base_size + (cantidad / max_count) * 1800
            # halo doble para efecto suave
            ax.scatter(lon, lat, s=size * 2.4, c=primary, alpha=0.10, zorder=3)
            ax.scatter(lon, lat, s=size * 1.5, c=primary, alpha=0.18, zorder=3)
            # círculo principal
            ax.scatter(lon, lat, s=size, c=primary, alpha=1.0,
                       edgecolors='white', linewidths=2.5, zorder=4)
            # número con stroke
            txt = ax.text(lon, lat, str(cantidad), ha='center', va='center',
                          color='white', fontsize=13, fontweight='bold', zorder=5)
            txt.set_path_effects([pe.withStroke(linewidth=2, foreground=primary)])
            # etiqueta en cápsula
            ox, oy, ha, va = LABEL_OFFSET.get(pais, (0, 14, 'center', 'bottom'))
            ax.annotate(pais, (lon, lat), xytext=(ox, oy),
                        textcoords='offset points', ha=ha, va=va,
                        fontsize=10.5, color=TEXT_DARK, fontweight='600', zorder=6,
                        bbox=dict(boxstyle='round,pad=0.4',
                                  facecolor='white', edgecolor='#dde0d8',
                                  linewidth=0.8, alpha=0.95))

    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight',
                facecolor='white', dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generar_imagenes_para_docs(tabla_maestra, programa='Fellowship', orgs_lista=None):
    """
    PNGs de los gráficos para insertar en el Google Doc.

    Genera:
      - mapa: bubble map de LATAM (matplotlib, offline)
      - pie_causas: pie chart de causas (Plotly via kaleido)
      - nps_gauge, eficiencia_donut, eficiencia_bar, ai_adoption_pie,
        ai_adoption_change, mindset_bar, tool_learning_avg, tool_learning_pct,
        digital_maturity, google_ai_pie, confianza_donut: gráficos Plotly

    Returns: dict con bytes PNG por gráfico + 'meta' con datos sociodemográficos.
    """
    paleta = COLORES_FELLOWSHIP if programa == 'Fellowship' else COLORES_ACCELERATOR

    if orgs_lista is None:
        from datos_sinteticos import ORGS_C8
        orgs_lista = list(ORGS_C8.keys())
    orgs_enriq = enriquecer_orgs(orgs_lista)
    meta = agregar_metadata(orgs_enriq)

    # Mapa: intentar primero choropleth Plotly (mapas reales). Si falla
    # (sin internet, kaleido sin chromium, etc.), fallback al matplotlib.
    mapa_png = None
    try:
        mapa_png = _png_mapa_choropleth(meta['paises'], paleta)
    except Exception as e:
        print(f"Warning: mapa choropleth falló ({e}), usando fallback matplotlib")

    if not mapa_png:
        mapa_png = _png_mapa_bubble(meta['paises'], paleta['pie_palette'])

    resultado = {
        'mapa': mapa_png,
        'pie_causas': _png_pie_causas(meta['causas'], paleta['pie_palette']),
        'meta': meta,
    }

    # Agregar PNGs de los gráficos de indicadores (si tabla_maestra disponible)
    if tabla_maestra is not None and not tabla_maestra.empty:
        try:
            indicadores_pngs = _png_indicadores_clave(tabla_maestra)
            resultado.update(indicadores_pngs)
        except Exception as e:
            print(f'Warning: no se pudieron generar PNGs de indicadores: {e}')

    return resultado


# ============================================================
# UTILIDAD: comprimir imagen subida y convertirla a data URI base64
# ============================================================
def imagen_a_data_uri(file_bytes, max_width=900, quality=82):
    """
    Toma bytes de una imagen subida (jpg/png), la redimensiona y comprime,
    y devuelve un data URI listo para usar en <img src="...">.

    Esto reduce el tamaño del HTML significativamente (de varios MB a ~100-300 KB
    por imagen). Si Pillow no está instalado, devuelve la imagen sin comprimir.
    """
    import base64
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        # Redimensionar manteniendo aspect ratio
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        # Convertir a RGB si tiene canal alpha (RGBA → RGB)
        if img.mode in ('RGBA', 'LA', 'P'):
            fondo = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            fondo.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = fondo
        # Guardar como JPEG comprimido
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        compressed = buf.getvalue()
        b64 = base64.b64encode(compressed).decode('ascii')
        return f'data:image/jpeg;base64,{b64}'
    except ImportError:
        # Fallback sin Pillow: usar la imagen tal cual
        b64 = base64.b64encode(file_bytes).decode('ascii')
        return f'data:image/jpeg;base64,{b64}'
