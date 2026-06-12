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
  4. Captura tokens y coste económico para que Promptfoo los muestre en la
     tabla comparativa.
"""

from __future__ import annotations

import importlib
import os
import sys
import time

# ── Forzar uso de CPU para evitar CUDA Out of Memory en Promptfoo ──────────
os.environ["CUDA_VISIBLE_DEVICES"] = ""

# ── Asegurar que el directorio src está en PYTHONPATH ──────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ── Precios por millón de tokens (USD) — actualizado junio 2026 ────────────
# Fuente: páginas de pricing de OpenAI y Groq.
# Estructura: { modelo: (precio_input_por_1M, precio_output_por_1M) }
MODEL_PRICING = {
    # OpenAI
    "gpt-4o-mini":   (0.15,   0.60),
    "gpt-5.4-mini":  (0.75,   4.50),
    "gpt-4o":        (2.50,  10.00),
    "gpt-5.5":       (5.00,  30.00),
    # Groq (modelos open-source, precios Groq API)
    "openai/gpt-oss-120b":      (0.15, 0.60),
    "llama-3.3-70b-versatile":  (0.59, 0.79),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calcula el coste en USD a partir del modelo y los tokens consumidos."""
    prices = MODEL_PRICING.get(model, (0.0, 0.0))
    input_cost  = (prompt_tokens / 1_000_000) * prices[0]
    output_cost = (completion_tokens / 1_000_000) * prices[1]
    return round(input_cost + output_cost, 6)


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
        ``{"output": "<texto>", "tokenUsage": {...}, "cost": <float>}``
        en caso de éxito, o ``{"error": "<mensaje>"}`` en caso de fallo.
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

    # ── 3. Invocar el pipeline con captura de costes ──────────────────────
    try:
        from langchain_community.callbacks.manager import get_openai_callback

        start = time.time()

        with get_openai_callback() as cb:
            state = _pipeline.pipeline.invoke({
                "query":   prompt,
                "chat_id": "eval_promptfoo",
            })

        latencia = round(time.time() - start, 2)

        # Tokens capturados por el callback de LangChain
        prompt_tokens     = cb.prompt_tokens
        completion_tokens = cb.completion_tokens
        total_tokens      = cb.total_tokens

        # Coste: si OpenAI lo reporta, lo usamos; si no, lo estimamos
        if cb.total_cost and cb.total_cost > 0:
            cost = round(cb.total_cost, 6)
        else:
            cost = _estimate_cost(model_name, prompt_tokens, completion_tokens)

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

        return {
            "output": "\n".join(salida_partes),
            "tokenUsage": {
                "total":      total_tokens,
                "prompt":     prompt_tokens,
                "completion": completion_tokens,
            },
            "cost": cost,
        }

    except Exception as exc:
        return {"error": f"[{provider}/{model_name}] {exc.__class__.__name__}: {exc}"}
