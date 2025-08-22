# src/scouting/pipeline.py
from __future__ import annotations
import os
import tempfile
from typing import TypedDict, Literal

import requests
import plotly.io as pio
from langgraph.graph import StateGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Agentes
from scouting.agents.agent0 import Agente0VectorRetriever
from scouting.agents.agent1 import Agente1HardFilter
from scouting.agents.agent2 import ScoreEvaluatorAgent
from scouting.agents.agent3 import Agente3Explanation
from scouting.agents.agent4 import GraphComparisonAgent


# ================== ENV & KALEIDO ==================
load_dotenv()  # lee .env en la raíz
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_MODEL_SUPERVISOR = os.getenv("OPENAI_MODEL_SUPERVISOR", "gpt-4o-mini")

#Configurar Chrome para Kaleido v1
def _set_chromium_executable(path: str):
    """Intenta fijar la ruta de Chrome/Chromium en Plotly tanto en defaults como en kaleido.scope."""
    try:
        # Plotly 6+
        if hasattr(pio, "defaults"):
            setattr(pio.defaults, "chromium_executable", path)  # puede lanzar si tu versión no lo soporta
    except Exception as e:
        print("[kaleido] pio.defaults.chromium_executable no disponible:", e)
    try:
        # Compatibilidad (Plotly ≤6 / Kaleido v1)
        if hasattr(pio, "kaleido") and hasattr(pio.kaleido, "scope"):
            pio.kaleido.scope.chromium_executable = path
    except Exception as e:
        print("[kaleido] pio.kaleido.scope.chromium_executable no disponible:", e)

# 1) Intenta usar la ruta del sistema (inyectada por compose)
chrome_hint = os.environ.get("KAL_CHROME_PATH")
if chrome_hint and os.path.exists(chrome_hint):
    _set_chromium_executable(chrome_hint)
else:
    # 2) Descarga embebido con Kaleido (primera vez tarda)
    try:
        from kaleido import get_chrome_sync
        chrome_path = get_chrome_sync()
        _set_chromium_executable(chrome_path)
    except Exception as e:
        print("[kaleido] No pude conseguir Chrome embebido:", e)

# Formato por defecto
try:
    if hasattr(pio, "defaults"):
        pio.defaults.to_image = dict(format="png")
except Exception:
    pass
try:
    pio.kaleido.scope.default_format = "png"
except Exception:
    pass

# ================== STATE ==================
class PipelineState(TypedDict, total=False):
    query: str
    tipo: Literal["jugador", "portero"]
    df_pre_filtrado: object
    df_filtrado: object
    resultados: object
    df_top3: object
    explicacion: str
    chat_id: str
    decision: str
    chart_paths: list[str]

# ================== NODES ==================
def nodo_supervisor(state: PipelineState) -> PipelineState:
    prompt = ChatPromptTemplate.from_template(
        """Decide si la siguiente consulta trata sobre scouting de fútbol (jugadores/porteros, fichajes, estadísticas, rendimiento).
Si SÍ: responde 'ok'. Si NO: responde 'fin'.

Consulta:
----------
{query}
----------

Tu respuesta (ok/fin):"""
    )
    llm = ChatOpenAI(model=OPENAI_MODEL_SUPERVISOR, temperature=0)
    decision = (prompt | llm).invoke({"query": state["query"]}).content.strip().lower()
    print(f"SUPERVISOR: {decision}")
    return {**state, "decision": decision[:3]}  # 'ok' o 'fin'

def supervisor_decision(state: PipelineState) -> str:
    return "agente0" if state.get("decision") == "ok" else "nodo_send_to_telegram"

def nodo_agente0(state: PipelineState) -> PipelineState:
    a0 = Agente0VectorRetriever()
    df_pre, tipo = a0.recuperar(state["query"])
    return {**state, "df_pre_filtrado": df_pre, "tipo": tipo}

def nodo_agente1(state: PipelineState) -> PipelineState:
    a1 = Agente1HardFilter()
    df_filt, tipo = a1.filtrar(state["df_pre_filtrado"], state["query"], state["tipo"])
    return {**state, "df_filtrado": df_filt, "tipo": tipo}

