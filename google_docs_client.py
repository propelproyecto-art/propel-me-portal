"""
google_docs_client.py — Crea un Google Doc con layout profesional estilo Propel.

Estructura del documento:
  1. Header con título grande + subtítulo (color institucional Propel)
  2. Resumen ejecutivo
  3. Cohort at a glance (KPIs grandes + mapa + pie de causas)
  4. Indicadores clave con sus gráficos (NPS, eficiencia, adopción IA, mindset,
     tool learning, madurez digital, comunidad)
  5. Indicadores en detalle (texto completo de cada insight)
  6. Footer institucional

Las imágenes se generan localmente (Plotly + matplotlib), se suben al Shared
Drive del Workspace, y se referencian en el Doc por URL pública.
"""
import io
import json
from datetime import datetime
from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_DRIVE_FOLDER_ID


# ============================================================
# COLORES INSTITUCIONALES PROPEL (Google Docs RGB 0-1)
# ============================================================
COLOR_GREEN = {'red': 0.114, 'green': 0.302, 'blue': 0.302}      # #1d4d4d
COLOR_ORANGE = {'red': 0.906, 'green': 0.435, 'blue': 0.318}     # #e76f51
COLOR_TEXT_DARK = {'red': 0.102, 'green': 0.180, 'blue': 0.208}  # #1a2e35
COLOR_GRAY = {'red': 0.4, 'green': 0.4, 'blue': 0.4}             # #666666
COLOR_LIGHT = {'red': 0.85, 'green': 0.85, 'blue': 0.85}         # #d8d8d8


def _get_services():
    """Obtiene clientes autenticados de Docs y Drive."""
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise ValueError(
            "Google Docs no está configurado. Configura "
            "GOOGLE_SERVICE_ACCOUNT_JSON en Streamlit Secrets."
        )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = (json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
            if isinstance(GOOGLE_SERVICE_ACCOUNT_JSON, str)
            else GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=[
            'https://www.googleapis.com/auth/documents',
            'https://www.googleapis.com/auth/drive',
        ],
    )
    docs_service = build('docs', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return docs_service, drive_service


def _subir_imagen_publica(drive_service, png_bytes, nombre):
    """Sube una imagen PNG al Shared Drive y devuelve URL pública."""
    from googleapiclient.http import MediaIoBaseUpload
    media = MediaIoBaseUpload(io.BytesIO(png_bytes), mimetype='image/png',
                              resumable=False)
    metadata = {'name': nombre, 'mimeType': 'image/png'}
    if GOOGLE_DRIVE_FOLDER_ID:
        metadata['parents'] = [GOOGLE_DRIVE_FOLDER_ID]

    file = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields='id,webContentLink',
        supportsAllDrives=True,
    ).execute()
    file_id = file['id']
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'},
            supportsAllDrives=True,
        ).execute()
    except Exception as e:
        print(f"Warning: no se pudo hacer pública la imagen {nombre}: {e}")
    return f'https://drive.google.com/uc?id={file_id}'


