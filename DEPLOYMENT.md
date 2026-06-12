# 🚀 Guía de Despliegue e Instalación — ScoutingInteligente

Esta guía detalla los pasos necesarios para instalar, configurar y desplegar el sistema **ScoutingInteligente** en entornos locales o de contenedores (Docker). Está diseñada para que cualquier desarrollador o tribunal académico pueda levantar el proyecto desde cero.

---

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener instalado el siguiente software en tu máquina anfitriona:

| Requisito | Propósito | Versión Mínima | Comando de Verificación |
| :--- | :--- | :--- | :--- |
| **Docker & Compose** | Orquestación y ejecución de contenedores | Docker `v24+` / Compose `v2.20+` | `docker compose version` |
| **Python** (Opcional, para ejecución local) | Entorno de desarrollo y ejecución de scripts | `3.10` | `python --version` |
| **Node.js** (Opcional, para evaluación) | Ejecución del framework de evaluación Promptfoo | `18` | `node --version` |

---

## 🔌 Configuración del Entorno (`.env`)

El sistema utiliza variables de entorno para gestionar las credenciales de API, los proveedores de Modelos de Lenguaje (LLM) y las rutas de datos. 

1. Copia la plantilla de configuración en la raíz del proyecto:
   ```bash
   cp .env.example .env
   ```
2. Abre el archivo `.env` recién creado y completa los valores requeridos. A continuación se explica cada variable:

| Variable | Descripción | Valor de Ejemplo / Defecto | Obligatorio |
| :--- | :--- | :--- | :--- |
| `LLM_PROVIDER` | Proveedor de LLM activo para el pipeline. | `openai` o `groq` | Sí |
| `OPENAI_API_KEY` | Clave de API de OpenAI. Requerida si el proveedor es `openai`. | `sk-proj-...` | Condicional |
| `GROQ_API_KEY` | Clave de API de Groq. Requerida si el proveedor es `groq`. | `gsk_...` | Condicional |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram obtenido a través de `@BotFather`. | `123456:ABC-DEF...` | Sí (para bot) |
| `X_MAS_TOKEN` | Token de autenticación temporal para la API de FotMob (requerido para ETL). | *Ver instrucciones abajo* | Sí (para ETL FotMob) |
| `OPENAI_MODEL_SUPERVISOR` | Modelo de OpenAI utilizado para la supervisión y generación de textos. | `gpt-4o-mini` | No |
| `GROQ_MODEL_SUPERVISOR`| Modelo de Groq utilizado para la supervisión y generación de textos. | `llama-3.3-70b-versatile` | No |
| `INDICES_DIR` | Ruta del directorio donde se guardan los índices FAISS y metadatos. | `/data_local/processed/indices` | No (ajustado en compose) |
| `KAL_CHROME_PATH` | Ruta de ejecución de Chrome/Chromium para exportación de gráficos. | `/usr/bin/google-chrome-stable` | No (ajustado en compose) |

