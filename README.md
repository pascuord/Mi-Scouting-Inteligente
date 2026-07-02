# ScoutingInteligenteBot  
Sistema multiagente basado en RAG para scouting futbolístico  


<p align="center">
    <img src="figuras/Logo.PNG" alt="Logo del proyecto" width="400">
</p>

---

## 📌 Descripción general
Este proyecto implementa un **bot de Telegram** para *scouting* futbolístico, capaz de responder consultas en lenguaje natural sobre una base de 14476 jugadores (porteros: 1444, jugadores: 13032).  
El sistema se basa en una **arquitectura multiagente orquestada en LangGraph**, que combina recuperación de información con generación aumentada (**RAG**).  

El pipeline completo:
1. Recupera candidatos (FAISS + embeddings).  
2. Aplica filtros restrictivos (edad, valor de mercado, posición, contrato…).  
3. Evalúa y puntúa candidatos en métricas clave derivadas de la query.  
4. Explica los resultados en lenguaje natural.  
5. Devuelve gráficos comparativos y perfiles individuales.  

---

## 📚 Documentación Adicional

Para facilitar la evaluación académica y el mantenimiento técnico del proyecto, se han incorporado las siguientes guías detalladas:

*   **[📐 Especificación Arquitectónica (ARCHITECTURE.md)](ARCHITECTURE.md)**: Detalle del flujo multiagente (LangGraph), formulación matemática del score, espacio vectorial RAG (FAISS/E5) y estructura del pipeline de datos.
*   **[🚀 Guía de Despliegue (DEPLOYMENT.md)](DEPLOYMENT.md)**: Instrucciones paso a paso para la instalación de dependencias, configuración de entornos (`.env`) y arranque del bot y del módulo ETL.
*   **[🤝 Guía de Contribución (CONTRIBUTING.md)](CONTRIBUTING.md)**: Estándares de calidad de código, formato de commits y flujo de trabajo para colaborar en el repositorio.

---

## 🗂️ Estructura del repositorio

```text
proyectosjg/
├── data/                 # Datos brutos y procesados
│   ├── processed/
│   │   ├── merged/       # Bases combinadas (jugadores / porteros)
│   │   └── indices/      # Índices FAISS + metadata
├── src/                  # Código fuente
│   ├── scouting/
│   │   ├── etl/          # Scripts ETL (extracción, merge, indexado)
│   │   ├── agents/       # Implementación de agentes 0–4
│   │   └── telegram/     # Entrypoint del bot
├── figuras/              # Imágenes usadas en README
├── .env.example          # Ejemplo de variables de entorno
├── docker-compose.yml    # Orquestación de servicios
├── Dockerfile            # Imagen base
├── pyproject.toml        # Dependencias
├── ARCHITECTURE.md       # Detalle teórico, matemático y de flujos (Nuevo)
├── DEPLOYMENT.md         # Guía de instalación y despliegue (Nuevo)
├── CONTRIBUTING.md       # Guías de contribución y Git workflow (Nuevo)
└── README.md             # Este archivo
```

---

## 🐳 Despliegue y Garantía de Reproducibilidad con Docker

Para garantizar la **reproducibilidad académica y técnica** de este Trabajo Fin de Máster (TFM), todo el entorno del sistema de scouting está encapsulado mediante contenedores utilizando **Docker Compose**. 

### 🛡️ ¿Cómo garantiza Docker la reproducibilidad?
1. **Entorno Aislado e Idéntico**: Se utiliza una imagen base estandarizada de Python 3.11-slim, eliminando discrepancias debidas al sistema operativo anfitrión (Linux, macOS o Windows/WSL2).
2. **Compilación de Dependencias Complejas**: Librerías como `FAISS` (para indexación y búsqueda vectorial rápida) se compilan y configuran dentro del contenedor sin necesidad de configurar compiladores C++ locales.
3. **Generación Automatizada de Gráficos (Chrome Headless)**: Los módulos de generación visual (radares comparativos y diagramas pizza mediante `Plotly` y `Kaleido`) requieren binarios del sistema de Google Chrome. El `Dockerfile` instala automáticamente Chrome estable y todas sus dependencias gráficas (`libnss3`, `libxss1`, etc.), asegurando que los reportes visuales se generen correctamente en entornos headless sin configuraciones manuales adicionales.
4. **Persistencia Controlada (Volúmenes)**: Se definen rutas mapeadas exactas para la persistencia del histórico del bot (`last_update_id.txt`), datos de jugadores indexados e históricos de caché, garantizando que el estado del sistema persista entre reinicios.

