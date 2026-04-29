"""
datos_sinteticos.py — Mock de enriquecimiento sociodemográfico desde Salesforce.

Esta información (país, ciudad, causa social, alcance) en producción vendrá
de Salesforce. Mientras tanto, este módulo provee datos sintéticos verosímiles
para que el reporte visual se vea completo en pruebas y demos.

Cuando se conecte Salesforce, basta reemplazar enriquecer_orgs() por una
llamada al CRM.
"""

# Mapeo de orgs Cohorte 8 a sus datos enriquecidos (sintéticos).
# Las orgs son las reales del programa; el resto fue inventado de forma
# verosímil basándose en las regiones de operación.
ORGS_C8 = {
    'SHEnampa': {
        'pais': 'México', 'ciudad': 'Ciudad de México',
        'causa': 'Gender Equality', 'alcance': 7000,
    },
    'Fundacion Leonardo Da Vinci': {
        'pais': 'Argentina', 'ciudad': 'Buenos Aires',
        'causa': 'Education', 'alcance': 10000,
    },
    'Fundacion Amanecer': {
        'pais': 'Colombia', 'ciudad': 'Bogotá',
        'causa': 'Education', 'alcance': 100000,
    },
    'Mentors International': {
        'pais': 'Guatemala', 'ciudad': 'Ciudad de Guatemala',
        'causa': 'Education', 'alcance': 220000,
    },
    'Ayni Educativo': {
        'pais': 'Perú', 'ciudad': 'Lima',
        'causa': 'Education', 'alcance': 8000,
    },
    'World Connect Academy': {
        'pais': 'Honduras', 'ciudad': 'Tegucigalpa',
        'causa': 'Education', 'alcance': 1200,
    },
    'UMA Peru': {
        'pais': 'Perú', 'ciudad': 'Lima',
        'causa': 'Health & Wellbeing', 'alcance': 400,
    },
    'Fundacion Verez y Saberes': {
        'pais': 'Colombia', 'ciudad': 'Medellín',
        'causa': 'Human Rights', 'alcance': 3600,
    },
    'Hechoxrefugiados': {
        'pais': 'Perú', 'ciudad': 'Lima',
        'causa': 'Human Rights', 'alcance': 244,
    },
    'Fundacion Impulso Docente': {
        'pais': 'Chile', 'ciudad': 'Santiago',
        'causa': 'Education', 'alcance': 32929,
    },
    'Corporacion Dolores Sopena': {
        'pais': 'Colombia', 'ciudad': 'Cali',
        'causa': 'Education', 'alcance': 20774,
    },
    'Sociedad Ornitologica de Cordoba': {
        'pais': 'Argentina', 'ciudad': 'Córdoba',
        'causa': 'Environment & Climate', 'alcance': 3000,
    },
    'Proa': {
        'pais': 'Estados Unidos', 'ciudad': 'Miami',
        'causa': 'Civic Engagement', 'alcance': 70000,
    },
    'Teuno': {
        'pais': 'Perú', 'ciudad': 'Lima',
        'causa': 'Arts & Culture', 'alcance': 400,
    },
    'Niños a la Vida': {
        'pais': 'Perú', 'ciudad': 'Lima',
        'causa': 'Youth Development', 'alcance': 5000,
    },
    'MAR Fund': {
        'pais': 'Panamá', 'ciudad': 'Ciudad de Panamá',
        'causa': 'Environment & Climate', 'alcance': 25000,
    },
    'Fonselp': {
        'pais': 'Perú', 'ciudad': 'Cusco',
        'causa': 'Civic Engagement', 'alcance': 116879,
    },
    'Impacto Digital': {
        'pais': 'Chile', 'ciudad': 'Valparaíso',
        'causa': 'Civic Engagement', 'alcance': 200000,
    },
    'Kaykuna Peru': {
        'pais': 'Perú', 'ciudad': 'Arequipa',
        'causa': 'Human Rights', 'alcance': 6000,
    },
    'Fundacion Educacional Chungungo': {
        'pais': 'Chile', 'ciudad': 'La Serena',
        'causa': 'Education', 'alcance': 3000,
    },
    'Deficit Cero': {
        'pais': 'Chile', 'ciudad': 'Santiago',
        'causa': 'Civic Engagement', 'alcance': 37000,
    },
    'Fundacion Seamos Huella': {
        'pais': 'Colombia', 'ciudad': 'Cartagena',
        'causa': 'Youth Development', 'alcance': 1000,
    },
    'Impacta: Jovenes por la Gestion Publica': {
        'pais': 'Argentina', 'ciudad': 'Buenos Aires',
        'causa': 'Civic Engagement', 'alcance': 1000,
    },
}

# Códigos ISO para el choropleth
CODIGOS_PAIS = {
    'México': 'MEX', 'Argentina': 'ARG', 'Colombia': 'COL',
    'Guatemala': 'GTM', 'Perú': 'PER', 'Honduras': 'HND',
    'Chile': 'CHL', 'Estados Unidos': 'USA', 'Panamá': 'PAN',
    'Ecuador': 'ECU', 'Bolivia': 'BOL', 'Uruguay': 'URY',
    'Paraguay': 'PRY', 'Venezuela': 'VEN', 'Brasil': 'BRA',
    'Costa Rica': 'CRI', 'El Salvador': 'SLV', 'Nicaragua': 'NIC',
    'República Dominicana': 'DOM', 'Cuba': 'CUB',
}


def enriquecer_orgs(lista_orgs):
    """
    Devuelve un dict con la info enriquecida de cada org.
    Las que están en ORGS_C8 usan datos sintéticos predefinidos;
    las que no, reciben placeholders de "(no disponible)".
    """
    resultado = {}
    for org in lista_orgs:
        if org in ORGS_C8:
            resultado[org] = ORGS_C8[org]
        else:
            resultado[org] = {
                'pais': '(no disponible)',
                'ciudad': '(no disponible)',
                'causa': 'Otros',
                'alcance': 0,
            }
    return resultado


def agregar_metadata(orgs_enriquecidas):
    """Calcula totales agregados a partir de las orgs enriquecidas."""
    paises = {}
    causas = {}
    alcance_total = 0
    for org, datos in orgs_enriquecidas.items():
        paises[datos['pais']] = paises.get(datos['pais'], 0) + 1
        causas[datos['causa']] = causas.get(datos['causa'], 0) + 1
        alcance_total += datos['alcance']
    paises = {k: v for k, v in paises.items() if k != '(no disponible)'}
    return {
        'paises': paises,
        'causas': causas,
        'alcance_total': alcance_total,
        'num_orgs': len(orgs_enriquecidas),
        'num_paises': len(paises),
        'num_causas': len(causas),
    }