> [!IMPORTANT]
> **Cómo obtener el `X_MAS_TOKEN` (Requerido para actualizar FotMob):**
> 1. Accede a [FotMob](https://www.fotmob.com) en tu navegador.
> 2. Abre las Herramientas de Desarrollador (`F12` o Clic Derecho -> Inspeccionar).
> 3. Dirígete a la pestaña **Network** (Red) y filtra por **Fetch/XHR**.
> 4. Realiza alguna acción que cargue estadísticas (por ejemplo, ver el perfil de un jugador).
> 5. Busca una petición (p. ej. `profile`) y revisa los encabezados de la solicitud. Copia el valor del encabezado `x-mas` (o de la respuesta `X-Mas`).
> 6. Pégalo en tu archivo `.env` como `X_MAS_TOKEN=tu_token_aqui` (sin comillas).

---

## 🗃️ Estructura de Volúmenes y Datos (Persistencia)

Para que el bot de Telegram y el motor de búsqueda RAG funcionen, el proyecto requiere una estructura de carpetas físicas en el host que se montan como volúmenes en Docker:

```text
ScoutingInteligente/
├── data/
│   ├── raw/                  # Datos en bruto recopilados por ETL
│   ├── interim/              # Datos estructurados temporales
│   └── processed/
│       └── indices/          # Índices FAISS globales montados en contenedor
└── data_local/
    └── processed/
        ├── merged/           # Bases de datos JSON consolidadas (jugadores/porteros)
        └── indices/          # Índices FAISS locales generados
```

---

## 🐳 Despliegue con Docker Compose (Recomendado)

### Paso 1: Construir las Imágenes del Sistema
Construye la imagen base local con todas las dependencias del sistema de gráficos (Chrome, Kaleido, etc.):
```bash
docker compose build --no-cache --pull
```

### Paso 2: Ejecutar el Pipeline ETL (Carga de Datos)
Si dispones de los datos iniciales, puedes omitir la recolección externa y ejecutar únicamente el procesamiento/indexado. De lo contrario, ejecuta el flujo completo:

* **Opción A: Ejecución total del ETL (Recolección externa + Procesamiento + Indexado)**
  ```bash
  docker compose run --rm etl python -m scouting.etl.main_etl
  ```
* **Opción B: Indexado de datos existentes (Salto de ETL externa)**
  Si ya tienes los archivos `.json` en `data_local/processed/merged/`, puedes generar los índices directamente:
  ```bash
  docker compose run --rm etl python -m scouting.etl.vector_store_indexing
  ```

### Paso 3: Iniciar el Bot de Telegram
Una vez generados los índices FAISS en `data_local/processed/indices`, arranca el bot de Telegram en segundo plano:
```bash
docker compose up -d bot
```

Puedes inspeccionar los logs de ejecución en tiempo real para verificar que no haya errores de inicio:
```bash
docker compose logs -f bot
```

---

## 🧪 Ejecución de Evaluaciones Académicas (Promptfoo)

El proyecto incluye un arnés de pruebas automáticas (matriz de evaluación) usando **Promptfoo** para comparar la calidad, costes y latencias entre modelos (OpenAI vs Groq).

### Paso 1: Instalación de Dependencias Locales
Para ejecutar evaluaciones desde la máquina local, instala el paquete en modo editable:
```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate

# 2. Instalar dependencias del sistema
pip install -e .
```

### Paso 2: Ejecutar la Matriz de Pruebas
Promptfoo utiliza `npx` para descargar y ejecutar la herramienta directamente sin instalación global:
```bash
# Ejecutar evaluación
npx promptfoo@latest eval
```

### Paso 3: Visualizar Resultados en Interfaz Gráfica
Levanta el servidor local de visualización:
```bash
npx promptfoo@latest view
```
Abre tu navegador en `http://localhost:15500` para analizar la matriz comparativa de respuestas, costes y puntuaciones del juez LLM.

---

## 🛠️ Resolución de Problemas (Troubleshooting)

### 1. Error de Renderizado de Gráficos (Kaleido / Chrome headless)
Si los logs del bot muestran errores al generar los archivos PNG de los radares comparativos:
* Comprueba si el ejecutable de Chrome está en la ruta configurada en el contenedor:
  ```bash
  docker compose exec bot sh -lc 'which google-chrome-stable'
  ```
* El Dockerfile ya incluye la instalación automatizada del navegador y las librerías necesarias. Si realizas cambios en el entorno de visualización, asegúrate de reconstruir la imagen con `docker compose build --no-cache`.

### 2. El Bot de Telegram responde dos veces / Repite mensajes
* El bot utiliza *polling* de Telegram con offset de lectura.
* El ID del último mensaje procesado se guarda en `/data/last_update_id.txt`.
* Asegúrate de que el volumen `./data:/data` tiene permisos de escritura en tu sistema operativo host, permitiendo al contenedor guardar este archivo de control.

### 3. Error `FileNotFoundError` en los Índices FAISS
* Si al arrancar el bot muestra que no encuentra los archivos `faiss_jugadores.index`, verifica que hayas ejecutado el indexador (`scouting.etl.vector_store_indexing`) o que hayas copiado correctamente los datos preexistentes en la carpeta local `data_local/processed/indices`.