# ============================================================
# DocBuilder — acumula requests para batchUpdate
# ============================================================
class _DocBuilder:
    def __init__(self):
        self.requests = []
        self.cursor = 1  # Google Docs empieza en 1

    def _insert_text(self, text):
        if not text:
            return self.cursor, self.cursor
        start = self.cursor
        self.requests.append({
            'insertText': {'location': {'index': start}, 'text': text}
        })
        self.cursor += len(text)
        return start, start + len(text)

    def _style_paragraph(self, start, end, named_style='NORMAL_TEXT',
                          alignment=None):
        ps = {'namedStyleType': named_style}
        fields = ['namedStyleType']
        if alignment:
            ps['alignment'] = alignment
            fields.append('alignment')
        self.requests.append({
            'updateParagraphStyle': {
                'range': {'startIndex': start, 'endIndex': end},
                'paragraphStyle': ps,
                'fields': ','.join(fields),
            }
        })

    def _style_text(self, start, end, **kwargs):
        ts = {}
        fields = []
        if 'bold' in kwargs:
            ts['bold'] = kwargs['bold']; fields.append('bold')
        if 'italic' in kwargs:
            ts['italic'] = kwargs['italic']; fields.append('italic')
        if 'color' in kwargs:
            ts['foregroundColor'] = {'color': {'rgbColor': kwargs['color']}}
            fields.append('foregroundColor')
        if 'fontSize' in kwargs:
            ts['fontSize'] = {'magnitude': kwargs['fontSize'], 'unit': 'PT'}
            fields.append('fontSize')
        if not fields:
            return
        self.requests.append({
            'updateTextStyle': {
                'range': {'startIndex': start, 'endIndex': end},
                'textStyle': ts,
                'fields': ','.join(fields),
            }
        })

    def title(self, text):
        """Título principal (verde Propel grande)."""
        s, e = self._insert_text(text + '\n')
        self._style_paragraph(s, e, 'TITLE')
        self._style_text(s, s + len(text), color=COLOR_GREEN, bold=True,
                          fontSize=26)

    def subtitle(self, text):
        """Subtítulo debajo del título."""
        s, e = self._insert_text(text + '\n')
        self._style_paragraph(s, e, 'SUBTITLE')
        self._style_text(s, s + len(text), color=COLOR_GRAY, italic=True,
                          fontSize=12)

    def heading(self, text, level=1, color=None):
        """Heading 1, 2 o 3."""
        s, e = self._insert_text(text + '\n')
        named = {1: 'HEADING_1', 2: 'HEADING_2', 3: 'HEADING_3'}.get(level, 'HEADING_2')
        self._style_paragraph(s, e, named)
        if color:
            self._style_text(s, s + len(text), color=color, bold=True)

    def paragraph(self, text, font_size=None, color=None, bold=False,
                   italic=False, alignment=None):
        if not text:
            return
        s, e = self._insert_text(text + '\n')
        self._style_paragraph(s, e, 'NORMAL_TEXT', alignment=alignment)
        kwargs = {}
        if font_size: kwargs['fontSize'] = font_size
        if color: kwargs['color'] = color
        if bold: kwargs['bold'] = bold
        if italic: kwargs['italic'] = italic
        if kwargs:
            self._style_text(s, s + len(text), **kwargs)

    def empty_line(self):
        self._insert_text('\n')

    def image(self, url, width_pt=460):
        """Inserta imagen centrada."""
        start = self.cursor
        self.requests.append({
            'insertInlineImage': {
                'location': {'index': start},
                'uri': url,
                'objectSize': {
                    'height': {'magnitude': width_pt * 0.58, 'unit': 'PT'},
                    'width': {'magnitude': width_pt, 'unit': 'PT'},
                },
            }
        })
        self.cursor += 1
        # newline + centrado
        self._insert_text('\n')
        self._style_paragraph(start, start + 2, 'NORMAL_TEXT', alignment='CENTER')

    def divider(self):
        text = '─' * 30 + '\n'
        s, e = self._insert_text(text)
        self._style_paragraph(s, e, 'NORMAL_TEXT', alignment='CENTER')
        self._style_text(s, s + len(text) - 1, color=COLOR_LIGHT, fontSize=10)

    def kpi_block(self, valor, etiqueta):
        """Bloque KPI grande centrado: número grande + etiqueta pequeña."""
        # valor (grande, verde)
        s, e = self._insert_text(valor + '\n')
        self._style_paragraph(s, e, 'NORMAL_TEXT', alignment='CENTER')
        self._style_text(s, s + len(valor), color=COLOR_GREEN, bold=True,
                          fontSize=32)
        # etiqueta (pequeña, gris, mayúsculas)
        s, e = self._insert_text(etiqueta.upper() + '\n')
        self._style_paragraph(s, e, 'NORMAL_TEXT', alignment='CENTER')
        self._style_text(s, s + len(etiqueta), color=COLOR_GRAY, fontSize=10)
        self.empty_line()

    def build(self):
        return self.requests


