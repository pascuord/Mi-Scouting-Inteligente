"""
scouting_provider.py — Proveedor personalizado de Promptfoo para el pipeline
multiagente de ScoutingInteligente.

Promptfoo invoca `call_api(prompt, options, context)` para cada celda de la
matriz (proveedor × pregunta).  Este módulo:

  1. Inyecta las variables de entorno necesarias (LLM_PROVIDER, modelo)
     según la configuración declarada en promptfooconfig.yaml.
  2. Recarga los módulos `common` y `pipeline` para que `build_global_llm()`
     construya el LLM correcto en cada ejecución.
  3. Invoca `pipeline.invoke()` y consolida la salida (explicación + nombres
     de candidatos) en la clave "output" que Promptfoo espera.
"""

from __future__ import annotations

import importlib
import os
import sys
import time

# ── Asegurar que el directorio src está en PYTHONPATH ──────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Punto de entrada requerido por Promptfoo (Python provider).

    Parameters
    ----------
    prompt : str
        Pregunta de scouting renderizada desde la variable ``{{pregunta}}``.
    options : dict
        Contiene ``options['config']`` con las claves ``provider`` y ``model``
        definidas en el bloque ``config`` de cada proveedor del YAML.
    context : dict
        Metadata del test case (no utilizado directamente).

    Returns
    -------
    dict
        ``{"output": "<texto consolidado>"}`` en caso de éxito, o
        ``{"error": "<mensaje>"}`` en caso de fallo.
    """
    config     = options.get("config", {})
    provider   = config.get("provider", "openai")
    model_name = config.get("model", "gpt-4o-mini")

    # ── 1. Inyectar variables de entorno ───────────────────────────────────
    os.environ["LLM_PROVIDER"] = provider

    if provider == "openai":
        os.environ["OPENAI_MODEL_SUPERVISOR"] = model_name
    elif provider == "groq":
        os.environ["GROQ_MODEL_SUPERVISOR"] = model_name

    # ── 2. Recargar módulos para que build_global_llm() recoja el nuevo env
    import scouting.agents.common   as _common
    import scouting.agents.pipeline as _pipeline

    importlib.reload(_common)
    importlib.reload(_pipeline)

    # ── 3. Invocar el pipeline ─────────────────────────────────────────────
    try:
        start = time.time()
        state = _pipeline.pipeline.invoke({
            "query":   prompt,
            "chat_id": "eval_promptfoo",
        })
        latencia = round(time.time() - start, 2)

        # Extraer campos del state resultante
        explicacion = state.get("explicacion", "ERROR: Sin respuesta")
        candidatos  = [
            r["nombre"] for r in state.get("resultados", []) if "nombre" in r
        ]

        # Consolidar en una sola cadena de texto
        salida_partes = [
            explicacion,
            "",
            "---",
            f"Candidatos: {', '.join(candidatos) if candidatos else 'Ninguno'}",
            f"Latencia: {latencia}s | Provider: {provider} | Model: {model_name}",
        ]

        return {"output": "\n".join(salida_partes)}

    except Exception as exc:
        return {"error": f"[{provider}/{model_name}] {exc.__class__.__name__}: {exc}"}
