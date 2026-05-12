# src/scouting/pipeline.py
from __future__ import annotations
import os
import tempfile
from typing import TypedDict, Literal
import json

import requests
import plotly.io as pio
from langgraph.graph import StateGraph
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# --- IMPORT PARA OPENAI ---
from langchain_openai import ChatOpenAI

# Agentes
from scouting.agents.agent0 import Agente0VectorRetriever
from scouting.agents.agent1 import Agente1HardFilter
from scouting.agents.agent2 import ScoreEvaluatorAgent
from scouting.agents.agent3 import Agente3Explanation
from scouting.agents.agent4 import GraphComparisonAgent
from scouting.agents.common import get_llm_provider, get_openai_key, jlog


# ================== ENV & KALEIDO ==================
load_dotenv()  # lee .env en la raíz
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ================== CONFIGURACIÓN DEL LLM GLOBAL ==================
# Definimos el LLM aquí arriba para que TODAS las funciones puedan usarlo
llm = ChatOpenAI(
    temperature=0,
    model_name="gpt-5.4-mini",
    api_key=os.getenv("OPENAI_API_KEY")
)

# DEBUG: Mostrar configuración del LLM
print("=" * 60)
print("[PIPELINE] LLM Configuration:")
print(f"  Model: {llm.model_name}")
print(f"  Provider: OpenAI")
print(f"  Temperature: {llm.temperature}")
print(f"  API Key: {'✓ Configured' if os.getenv('OPENAI_API_KEY') else '✗ NOT CONFIGURED'}")
print("=" * 60)

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

#Para el ajuste de los idiomas
def _json_loads_relaxed(s: str) -> dict:
    try:
        return json.loads(s)
    except Exception:
        s = s.replace("“","\"").replace("”","\"").replace("’","'")
        try:
            return json.loads(s)
        except Exception:
            return {}

# ================== STATE ==================
class PipelineState(TypedDict, total=False):
    query: str
    query_norm: str           # español normalizado por el supervisor
    lang: Literal["es","en","fr","it","de"]  # idioma original detectado
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
    
    prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Eres un supervisor de un sistema de scouting de fútbol. "
     "Devuelve SOLO JSON válido con las claves: "
     "domain ('ok'|'fin'), lang ('es'|'en'|'fr'|'it'|'de'), query_es (texto).\n\n"
     "REGLAS DURAS:\n"
     "1) SOLO están permitidas consultas de scouting de fútbol de JUGADORES o PORTEROS. "
     "Incluyen búsquedas sobre posiciones (extremo, lateral, portero, delantero, mediocentro, etc.), "
     "cualidades futbolísticas (regate, gol, centros, duelos, altura, pie dominante, valor de mercado, contrato, edad, etc.) "
     "y métricas estadísticas (xG, xA, percentiles, por 90, etc.).\n"
     "2) Si la consulta trata de CUALQUIER OTRO tema (política, música, recetas, marcas, fórmulas químicas, clima, etc.), "
     "entonces siempre responde con domain='fin'.\n"
     "3) Decide 'lang' únicamente por el texto original (es/en/fr/it/de).\n"
     "4) Si domain='ok' y lang!='es', traduce literalmente al español neutro en 'query_es', "
     "sin cambiar cifras, unidades, comparadores, símbolos (€/%), ni nombres propios. "
     "Normaliza roles a español (winger→extremo, fullback→lateral, holding midfielder→mediocentro defensivo, box-to-box→interior).\n"
     "5) Si el original ya está en español (lang='es'), 'query_es' debe ser EXACTAMENTE el original (sin reescribirlo).\n\n"
     "EJEMPLOS:\n"
     "- 'Extremo regateador…' → {{\"domain\": \"ok\", \"lang\": \"es\", \"query_es\": \"Extremo regateador…\"}}\n"
     "- 'Best goalkeeper…' → {{\"domain\": \"ok\", \"lang\": \"en\", \"query_es\": \"Portero menor de 25 con buena distribución\"}}\n"
     "- '¿Cuál es la fórmula de la Coca-Cola?' → {{\"domain\": \"fin\", \"lang\": \"es\", \"query_es\": \"¿Cuál es la fórmula de la Coca-Cola?\"}}\n"
     "- 'Tiempo mañana en Madrid' → {{\"domain\": \"fin\", \"lang\": \"es\", \"query_es\": \"Tiempo mañana en Madrid\"}}\n"
    ),
    ("human",
     "Decide dominio e idioma (es/en/fr/it/de) y, si procede, TRADUCE:\n\n"
     "Consulta (texto ORIGINAL):\n----------\n{query}\n----------\n\n"
     "Responde SOLO JSON válido.")
    ])

    # Trazabilidad de proveedor/modelo para confirmar consistencia de backend en el experimento del TFM.
    jlog("supervisor_llm_invoke", provider="openai", model=os.getenv("OPENAI_MODEL_SUPERVISOR", "gpt-4o-mini"))
    raw = (prompt | llm).invoke({"query": state["query"]}).content.strip()
    
    # Limpieza en caso de que el LLM meta markdown ```json ... ```
    # FIX: Sanitización de respuesta del LLM (Groq/Llama 3).
    # Previene JSONDecodeError eliminando los bloques de formato Markdown (```json ... ```) 
    # que el modelo suele añadir alrededor de su respuesta estructural.
    if raw.startswith("```json"):
        raw = raw.replace("```json", "", 1)
    if raw.endswith("```"):
        raw = raw[::-1].replace("```", "", 1)[::-1]
    raw = raw.strip()

    data = _json_loads_relaxed(raw)

    decision = (data.get("domain") or "fin").lower()
    lang = (data.get("lang") or "es").lower()
    if lang not in ("es","en","fr","it","de"):
        lang = "es"
    query_es = data.get("query_es") or state["query"]

    print(f"[SUPERVISOR] domain={decision} lang={lang} query_es={query_es[:140]}...")
    return {**state, "decision": decision, "lang": lang, "query_norm": query_es}