---

### 📋 Requisitos Previos
Antes de iniciar el despliegue, asegúrate de cumplir con lo siguiente:
- **Docker Engine** (`v24.0` o superior) e **instalación de Docker Compose** (`v2.20` o superior).
- Claves de APIs y tokens necesarios (se configuran en el `.env`):
  - `TELEGRAM_BOT_TOKEN` (obtenido desde `@BotFather`).
  - `OPENAI_API_KEY` (si se usa OpenAI) o `GROQ_API_KEY` (si se usa Groq).

---

### 🚀 Guía de Puesta en Marcha Paso a Paso

#### 1. Clonación del Repositorio e Inicialización del Entorno
Clona el proyecto y crea tu archivo de configuración `.env` a partir de la plantilla predeterminada:
```bash
git clone https://github.com/Scouting-Inteligente-Bot/ScoutingInteligenteBot.git
cd ScoutingInteligenteBot
cp .env.example .env
```
> [!TIP]
> Abre el archivo `.env` en un editor de texto y completa las credenciales requeridas. Para obtener detalles adicionales sobre cada variable de entorno, consulta la [Guía de Despliegue Detallada (DEPLOYMENT.md)](DEPLOYMENT.md#-configuracion-del-entorno-env).

#### 2. Construcción del Contenedor
Descarga las imágenes base y construye el entorno local de dependencias:
```bash
docker compose build --no-cache --pull
```

#### 3. Carga y Procesamiento de Datos (Flujo ETL & Indexación)
Para que el bot multiagente pueda recuperar candidatos mediante RAG, se necesitan los datos e índices vectoriales en la carpeta física de persistencia. Tienes dos opciones para levantarlos:

* **Opción A (Recomendada para reproducibilidad total): Ejecución del Pipeline ETL Completo**
  Si deseas realizar toda la extracción, limpieza, consolidación e indexación vectorial desde las fuentes originales:
  ```bash
  docker compose run --rm etl python -m scouting.etl.main_etl
  ```
  > [!IMPORTANT]
  > Para extraer datos actualizados desde FotMob, debes actualizar de forma manual la variable `X_MAS_TOKEN` en tu `.env`. Ver detalles sobre [cómo obtener el token de FotMob](#obtencion-del-token-de-fotmob-para-recolectar-datos).
  >
  > *Atajos del script ETL:* Puedes saltar fases añadiendo banderas al script. Por ejemplo, si deseas omitir la descarga externa de Fotmob y Transfermarkt porque ya tienes los `.json` en bruto en `data/` y solo quieres hacer el merge e indexado:
  > ```bash
  > docker compose run --rm etl python -m scouting.etl.main_etl --skip-fotmob --skip-tm
  > ```

* **Opción B (Indexación Directa): Generación de Índices FAISS sobre Datos Existentes**
  Si ya tienes los archivos consolidados de base de datos (`db_jugadores.json` y `db_porteros.json`) bajo el directorio `data_local/processed/merged/`, puedes ejecutar directamente la vectorización para crear los índices FAISS:
  ```bash
  docker compose run --rm etl python -m scouting.etl.vector_store_indexing
  ```
  
  **Estructura de archivos esperada en el host para esta fase:**
  ```text
  data/
  └─ processed/
     └─ indices/
        └─ current/
           ├─ faiss_jugadores.index      # Base vectorial de jugadores
           ├─ faiss_porteros.index       # Base vectorial de porteros
           ├─ metadata_jugadores.json    # Metadatos del RAG
           └─ metadata_porteros.json     # Metadatos del RAG
  ```

#### 4. Lanzamiento del Bot de Telegram
Una vez completado el procesamiento/indexado y con los archivos en su lugar, levanta el servicio del bot de Telegram en segundo plano:
```bash
docker compose up -d bot
```

Comprueba el correcto arranque del bot y visualiza los logs de ejecución en tiempo real:
```bash
docker compose logs -f bot
```

---

### 🔑 Obtención del Token de FotMob para recolectar datos
Si vas a realizar la recolección completa en el paso ETL (Opción A):
1. Entra en [FotMob](https://www.fotmob.com) desde tu navegador web.
2. Abre las herramientas de desarrollo de tu navegador (`F12` o Clic Derecho -> Inspeccionar).
3. Ve a la pestaña **Network** (Red) y filtra los resultados por **Fetch/XHR**.
4. Realiza alguna acción que consulte métricas de un jugador (ej: ver su perfil).
5. Selecciona la petición de red (ej: `profile`) y copia el valor del encabezado de solicitud `x-mas` (o `X-Mas`).
6. Pégalo en tu archivo `.env` como `X_MAS_TOKEN=tu_valor_aqui` (sin comillas).

---

### 📊 Flujo del Pipeline ETL
El siguiente diagrama detalla cómo se extraen y fusionan los datos de **FotMob** (estadísticas deportivas de rendimiento) y **Transfermarkt** (información contractual y de mercado) para alimentar los índices del RAG:

<p align="center">
  <img src="figuras/diagrama.png" alt="ETL pipeline" width="700"/>
</p>

---


## 🧩 Arquitectura multiagente

El corazón del sistema está en la carpeta `src/scouting/agents/`, donde cada archivo implementa un **agente especializado** dentro del pipeline orquestado en **LangGraph**.  

Estructura:

```text
src/scouting/agents/
├── agent0.py        # Vector Retriever
├── agent1.py        # Hard Filter
├── agent2.py        # Score Evaluator
├── agent3.py        # Explanation (LLM)
├── agent4.py        # Graph Comparison
├── common.py        # Funciones y utilidades compartidas
├── pipeline.py      # Definición del grafo multiagente con LangGraph
└── telegram_bot.py  # Interfaz de entrada/salida con Telegram
```

### 🧠 Agente 0 — Vector Retriever (`agent0.py`)

**Función principal:**  
Recupera los *k* jugadores más cercanos a la *query* en el espacio de embeddings y devuelve un **DataFrame de Polars** con toda la información estructurada.

**Características clave:**
- Usa el modelo `intfloat/multilingual-e5-base` (SentenceTransformers).
- Busca en índices **FAISS** separados para jugadores y porteros.
- Detecta automáticamente si la consulta es de *jugadores de campo* o *porteros* (palabras clave como “portero”, “goalkeeper”…).
- Normaliza los metadatos complejos (`estadísticas`, `rasgos`, `contratos`) en formato JSON seguro para Polars.
- Recupera por defecto los **3500 más cercanos**, configurables en `top_k`.

**Entradas:**  
- `query_norm`: texto libre del usuario normalizado y traducido a español si fuera necesario.  
- `tipo`: (opcional) forzar búsqueda en `jugador` o `portero`.

**Salidas:**  
- `pl.DataFrame` con los jugadores más cercanos.  
- `tipo` utilizado finalmente.

**Ejemplo de uso en el pipeline:**
```python
from scouting.agents.agent0 import Agente0VectorRetriever

agent0 = Agente0VectorRetriever(top_k=3500)
df, tipo = agent0.recuperar("extremo joven habilidoso")
```
Este DataFrame es la base para los siguientes agentes: primero se filtra (Agente 1), después se puntúa (Agente 2).

- **Agente 1 – Hard Filter**
### 🧱 Agente 1 — Hard Filter (`agent1.py`)

**Función principal:**  
Aplica **filtros restrictivos** derivados de la query para reducir el universo devuelto por el Agente 0 a los candidatos que cumplen las condiciones explícitas.

**Características clave:**
- **Parsing robusto** de la query (normaliza tildes, símbolos y alias).
- Filtros soportados:
  - **Edad** (rangos, `<`, `≤`, `sub-23`, “joven”, “veterano”…).
  - **Valor de mercado** (euros, `k`, `M`, “millones”, “barato/asequible”…).
  - **Posición** (mapa amplio de sinónimos: *extremo/winger, pivote, central, lateral…* + laterales/alas por banda).
  - **Pie dominante** (zurdo/diestro/ambidiestro).
  - **Altura** (`m` o `cm`, además de descriptores “alto/bajo”).
  - **Contrato** (años restantes: “menos de 2 años de contrato”).
  - **Nacionalidad** (gentilicios y alias normalizados a país canónico).
  - **Liga explícita** (alias → nombre canónico) y **país de la liga** (con reconciliación liga↔país).
- **Normalización de columnas** para Polars (renombra si vienen como `posicion/position`, `valor_mercado`, etc.).
- Convierte campos complejos (p. ej. `other_positions`) desde *JSON/string → list[str]*.
- Logs `DEBUG` opcionales para trazar qué filtros se aplicaron y cómo afectaron al tamaño del DF.

**Entradas:**  
- `df_pre_filtrado: pl.DataFrame` (salida del Agente 0).  
- `query_norm`: texto libre del usuario normalizado y traducido a español si fuera necesario.  
- `tipo: "jugador" | "portero"`.

**Salidas:**  
- `pl.DataFrame` filtrado (mismo esquema, menos filas).  
- `tipo` (propagado).

**Ejemplo de uso en el pipeline:**
```python
from scouting.agents.agent1 import Agente1HardFilter

a1 = Agente1HardFilter()
df_filtrado, tipo = a1.filtrar(df_pre, "extremo izquierdo sub23, zurdo, < 2M, menos de 2 años de contrato", "jugador")
```
El resultado queda listo para el Agente 2, que calculará el scoring sobre este subconjunto ya depurado.

### 📊 Agente 2 — Score Evaluator (`agent2.py`)

**Función principal**  
Selecciona **8 métricas clave** alineadas con la *query* y calcula un **score final por jugador/portero**, ajustado por **minutos** y **nivel de liga**. Devuelve el **Top-3** ordenado y un DF con esos jugadores.

**Cómo decide las 8 métricas**
- Combina **dos señales**:
  1) **Intents semánticos** (p. ej., *desborde, centros, finalización, duelos, presión…* / para GK: *paradas, juego aéreo, salida de balón…*) mapeados a métricas con pesos.  
  2) **Similitud por embeddings** entre la query y las **descripciones de cada estadística**.
- Fusión ponderada (intents 70% + embeddings 30%), limpieza de **métricas redundantes/conflictivas** (p. ej., *Duels won* vs *Duels won %*), y refuerzo de **bloques** si la query lo sugiere (Shooting/Passing/Possession/Defending).
- Si la query menciona explícitos como “regate”, “centros”, “duelos” o “gol”, estas familias reciben **boost** y entran antes en los 8 *slots*.

**Tratamiento de minutos**
- Filtro mínimo por minutos (por defecto: **≥500** jugadores, **≥0** porteros; configurable desde la query, p. ej. “sin restricción de minutos” o “≥800 min”).  
- Si el jugador tiene **< 750 min**, se **prioriza per90** en el cómputo del score.

**Cálculo del score por métrica**
- Para cada métrica seleccionada:  
  - Combina **percentil**, **percentil/90**, **valor** y **valor/90** (más peso al percentil; si <750 min, más peso a **/90**).  
  - Métricas donde **menor es mejor** (*Dispossessed, Fouls committed, Dribbled past, Goals conceded…*) ignoran el valor bruto.
- El **score total** es la suma de los ponderados por los **pesos de las 8 métricas** (renormalizados a 1).

**Ajuste por liga**
- Multiplica el score por un **coeficiente de liga** (Big-5 ≈ 1.00; ligas menores < 1) para **equiparar dificultad competitiva**.

**Entradas:**  
- `df_filtrado: pl.DataFrame` (salida del Agente 1).  
- `query_norm`: texto libre del usuario normalizado y traducido a español si fuera necesario.  
- `tipo: "jugador" | "portero"`.

**Salidas**
- `resultados[:3]` → lista de 3 dicts con: `score`, `metricas_clave`, `detalle` por métrica, `minutes_real`, `nivel_liga`, rasgos, etc.  
- `df_top3` → DataFrame Polars con las filas de los 3 mejores.

**Ejemplo de uso en el pipeline**
```python
from scouting.agents.agent2 import ScoreEvaluatorAgent

a2 = ScoreEvaluatorAgent()
top3, df_top3 = a2.score_dataframe(df_filtrado, "extremo izquierdo habilidoso con regate y gol", "jugador")
```
Esta salida alimenta al Agente 3 (explicación en lenguaje natural) y al Agente 4 (gráficos).

### 🧠 Agente 3 — Explanation (`agent3.py`)

**Función principal**  
Genera una **explicación profesional en lenguaje natural** (idioma de la query) que justifica por qué los 3 jugadores del Agente 2 encajan con la búsqueda. Usa un **system prompt asistente experto en análisis futbolístico** + *few-shot* y compone un texto con datos clave (edad, posición, minutos, pie, altura, valor, contrato, score) y **lectura de métricas** (percentil y por-90).

**Entradas**
- `query` (str): petición del usuario sin normalizar y en idioma original.
- `resultados` (List[dict]): salida del Agente 2 con `metricas_clave`, `detalle` por métrica, `minutes_real`, `nivel_liga`, `liga`/`liga_stats`/`temporada_stats`, `años_contrato`, `rasgos`, etc.

**Cómo construye la explicación**
- **Plantilla de sistema** con reglas de estilo y exactitud (no reasignar posición, interpretar métricas “negativas”: *Dispossessed*, *Dribbled past*, *Fouls committed*, y que un percentil alto siempre es bueno).
- **Formateo previo**: ordena métricas por **peso**, muestra percentiles y **prioriza per90** si `minutes_real < 750`.  
- **Contrato**: traduce años restantes a señal de **disponibilidad/coste**.  
- **Liga vs. liga_stats**: añade nota cuando las estadísticas provienen de otra liga/temporada.  
- **Rasgos**: resalta los que son ≥ 75 como fortalezas.

**Salida**
- `str` con un informe claro (3 bloques, uno por jugador) listo para enviar por Telegram.

**Ejemplo de uso en el pipeline**
```python
from scouting.agents.agent3 import Agente3Explanation

a3 = Agente3Explanation(model="gpt-4o-mini", lang="es")
texto = a3.explicar_resultados(query, resultados_top3)
# → cadena con el análisis para Telegram
```
**Notas de implementación**
- Modelo por defecto: `gpt-4o-mini`, `temperature=0.35`.
- No inventa campos: si faltan datos en `resultados`, se omiten.
- Mantiene la posición **principal**  tal cual; si el encaje es por posición secundaria, lo advierte.

### 📊 Agente 4 — Graph Comparison (`agent4.py`)

**Función principal**  
Genera las **visualizaciones** del sistema:
1) **Dos radares Plotly** (percentil total y percentil por 90’) para los 3 candidatos del Agente 2.  
2) **Collage de player radars de perfil** (MPLSoccer) por bloques estadísticos, con reglas que **adaptan las métricas** al rol (ofensivo / medio / defensa / portero).

