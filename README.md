# Scouting Bot (Telegram + LangGraph)

Bot de scouting de fútbol que:
- Recupera candidatos vía FAISS + SentenceTransformers
- Filtra (edad, valor, posición, altura, etc.)
- Puntúa en base a métrica más cercanas a la query
- Explica y justifica los candidatos obtenidos y los envia a bot de Telegram
- Envía comparativas **PNG** (Plotly + Kaleido) a bot de Telegram

## Requisitos

- Docker Desktop (Windows: WSL2 habilitado)
- Claves:
  - `OPENAI_API_KEY`
  - `TELEGRAM_BOT_TOKEN`

## Configuración rápida

1. Clona el repo y copia el entorno:
   ```bash
   cp .env.example .env
   # edita .env con tus claves

2. Estructura de datos (no versionada):
    data/
    └─ processed/
    ├─ merged/
    │  ├─ db_jugadores.json
    │  └─ db_porteros.json
    └─ indices/
        └─ current/  # se rellena con FAISS + metadata

3. Construye imágenes:
    ```bash
    docker compose build --no-cache --pull

## ETL (Collect + merge + Indexado)
    Se generan las bases de datos de jugadores de fotmob y de transfermarkt.

### Collect
    En esta fase del ETL se recolectan los datos de las distintas bases, en nuestro caso se usa Fotmob para la extracción de estadísticas de los jugadores y
    transfermarkt para información contractual, trayectoria, históricos y valor del jugador

    Para generar la de fotmob hacemos: 
    
    ```bash
    docker compose run --rm etl python -m scouting.etl.collect_fotmob
    
    Para transfermarkt:
    
    ```bash
    docker compose run --rm etl python -m scouting.etl.collect_transfermarkt

### Merge
    Para poder usar estos datos, tenemos hacer el merge de estas dos bases, para tener nuestra db combinada y separa en jugadores y porteros:


    ```bash
    docker compose run --rm etl python -m scouting.etl.merge


### Indexado (ETL)
    Genera FAISS y metadatos desde data/processed/merged hacia data/processed/indices/current:
    ```bash
    docker compose run --rm etl python -m scouting.etl.vector_store_indexing

    Salida esperada:
        data/processed/indices/current/
            faiss_jugadores.index
            faiss_porteros.index
            metadata_jugadores.json
            metadata_porteros.json

### Main_etl
    Aqui tenemos la ejecución del main_etl.py completo, aunque con algunos atajos por si no queremos ejecutar todo 
    ```bash
    docker compose run --rm etl python -m scouting.etl.main_etl.py

    Tenemos estos 3 atajos para añadir al comando previo por si quisieramos saltarnos alguna fase: --skip-fotmob --skip-tm --skip-merge podemos saltarnos la recolección de fotmob o la de transfermarkt, podmeos saltarnos estas y además su merge y pasar directo al indexado, o bien podemos hacerlo entero.   
## Ejecutar el bot
    ```bash
    docker compose up -d bot
    docker compose logs -f bot
    
    + El bot usa polling con offset, guardado en /data/last_update_id.txt.

    + En Telegram, envía consultas como:

    > Delantero centro tanque, alto, buen rematador, experimentado, < 2 millones

## Variables de Entorno

    + OPENAI_API_KEY — clave de OpenAI
    + TELEGRAM_BOT_TOKEN — token del bot
    + OPENAI_MODEL_SUPERVISOR — default: gpt-4o-mini
    + INDICES_DIR — default: /data/processed/indices/current
    + KAL_CHROME_PATH — default: /usr/bin/google-chrome-stable (necesario para PNG)

## Troubleshooting
    + No genera PNG / error Kaleido
    Asegúrate de que el contenedor bot tiene Chrome:
    ```bash
    docker compose exec bot sh -lc 'which google-chrome-stable || which google-chrome || which chromium || which chromium-browser'

    Si no existe, reconstruye la imagen del bot con el bloque de instalación de Chrome en su Dockerfile.

    + El bot repite el mismo mensaje
    Comprueba que existe /data/last_update_id.txt y que el volumen ./data:/data está montado.

    + No filtra nada
    Verifica que metadata_*.json tengan estructura con info completo (posición, pie, altura, valor, contrato…).

    + WSL/Engine cuelga
    Reinicia Docker Desktop y WSL:
    wsl --shutdown y vuelve a abrir Docker Desktop.

## Seguridad y tamaño
    + No commitees .env ni data/ (índices grandes).
    + Si necesitas versionar datasets, usa Git LFS o almacén externo.

