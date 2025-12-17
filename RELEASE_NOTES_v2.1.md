# v2.1

## Cambios principales

- Ajustes en `Dockerfile` y `docker-compose` para montar la nueva imagen; los cambios en ETL/agentes y guardado se aplican al correr el bot.
- ETL actualizada para obtener datos más recientes:
  - **FotMob:** temporada de stats actualizada.
  - **Transfermarkt:** valores actuales, situación contractual, cambios de posición/club según temporada.
- **Transfermarkt ETL optimizada:**
  - Datos de perfil resueltos con **1 petición HTML + 2 llamadas CEAPI**.
  - Eliminación de sleeps y sustitución por **`RateLimiter` global**.
  - Tiempo por liga reducido de **~8 horas a <20 minutos** (parámetros configurables por CLI).
- Aumento de cobertura por usar los clubes de la temporada objetivo:
  - **Total:** 14.476 jugadores (**Porteros:** 1.444, **Jugadores:** 13.032).
- Ajuste de umbral de minutos para percentiles `per90` (más flexible al inicio de temporada; irá subiendo conforme avance).

## Ajustes en agentes

- **Agente 1:** mejoras en nacionalidades y patrones (precio, edad, posición, liga).
- **Agente 2:** ajuste de mínimos de minutos para score y criterio de `percentile_per90` vs `percentile`.
- **Agente 3:** cambio de modelo de `gpt-4o-mini` a `gpt-4o` (coste asumible tras bajadas de precio).
- **Agente 4:** ajuste de minutos para mostrar `percentile_per90` vs `percentile`.

## Siguientes posibles cambios

- Control de acceso por `chat_id` (permitir solo IDs autorizados; pensado para “pizarritas”).
- Manejo de casos de jugadores que cambian de liga/club a mitad de temporada (fallback 0-0 → 0-1 según minutos / ligas no-copa).
- Módulo de “jugadores similares a X” (distancias en percentiles y nuevo pipeline).