**Entradas**
- `resultados` (List[dict], tamaño 3): salida del Agente 2 con `metricas_clave` y `detalle[stat].raw` (incluye `percentile` y `percentile_per90`), `nombre`, `main_position`, `estadísticas`, `Minutes`, `Rating`, etc.
- `out_dir` (str): carpeta donde guardar imágenes.

**Qué produce**
- `graph_comparison(resultados) -> (fig1, fig2)`: dos `go.Figure` (radares de **percentiles totales** y **per90**).
- `build_radar_collage(resultados, out_dir, filename="radars_collage.png") -> str`: PNG con ambos radares maquetados y **leyenda grande** a la derecha.
- `build_pizza_collage(resultados, out_dir, filename_collage="profiles_comparison.png", layout="column") -> (jpg_collage, [png_individuales])`:  
  - 1 **collage** (JPG) con 3 player radars (uno por jugador)  
  - y, opcionalmente, **PNG individuales** por jugador.

**Detalles relevantes**
- **Per90 inteligente**: si `Minutes` < umbral (por defecto 1000), la pizza usa `percentile_per90`.  
- **Bloques y colores**  
  - Jugadores: `Shooting` (azul), `Passing` (naranja), `Possession` (verde agua), `Defending` (rojo).  
  - Porteros: `Goalkeeping` (azul) y `Distribution` (naranja).  
