# Propel M&E — Calculadora de indicadores

Portal Streamlit para automatizar el cálculo de indicadores M&E de los programas de Propel.

## Estructura del proyecto

```
streamlit_app/
├── app.py              ← Interfaz Streamlit (la app principal)
├── indicadores.py      ← Lógica de cálculo (validada contra C8)
├── data_sources.py     ← Conexión a Supabase y lectura de CSVs
├── config.py           ← Credenciales y configuración
├── requirements.txt    ← Dependencias
└── README.md           ← Este archivo
```

## Cómo correrla en tu computadora

### Paso 1 — Instalar Python (si no lo tienes)

Descargar de https://www.python.org/downloads/ (versión 3.10 o superior).

Verificar instalación:
```bash
python --version
```

### Paso 2 — Descargar el proyecto

Guarda los 5 archivos (`app.py`, `indicadores.py`, `data_sources.py`, `config.py`, `requirements.txt`) en una carpeta nueva, por ejemplo `propel-me`.

### Paso 3 — Instalar dependencias

Abre una terminal en esa carpeta y corre:

```bash
pip install -r requirements.txt
```

### Paso 4 — Lanzar la app

```bash
streamlit run app.py
```

Se abre automáticamente en `http://localhost:8501` en tu navegador.

## Cómo usarla

### Modo CSV (para pruebas con C8 o cohortes históricas)

1. En la barra lateral, escoge "Subir CSVs (pruebas)"
2. Sube `RAW_baseline.csv` y `RAW_endline.csv`
3. Da clic en "Calcular todos los indicadores"
4. Descarga el CSV de resultados o ve la tabla en pantalla

### Modo Supabase (para cohortes activas)

1. En la barra lateral, escoge "Supabase (producción)"
2. Selecciona la cohorte del dropdown
3. Da clic en "Conectar y cargar"
4. Da clic en "Calcular todos los indicadores"
5. (Opcional) Activa "Guardar resultados en Supabase" para que aparezcan en Looker

## Deploy gratis en Streamlit Community Cloud

### Paso 1 — Crear un repositorio en GitHub

1. Crear cuenta en https://github.com (si no tienes)
2. Crear un repositorio nuevo, ejemplo: `propel-me-app`
3. Subir los 5 archivos al repositorio

### Paso 2 — Conectar Streamlit Cloud

1. Ve a https://streamlit.io/cloud
2. Inicia sesión con tu cuenta de GitHub
3. Da clic en "New app"
4. Selecciona el repositorio `propel-me-app`
5. Branch: `main`
6. Main file path: `app.py`
7. Da clic en "Deploy"

En 2-3 minutos tendrás una URL pública del estilo `propel-me-app.streamlit.app`.

### Paso 3 — Configurar secretos (recomendado)

Por seguridad, las credenciales de Supabase no deberían estar hardcodeadas en `config.py` cuando el repo es público.

1. En Streamlit Cloud, da clic en tu app → "Settings" → "Secrets"
2. Pega lo siguiente:

```toml
SUPABASE_URL = "https://vnufvitjqjoiijbmzjxh.supabase.co"
SUPABASE_KEY = "tu_anon_key_aqui"
```

3. Edita `config.py` para usar los secretos:

```python
import streamlit as st
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
```

4. Sube el cambio a GitHub. La app se redepoya automáticamente.

## Crear la tabla `indicators_master` en Supabase

Si vas a guardar resultados en Supabase, primero crea la tabla. Ve al SQL editor de Supabase y corre:

```sql
create table indicators_master (
  id bigserial primary key,
  cohorte text,
  programa text,
  indicador text,
  valor numeric,
  unidad text,
  n integer,
  detalle text,
  calculado_at timestamptz default now()
);
```

## Conectar Looker Studio

1. Abre https://lookerstudio.google.com
2. "Crear" → "Fuente de datos" → buscar "PostgreSQL"
3. Datos de conexión de Supabase (revisa "Project Settings" → "Database" en Supabase para los detalles):
   - Host: `db.vnufvitjqjoiijbmzjxh.supabase.co`
   - Puerto: `5432`
   - Base de datos: `postgres`
   - Usuario: `postgres`
   - Contraseña: la del proyecto Supabase
4. Selecciona la tabla `indicators_master`
5. Crear gráficos a partir de allí (NPS por cohorte, distribución de Net AI Adoption, etc.)

## Validación

La lógica de `indicadores.py` fue validada contra el cálculo manual de la Cohorte 8 documentado en `Indicadores_calculados_C8_tablas.pdf`. Las pequeñas diferencias en N son por filtrado contra Salesforce que Melissa hace manualmente — en producción no aplica porque usamos email como llave estable.

## Próximos pasos

- **Fase 3:** asistente IA que toma la tabla maestra y genera insights interpretativos por indicador + borrador de reporte para donantes
- **Mejoras pendientes:** carga dinámica de cohortes desde Supabase, comparativos entre cohortes, panel de seguimiento bisemanal integrado