def supervisor_decision(state: PipelineState) -> str:
    return "agente0" if state.get("decision") == "ok" else "nodo_send_to_telegram"

def nodo_agente0(state: PipelineState) -> PipelineState:
    a0 = Agente0VectorRetriever()
    df_pre, tipo = a0.recuperar(state["query_norm"])
    return {**state, "df_pre_filtrado": df_pre, "tipo": tipo}

def nodo_agente1(state: PipelineState) -> PipelineState:
    a1 = Agente1HardFilter(llm=llm)
    df_filt, tipo = a1.filtrar(state["df_pre_filtrado"], state["query_norm"], state["tipo"])
    return {**state, "df_filtrado": df_filt, "tipo": tipo}

def nodo_agente2(state: PipelineState) -> PipelineState:
    a2 = ScoreEvaluatorAgent()
    resultados, df_top3 = a2.score_dataframe(state["df_filtrado"], state["query_norm"], state["tipo"])
    return {**state, "resultados": resultados, "df_top3": df_top3}


def _write_fallback_image(path: str, text: str, mode: str = "PNG"):
    """
    Crea una imagen sencilla con un mensaje de fallback para que Telegram reciba algo
    y podamos diagnosticar sin mirar logs.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 1200, 600
        img = Image.new("RGB", (W, H), (30, 30, 30))
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.load_default()
        except Exception:
            font_title = None
        # título
        draw.text((W//2, 80), "ScoutingInteligente charts", fill=(230, 230, 230),
                  anchor="mm", font=font_title)
        # cuerpo
        draw.text((W//2, H//2), f"fallback: {text}", fill=(200, 200, 200),
                  anchor="mm", font=font_title, align="center")
        # nota
        draw.text((W//2, H-40), "Se envía imagen de fallback para diagnóstico",
                  fill=(150, 150, 150), anchor="mm", font=font_title)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path, format=mode)
        return path
    except Exception:
        # último recurso: crear un archivo vacío para que el nodo no pete
        try:
            open(path, "wb").close()
        except Exception:
            pass
        return path


def nodo_resultados_completos(state: PipelineState) -> PipelineState:
    a3 = Agente3Explanation(lang=state.get("lang","es"))
    a4 = GraphComparisonAgent()

    # --- FLUJO AGENTE 3 (Explicación / OpenAI-Groq) ---
    jlog("agent3_explanation_start", query=state["query"], candidates=len(state.get("resultados", [])))
    
    try:
        if not state.get("resultados"):
            # Fallback local si no hay resultados para evitar llamada innecesaria al LLM
            explicacion = {
                "en": "No players were found matching your criteria.",
                "fr": "Aucun joueur n'a été trouvé correspondant à vos critères.",
                "it": "Non sono stati trovati giocatori corrispondenti ai tuoi criteri.",
                "de": "Es wurden keine Spieler gefunden, die Ihren Kriterien entsprechen.",
                "es": "No se han encontrado jugadores que cumplan con los criterios seleccionados."
            }.get(state.get("lang", "es"), "No se han encontrado resultados.")
        else:
            # El Agente 3 escribe en la clave 'explicacion' tras invocar al LLM
            explicacion = a3.explicar_resultados(state["query"], state["resultados"])
        
        if not explicacion:
            explicacion = "Error: El Agente 3 generó una respuesta vacía."
            
        jlog("agent3_explanation_done", success=True, length=len(explicacion))
    except Exception as e:
        jlog("agent3_explanation_error", error=str(e))
        explicacion = "Lo siento, se produjo un error al generar la explicación técnica."

    tmpdir = tempfile.gettempdir()

    # --- Collage de radares (PNG) ---
    radar_collage_path = os.path.join(tmpdir, "radars_collage.png")
    try:
        real_radar_path = a4.build_radar_collage(
            state["resultados"],
            out_dir=tmpdir,
            filename="radars_collage.png",
        )
        radar_collage_path = real_radar_path or radar_collage_path
        print("[charts] radar collage OK:", radar_collage_path)
    except Exception as e:
        msg = f"radars_collage failed: {e.__class__.__name__}"
        print("[charts]", msg)
        radar_collage_path = _write_fallback_image(radar_collage_path, msg, mode="PNG")

    # --- Collage de pizzas (JPG, más ligero) ---
    pizza_collage_path = os.path.join(tmpdir, "profiles_comparison.jpg")
    try:
        real_pizza_path, _ = a4.build_pizza_collage(
            state["resultados"],
            out_dir=tmpdir,
            filename_collage="profiles_comparison.jpg",
            save_individual=False,
            layout="column",
            dpi=180
        )
        pizza_collage_path = real_pizza_path or pizza_collage_path
        print("[charts] pizza collage OK:", pizza_collage_path)
    except Exception as e:
        msg = f"pizza_collage failed: {e.__class__.__name__}"
        print("[charts]", msg)
        pizza_collage_path = _write_fallback_image(pizza_collage_path, msg, mode="JPEG")

    # --- Clamp de existencia y lista final ---
    chart_paths = [p for p in [radar_collage_path, pizza_collage_path] if p and os.path.exists(p)]
    print("[charts] chart_paths finales:", chart_paths)

    return {
        **state,
        "explicacion": explicacion,
        "chart_paths": chart_paths
    }


def nodo_send_to_telegram(state: PipelineState) -> PipelineState:
    chat_id = state.get("chat_id")
    lang = state.get("lang","es")
    if state.get("decision") != "ok":
        mensaje = {
            "en": "Sorry, I only answer football scouting queries (players/goalkeepers).",
            "fr": "Désolé, je ne réponds qu’aux requêtes de scouting de football (joueurs/gardiens).",
            "it": "Spiacente, rispondo solo a richieste di scouting calcistico (giocatori/portieri).",
            "de": "Sorry, ich beantworte nur Scouting-Anfragen im Fußball (Feldspieler/Torhüter).",
            "es": "Lo siento, pero solo respondo preguntas sobre scouting de fútbol."
        }.get(lang, "Lo siento, pero solo respondo preguntas sobre scouting de fútbol.")
    else:
        mensaje = state.get("explicacion") or {
            "en": "Sorry, an unexpected error occurred.",
            "fr": "Désolé, une erreur inattendue s’est produite.",
            "it": "Spiacente, si è verificato un errore imprevisto.",
            "de": "Entschuldigung, es ist ein unerwarteter Fehler aufgetreten.",
            "es": "Lo siento, se produjo un error inesperado."
        }.get(lang, "Lo siento, se produjo un error inesperado.")
    if not BOT_TOKEN or not chat_id:
        print("[WARN] Falta TELEGRAM_BOT_TOKEN o chat_id. No se envía a Telegram.")
        print("\n=== MENSAJE ===\n", mensaje)
        return state

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    # texto
    try:
        # Telegram API limit is 4096 characters per message
        max_length = 4000
        for i in range(0, len(mensaje), max_length):
            chunk = mensaje[i:i+max_length]
            resp_txt = requests.post(f"{base_url}/sendMessage", data={"chat_id": chat_id, "text": chunk})
            print(f"[telegram] respuesta texto {resp_txt.status_code}: {resp_txt.text[:200]}")
    except Exception as e:
        print(f"[telegram] error enviando mensaje: {e}")

    # gráficos (si hay)
    for path in state.get("chart_paths", []):
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in [".png", ".jpg", ".jpeg"] and os.path.exists(path):
                print(f"[telegram] enviando imagen: {path}")
                with open(path, "rb") as f:
                    resp = requests.post(
                        f"{base_url}/sendPhoto",
                        data={"chat_id": chat_id},
                        files={"photo": f}
                    )
                print(f"[telegram] respuesta Telegram {resp.status_code}: {resp.text[:200]}")
            else:
                print(f"[telegram] no se envía {path} (no existe o no es imagen)")
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