- **Selección de métricas** por bloque:
  - Se cubren listas fijas (p. ej., `Successful crosses`, `xG excl. penalty`, `Duels won %`, `High claims`, …).  
  - En **Possession** se alterna `Touches in opposition box` (ofensivos) o `Touches` (resto).  
  - En **Defending** se añaden extras por rol (p. ej., `Dribbled past` para laterales/CM; `Blocked scoring attempt` para CB/DM; `Possession won final 3rd` para ofensivos).
- **Robustez I/O**: soporta `estadísticas` como `dict` o `str` (JSON / dict-like). Limita tamaño final (**máx. 3840 px**) para envío en Telegram.
- **Dependencias opcionales**: si `mplsoccer`/`Pillow` no están, se **omiten pizzas** y solo se generan radares Plotly.

**Ejemplo de uso en el pipeline**
```python
from scouting.agents.agent4 import GraphComparisonAgent

a4 = GraphComparisonAgent(per90_minutes_threshold=1000)

# 1) Radares separados (si quieres mostrarlos en notebook o exportarlos tú)
fig_total, fig_per90 = a4.graph_comparison(resultados_top3)

# 2) Collage compacto con ambos radares (PNG listo para Telegram)
path_radars = a4.build_radar_collage(resultados_top3, out_dir="/data/figs")

# 3) Player radars de perfil jugadores (collage JPG + PNG individuales)
collage_fp, pngs = a4.build_pizza_collage(resultados_top3, out_dir="/data/figs", layout="column")
```
**Consejos**
- Si el radar sale con muchas etiquetas, reduce metricas_clave en el Agente 2 (p. ej., top-6), si se quieren más también se puede ampliar.
- Para README/Telegram, el collage para los radares comparativos es más legible que dos imágenes separadas.