# ============================================================
# Mapeo: nombre del indicador → key del PNG correspondiente
# Gráfico se inserta DEBAJO del nombre del indicador, ANTES del insight.
# ============================================================
INDICADOR_A_GRAFICO = {
    'NPS': 'nps_gauge',
    '% participantes mejoraron eficiencia': 'eficiencia_donut',
    'Promedio horas ahorradas/semana (proyección endline)': 'eficiencia_bar',
    'AI Adoption Level - Estratégico': 'ai_adoption_pie',
    '% orgs aumentaron Net AI Adoption': 'ai_adoption_change',
    '% participantes uso diario Google AI': 'google_ai_pie',
    '% participantes con AI Mindset alto': 'mindset_bar',
    'Tool Learning Marketing - promedio': 'tool_learning_avg',
    'Tool Learning Marketing - % aprendizaje sig.': 'tool_learning_pct',
    '% orgs mejoraron Digital Maturity (total)': 'digital_maturity',
    '% participantes mayor confianza tecnología': 'confianza_donut',
}


# ============================================================
# Construcción del reporte
# ============================================================
def _build_requests_reporte(reporte, urls_imagenes, datos_socio):
    b = _DocBuilder()

    # ===== HEADER =====
    b.title(reporte['titulo'])
    b.subtitle(reporte['subtitulo'])
    b.empty_line()

    # ===== RESUMEN EJECUTIVO =====
    b.heading('Resumen ejecutivo', level=1, color=COLOR_GREEN)
    for parr in reporte['resumen_ejecutivo'].split('\n\n'):
        if parr.strip():
            b.paragraph(parr.strip(), font_size=11)
    b.empty_line()

    # ===== COHORTE EN CIFRAS =====
    b.heading(f"Cohorte {reporte['cohorte']} en cifras", level=1, color=COLOR_GREEN)

    n_orgs = datos_socio.get('num_orgs', 0)
    n_paises = datos_socio.get('num_paises', 0)
    n_causas = datos_socio.get('num_causas', 0)
    alcance = datos_socio.get('alcance_total', 0)
    alcance_str = (f"+{alcance / 1_000_000:.1f}M" if alcance >= 1_000_000
                   else f"+{alcance // 1000}K" if alcance >= 1000 else str(alcance))

    b.paragraph(
        f"Una cohorte diversa de {n_orgs} organizaciones en {n_paises} "
        f"países, trabajando en {n_causas} causas sociales, con un alcance "
        f"anual de {alcance:,} personas.",
        font_size=12, italic=True, color=COLOR_GRAY,
    )
    b.empty_line()

    for valor, etiqueta in [
        (str(n_orgs), 'organizaciones'),
        (str(n_paises), 'países'),
        (str(n_causas), 'causas sociales'),
        (alcance_str, 'personas alcanzadas/año'),
    ]:
        b.kpi_block(valor, etiqueta)

    # Mapa
    if urls_imagenes.get('mapa'):
        b.heading('Distribución geográfica', level=2, color=COLOR_GREEN)
        b.image(urls_imagenes['mapa'], width_pt=460)
        b.empty_line()

    # Pie causas
    if urls_imagenes.get('pie_causas'):
        b.heading('Portafolio de impacto social', level=2, color=COLOR_GREEN)
        b.image(urls_imagenes['pie_causas'], width_pt=460)
        b.empty_line()

    # ===== INDICADORES — cada uno con su gráfico + insight juntos =====
    b.heading('Indicadores', level=1, color=COLOR_GREEN)
    b.paragraph(
        'Para cada indicador medido durante la cohorte se presenta el resultado, '
        'la visualización correspondiente y la interpretación estratégica.',
        font_size=11, italic=True, color=COLOR_GRAY,
    )
    b.empty_line()

    for seccion in reporte['secciones']:
        # Saltar la sección sociodemográfica (ya cubierta arriba con KPIs grandes)
        if seccion['titulo'].startswith('1.'):
            continue

        # Encabezado de sección (NPS, Eficiencia, Adopción de IA, etc.)
        b.heading(seccion['titulo'], level=2, color=COLOR_GREEN)

        for item in seccion['contenido']:
            if item['tipo'] == 'metadata':
                continue

            # Nombre del indicador (subheading)
            b.heading(item['nombre'], level=3, color=COLOR_TEXT_DARK)

            # Resultado en formato compacto
            resultado = f"Resultado: {item['valor']}{item['unidad']} (n={item['n']})"
            b.paragraph(resultado, font_size=10, color=COLOR_GRAY, italic=True)
            if item.get('detalle'):
                b.paragraph(f"Detalle: {item['detalle']}", font_size=10,
                            color=COLOR_GRAY, italic=True)
            b.empty_line()

            # GRÁFICO del indicador (si existe), justo debajo de los datos crudos
            grafico_key = INDICADOR_A_GRAFICO.get(item['nombre'])
            if grafico_key and urls_imagenes.get(grafico_key):
                b.image(urls_imagenes[grafico_key], width_pt=470)
                b.empty_line()

            # INSIGHT textual (interpretación)
            b.paragraph(item['insight'], font_size=11)
            b.empty_line()

    # ===== FOOTER =====
    b.divider()
    b.paragraph(
        f"Reporte generado automáticamente · Sistema Propel M&E · "
        f"{datetime.now().strftime('%d/%m/%Y')}",
        font_size=9, color=COLOR_GRAY, italic=True, alignment='CENTER',
    )

    return b.build()