def nodo_agente2(state: PipelineState) -> PipelineState:
    a2 = ScoreEvaluatorAgent()
    resultados, df_top3 = a2.score_dataframe(state["df_filtrado"], state["query"], state["tipo"])
    return {**state, "resultados": resultados, "df_top3": df_top3}

def nodo_resultados_completos(state: PipelineState) -> PipelineState:
    a3 = Agente3Explanation()
    a4 = GraphComparisonAgent()

    explicacion = a3.explicar_resultados(state["query"], state["resultados"])
    fig1, fig2 = a4.graph_comparison(state["resultados"])

    # Guarda PNGs en una ruta temporal compatible con Windows
    tmpdir = tempfile.gettempdir()
    chart1_path = os.path.join(tmpdir, "chart_percentiles.png")
    chart2_path = os.path.join(tmpdir, "chart_percentiles_per90.png")
    wrote_png = False
    try:
        # Intento PNG (requiere Chrome/Kaleido v1)
        pio.write_image(fig1, chart1_path, scale=2, width=1200, height=900)
        pio.write_image(fig2, chart2_path, scale=2, width=1200, height=900)
        wrote_png = True
    except Exception as e:
        print("[charts] write_image falló, uso HTML fallback:", e)
        # Fallback HTML (se puede enviar como documento o ignorar en Telegram)
        chart1_path = "/tmp/chart_percentiles.html"
        chart2_path = "/tmp/chart_percentiles_per90.html"
        pio.write_html(fig1, chart1_path, include_plotlyjs="cdn", full_html=True)
        pio.write_html(fig2, chart2_path, include_plotlyjs="cdn", full_html=True)

    print("TIPO CHART1:", type(fig1))
    print("TIPO CHART2:", type(fig2))

    return {
        **state,
        "explicacion": explicacion,
        "chart_paths": [p for p in [chart1_path, chart2_path] if os.path.exists(p)]
    }

def nodo_send_to_telegram(state: PipelineState) -> PipelineState:
    chat_id = state.get("chat_id")
    mensaje = state.get("explicacion") or "Lo siento, pero solo respondo preguntas sobre scouting de fútbol."
    if not BOT_TOKEN or not chat_id:
        print("[WARN] Falta TELEGRAM_BOT_TOKEN o chat_id. No se envía a Telegram.")
        print("\n=== MENSAJE ===\n", mensaje)
        return state

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    # texto
    try:
        requests.post(f"{base_url}/sendMessage", data={"chat_id": chat_id, "text": mensaje})
    except Exception as e:
        print(f"[telegram] error enviando mensaje: {e}")

    # gráficos (si hay)
    for path in state.get("chart_paths", []):
        try:
            if path.lower().endswith(".png"):
                with open(path, "rb") as f:
                    requests.post(f"{base_url}/sendPhoto", data={"chat_id": chat_id}, files={"photo": f})
        except Exception as e:
            print(f"[telegram] error enviando imagen {path}: {e}")

    return state

# ================== GRAPH ==================
grafo = StateGraph(PipelineState)
grafo.add_node("supervisor", nodo_supervisor)
grafo.add_node("agente0", nodo_agente0)
grafo.add_node("agente1", nodo_agente1)
grafo.add_node("agente2", nodo_agente2)
grafo.add_node("nodo_resultados_completos", nodo_resultados_completos)
grafo.add_node("nodo_send_to_telegram", nodo_send_to_telegram)

grafo.set_entry_point("supervisor")
grafo.add_conditional_edges("supervisor", supervisor_decision)
grafo.add_edge("agente0", "agente1")
grafo.add_edge("agente1", "agente2")
grafo.add_edge("agente2", "nodo_resultados_completos")
grafo.add_edge("nodo_resultados_completos", "nodo_send_to_telegram")
grafo.set_finish_point("nodo_send_to_telegram")

pipeline = grafo.compile()