### 🧰 Utilidades comunes (`common.py`)

Pequeño módulo de **infraestructura** compartida:

- **Carga de entorno**  
  `load_dotenv()` permite leer variables desde `.env` sin esfuerzo.

- **Logging JSON a stdout**  
  Configura `logging` en **stdout** y expone `jlog(event, **kw)` para emitir líneas JSON (útiles en Docker/CloudWatch).
  ```python
  from scouting.agents.common import jlog
  jlog("agent0_init", base="/data/processed/indices/current")
  # => {"ts":"2025-09-11T10:45:12Z","event":"agent0_init","base":"..."}
    ```

**Helpers de entorno (valores por defecto seguros)**
- `env_str(key, default="")` → `str`
- `env_int(key, default)` → `int` con fallback
- `get_indices_dir()` → `data/processed/indices/current` por defecto
- `get_openai_model_supervisor()` → `"gpt-4o-mini"`
- `get_openai_key()` y `get_telegram_token()` → extraen **secrets** del entorno

**Uso típico**
```python
from scouting.agents.common import (
  jlog, get_indices_dir, get_openai_model_supervisor, get_telegram_token
)

indices_dir = get_indices_dir()
model_sup   = get_openai_model_supervisor()
jlog("startup", indices_dir=indices_dir, model=model_sup)
```
**Ventaja**
- Centraliza config y logs estructurados → mismos defaults en local, Docker y CI/CD, y trazas limpias para depurar el pipeline.

