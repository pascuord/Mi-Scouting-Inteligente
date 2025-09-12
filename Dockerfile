# Imagen base: Python 3.11 slim
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Paquetes del sistema necesarios (FAISS compila wheels, Kaleido/Plotly para exportar imágenes)
# Nota: lista algo amplia para evitar problemas headless de Kaleido/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    libglib2.0-0 libnss3 libx11-6 libxcomposite1 libxcursor1 libxdamage1 libxext6 \
    libxi6 libxtst6 libxrandr2 libasound2 libxss1 libxshmfence1 libxkbcommon0 \
    libgtk-3-0 libdrm2 libgbm1 libxcb1 libpango-1.0-0 libcairo2 fonts-liberation \
    libjpeg62-turbo zlib1g libpng16-16 libfreetype6 libopenblas0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copiamos metadatos del proyecto y lo instalamos en editable
COPY pyproject.toml /app/
RUN python -m pip install --upgrade pip setuptools wheel

# Copiamos el código
COPY src /app/src

# Chrome para Kaleido v1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
 && mkdir -p /usr/share/keyrings \
 && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /usr/share/keyrings/google.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
 && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
 && rm -rf /var/lib/apt/lists/*


# Instalamos el proyecto y dependencias
# (añade aquí lo que ya usas en el entorno)
RUN pip install -e . \
    && pip install \
       python-dotenv langgraph langchain-openai \
       plotly kaleido \
       sentence-transformers faiss-cpu polars unidecode aiohttp bs4 requests rapidfuzz \
       mplsoccer==1.2.2 Pillow>=10.3 matplotlib>=3.8 numpy>=1.26 \
       brotli lxml

# (Opcional pero recomendable) Pre-descargar el modelo de embeddings para no hacerlo en arranque
#RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

ENV HF_HOME=/data/hf
# Si tenías TRANSFORMERS_CACHE, elimínalo o déjalo sin valor


# Directorios de datos (se montarán como volumen)
RUN mkdir -p /data/raw /data/interim /data/processed/indices

# Variables de entorno por defecto (puedes sobreescribir en docker-compose o con -e)
ENV INDICES_DIR=/data/processed/indices

# Comando por defecto: arrancar el bot (puedes cambiarlo en docker-compose)
CMD [\"scouting-bot\"]