def create_google_doc(reporte, tabla_maestra=None, programa='Fellowship',
                       email_para_compartir=None, orgs_lista=None):
    """
    Crea un Google Doc con layout profesional + colores Propel + todos los
    gráficos clave de la cohorte.

    Args:
        reporte: dict con la estructura del reporte.
        tabla_maestra: DataFrame con los indicadores calculados.
        programa: 'Fellowship' o 'Impact Accelerator'.
        email_para_compartir: si se da, comparte el doc con ese email.
        orgs_lista: lista de nombres de organizaciones de la cohorte. Si no
            se pasa, usa el default de datos_sinteticos (las 23 orgs de C8).
    """
    docs_service, drive_service = _get_services()

    # 1. Generar imágenes (hasta 13 PNGs distintos)
    urls_imagenes = {}
    datos_socio = {}
    if tabla_maestra is not None:
        try:
            from reporte_visual import generar_imagenes_para_docs
            imgs = generar_imagenes_para_docs(
                tabla_maestra, programa=programa, orgs_lista=orgs_lista
            )
            datos_socio = imgs.get('meta', {})

            # 2. Subir cada PNG al Shared Drive
            for tipo, png_bytes in imgs.items():
                if tipo == 'meta' or not png_bytes:
                    continue
                nombre = f"propel_{reporte['cohorte']}_{tipo}.png"
                try:
                    urls_imagenes[tipo] = _subir_imagen_publica(
                        drive_service, png_bytes, nombre
                    )
                except Exception as e:
                    print(f"Warning: no se pudo subir {tipo}: {e}")
        except Exception as e:
            print(f"Warning: generación de imágenes falló: {e}")

    # 3. Crear Doc en el Shared Drive
    file_metadata = {
        'name': reporte['titulo'],
        'mimeType': 'application/vnd.google-apps.document',
    }
    if GOOGLE_DRIVE_FOLDER_ID:
        file_metadata['parents'] = [GOOGLE_DRIVE_FOLDER_ID]

    file = drive_service.files().create(
        body=file_metadata,
        fields='id',
        supportsAllDrives=True,
    ).execute()
    doc_id = file['id']

    # 4. Aplicar contenido en chunks de 50 requests
    requests = _build_requests_reporte(reporte, urls_imagenes, datos_socio)
    if requests:
        for i in range(0, len(requests), 50):
            chunk = requests[i:i + 50]
            try:
                docs_service.documents().batchUpdate(
                    documentId=doc_id, body={'requests': chunk}
                ).execute()
            except Exception as e:
                print(f"Warning: chunk {i}-{i+50} falló: {e}")

    # 5. Permisos
    try:
        drive_service.permissions().create(
            fileId=doc_id,
            body={'type': 'anyone', 'role': 'writer'},
            supportsAllDrives=True,
        ).execute()
    except Exception as e:
        print(f"Warning: no se pudo hacer público: {e}")

    if email_para_compartir:
        try:
            drive_service.permissions().create(
                fileId=doc_id,
                sendNotificationEmail=False,
                supportsAllDrives=True,
                body={
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': email_para_compartir,
                },
            ).execute()
        except Exception:
            pass

    return {
        'url': f'https://docs.google.com/document/d/{doc_id}/edit',
        'doc_id': doc_id,
    }