### ⚙️ Pipeline (`pipeline.py`)

Define el grafo LangGraph que conecta los agentes y gestiona la salida a Telegram.

#### Flujo principal
1. **Supervisor**  
   - Clasifica la consulta (`ok`/`fin`), detecta idioma y normaliza a español.  
   - Si no es scouting de fútbol → mensaje de rechazo.

2. **Agente0** → Recupera candidatos vía FAISS + tipo (`jugador`/`portero`).  
3. **Agente1** → Filtros duros (edad, valor, posiciones, pie, altura, contrato, nacionalidad, liga).  
4. **Agente2** → Selección de métricas clave (embeddings + reglas), cálculo de score ponderado (percentiles, minutos, coeficiente de liga).  
5. **Agente3** → Explicación razonada (OpenAI, idioma original).  
6. **Agente4** → Gráficos comparativos:
   - Radar collage (totales vs per90)  
   - Collage player radars (perfil por bloques)  
   - Con fallback de imagen en caso de error.  
7. **Send to Telegram** → Envía explicación y gráficos al chat.

#### Estado compartido
`PipelineState`: query, lang, tipo, df_pre_filtrado, df_filtrado, resultados, df_top3, explicacion, chart_paths, chat_id, decision.

#### Integración
```python
from scouting.pipeline import pipeline

state = pipeline.invoke({
  "query": "Extremo izquierdo sub-23 con regate y centros",
  "chat_id": "<ID_TELEGRAM>"
})
```

