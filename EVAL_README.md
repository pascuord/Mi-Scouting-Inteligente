# 🧪 Evaluación con Promptfoo — ScoutingInteligente

## Prerequisitos

| Requisito | Versión mínima | Verificación |
|-----------|----------------|--------------|
| **Node.js** | ≥ 18 | `node --version` |
| **Python** | ≥ 3.10 | `python --version` |
| **Paquete scouting** | editable | `pip install -e .` desde la raíz del proyecto |
| **Claves API** | — | Configuradas en `.env` (`OPENAI_API_KEY`, `GROQ_API_KEY`) |

## Ejecución

Desde la **raíz del proyecto** (donde se encuentran `promptfooconfig.yaml` y `scouting_provider.py`):

```bash
# 1. Ejecutar la evaluación completa (2 proveedores × 10 preguntas = 20 celdas)
npx promptfoo@latest eval

# 2. Visualizar los resultados en el navegador (interfaz web interactiva)
npx promptfoo@latest view

# 3. Exportar resultados a JSON para análisis externo
npx promptfoo@latest eval -o results.json

# 4. Exportar resultados a CSV
npx promptfoo@latest eval -o results.csv
```

## Estructura de archivos

```
ScoutingInteligente/
├── scouting_provider.py      ← Proveedor Python (call_api → pipeline.invoke)
├── promptfooconfig.yaml      ← Matriz de orquestación (providers × tests)
├── EVAL_README.md            ← Este documento
└── src/scouting/agents/
    ├── common.py             ← build_global_llm() — fábrica de LLM
    └── pipeline.py           ← pipeline.invoke() — grafo multiagente
```

## Notas técnicas

- **Concurrencia**: Promptfoo ejecuta las celdas de la matriz de forma concurrente por defecto. Para limitar la concurrencia, usar la flag `--max-concurrency N`.
- **Caché**: Promptfoo cachea resultados por defecto. Para forzar re-evaluación completa: `npx promptfoo@latest eval --no-cache`.
- **Variables de entorno**: El proveedor Python (`scouting_provider.py`) inyecta `LLM_PROVIDER` y el modelo correspondiente en `os.environ` antes de cada invocación, garantizando que `build_global_llm()` construya el LLM correcto.