**Configuración**
- `OPENAI_API_KEY`, `OPENAI_MODEL_SUPERVISOR` (default: gpt-4o)
- `TELEGRAM_BOT_TOKEN` para envío real
- `KAL_CHROME_PATH` opcional (Chrome en Docker/headless)


### 🤖 Telegram bot (`telegram_bot.py`)

Maneja la **entrada/salida con Telegram** mediante *polling* y delega el procesamiento al `pipeline`.

- **Qué hace**
  - Lee el último update con `getUpdates` y usa un *offset* persistido en `/data/last_update_id.txt` para **no repetir mensajes**.
  - Extrae `chat_id` y `text`, y llama a:  
    `pipeline.invoke({"query": text, "chat_id": str(chat_id)})`.
  - Requiere `TELEGRAM_BOT_TOKEN` en `.env`.

- **Ejecución**
```bash
  # Servicio en Docker (recomendado)
  docker compose up -d bot
  docker compose logs -f bot

  # O directo (si tienes entorno local con deps)
  python -m scouting.agents.telegram_bot
```
**Notas**
- Si no hay `BOT_TOKEN`, el bot no se inicia y lo avisa por consola.
- El archivo `/data/last_update_id.txt` se guarda en el volumen `./data:/data` para persistencia entre reinicios.
- El envío al usuario lo hace el propio `pipeline` en su nodo `nodo_send_to_telegram` (texto + imágenes).

El flujo multiagente completo —desde la query hasta la explicación y gráficos enviados a Telegram— sigue este grafo:

<p align="center">
  <img src="figuras/grafo_pipeline_compacto.png" alt="Pipeline LangGraph" width="700"/>
</p>

---

## 🖼️ Demo del bot
Ejemplo real de interacción vía Telegram con el bot de scouting:

<p align="center">
  <img src="figuras/telegram_output.png" alt="Interfaz real de Telegram con la explicación del Agente 3" width="700"/>
</p>

<p align="center">
  <img src="figuras/radar_comparativo.png" alt="Radar comparativo" width="700"/>
</p>

<p align="center">
  <img src="figuras/player_radars.png" alt="Radar perfiles" width="700"/>
</p>

En la demo se observa cómo una consulta en lenguaje natural se transforma en:
1. **Explicación razonada** de los 3 jugadores más relevantes.  
2. **Gráficos comparativos** (radar y perfiles tipo player radar) generados automáticamente.  

---

## 🛠️ Resolución de Problemas (Troubleshooting)

### 1. Error de Renderizado de Gráficos (Kaleido / Chrome headless)
Si los logs del bot muestran errores al generar los archivos PNG de los radares comparativos:
- Comprueba si el ejecutable de Chrome está en la ruta correcta en el contenedor:
  ```bash
  docker compose exec bot sh -lc 'which google-chrome-stable'
  ```
- El `Dockerfile` ya incluye la instalación automatizada del navegador y las librerías necesarias. Si realizas cambios en el entorno de visualización, asegúrate de reconstruir la imagen con:
  ```bash
  docker compose build --no-cache
  ```

### 2. El Bot de Telegram responde dos veces o repite mensajes
- El bot utiliza *polling* de Telegram con offset de lectura.
- El ID del último mensaje procesado se guarda en `/data/last_update_id.txt`.
- Asegúrate de que el volumen `./data:/data` tiene permisos de escritura en tu sistema operativo host, permitiendo al contenedor guardar este archivo de control.

### 3. Error `FileNotFoundError` en los Índices FAISS
- Si al arrancar el bot muestra que no encuentra los archivos `faiss_jugadores.index`, verifica que hayas ejecutado el indexador (`scouting.etl.vector_store_indexing`) o que hayas copiado correctamente los datos preexistentes en la carpeta local `data/processed/indices/current/`.

### 4. WSL / Docker Desktop colgado (en Windows)
Si experimentas bloqueos en la ejecución de contenedores:
```bash 
wsl --shutdown
```
Y vuelve a abrir Docker Desktop.

---

## 🔒 Seguridad
- El archivo `.env` con credenciales privadas y la carpeta de datos en bruto/procesados `data/` están excluidos del control de versiones en el `.gitignore`.