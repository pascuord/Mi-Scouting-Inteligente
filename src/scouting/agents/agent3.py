# src/scouting/agents/agente3.py
from __future__ import annotations
from openai import OpenAI
from typing import List, Dict, Any

# System Prompt — scouting
system_prompt = (
    "Eres un asistente experto en análisis futbolístico dentro de un sistema de scouting inteligente. "
    "Tu rol es analizar y justificar por qué los jugadores seleccionados encajan con una consulta hecha por un club. "
    "Estos jugadores han sido seleccionados por distintos agentes del sistema y representan las mejores opciones disponibles "
    "según la query proporcionada. Redacta un análisis profesional y constructivo en español claro y natural. "
    "Para cada jugador, comenta edad, posición, minutos jugados, pie, altura, valor, contrato restante y score. "
    "Justifica por qué encaja usando métricas clave (valor, percentil y peso) y valora per90 si ha jugado pocos minutos. "
    "Si hay rasgos ≥75, destácalos como fortalezas. No inventes datos: si falta algo, omítelo. "
    "Evita frases negativas; aporta lectura útil y positiva para el club."
)

few_shot_example = """
[Ejemplo de entrada]

Query: "Busco un defensa central joven y barato"

Jugadores seleccionados:

Nombre: Joaquín Martín
Edad: 21 años | Posición: Centre-Back | Posiciones secundarias: Left-Back
Pie dominante: Left | Altura: 1,84 m | Valor: €500K | Contrato: 1.0 años
Minutos jugados: 620 | Score total: 66.2
Liga: LaLiga (nivel competitivo intermedio)
Métricas clave:
- Aerial duels won: percentil 69, peso 0.13
- Clearances: percentil 72, peso 0.12
- Defensive duels won: percentil 61, peso 0.11
- Passes completed: percentil 58, peso 0.10
Rasgos destacados: Concentración (percentil 91), Acciones defensivas (percentil 84)

[Salida esperada]

Según las necesidades de la query y las métricas clave, estos son nuestros 3 candidatos con mejor puntuación:

**1. Joaquín Martín** (score: 66.2) sobresale como opción joven y coste asumible. A sus 21 años y con un valor de mercado de €500K, el horizonte contractual de 1 año abre una ventana de incorporación inmediata. Aunque acumula 620', sus percentiles por 90' son consistentes: despejes (72) y duelos aéreos (69) respaldan su perfil de central dominador en área propia. Su pie izquierdo y la experiencia puntual como lateral amplían recursos tácticos. Añade rasgos altos en concentración (p91) y acciones defensivas (p84), indicadores de solidez y margen de crecimiento.
"""

def _fmt_valor(valor_txt: str | None, valor_num: float | None = None) -> str:
    if isinstance(valor_num, (int, float)):
        if valor_num >= 1_000_000: return f"€{valor_num/1_000_000:.2f}m"
        if valor_num >= 1_000:     return f"€{valor_num/1_000:.0f}k"
        return f"€{int(valor_num)}"
    return valor_txt or "-"

def _orden_metricas_por_peso(res: Dict[str, Any]) -> List[str]:
    pesos = res.get("metricas_clave") or {}
    return [k for k,_ in sorted(pesos.items(), key=lambda kv: kv[1], reverse=True)]

def _fmt_linea_metricas(nombre_stat: str, datos: Dict[str, Any], prefer_per90: bool) -> str:
    raw = (datos or {}).get("raw", {}) or {}
    peso = float((datos or {}).get("peso", 0.0))
    pct = raw.get("percentile"); pct90 = raw.get("percentile_per90")
    val = raw.get("value"); per90 = raw.get("value_per90", raw.get("per90"))
    def _tofloat(x):
        try: return float(x)
        except: return None
    pct_f, pct90_f = _tofloat(pct), _tofloat(pct90)
    if pct_f is not None:
        if prefer_per90 and (pct90_f is not None) and (pct90_f != pct_f):
            return f"- {nombre_stat}: percentil {round(pct_f)} (por 90: {round(pct90_f)}), peso {peso:.3f}"
        return f"- {nombre_stat}: percentil {round(pct_f)}, peso {peso:.3f}"
    if prefer_per90 and isinstance(per90, (int,float)):
        return f"- {nombre_stat}: {per90} por 90', peso {peso:.3f}"
    if isinstance(val, (int,float,str)):
        return f"- {nombre_stat}: {val}, peso {peso:.3f}"
    return f"- {nombre_stat}: s/d, peso {peso:.3f}"

class Agente3Explanation:
    def __init__(self, model: str = "gpt-4o-mini"):
        # coge OPENAI_API_KEY del entorno (.env)
        self.client = OpenAI()
        self.model = model

    def formatear_jugadores(self, resultados: List[Dict]) -> str:
        bloques=[]
        for res in resultados[:3]:
            nombre = res.get("nombre","Desconocido")
            edad = res.get("age"); pie = (res.get("foot") or "-").capitalize()
            altura = res.get("height"); valor = _fmt_valor(res.get("market_value"), res.get("market_value_num"))
            score = round(res.get("score",0), 2)
            pos_princ = res.get("main_position"); pos_sec = ", ".join(res.get("other_positions",[]) or [])
            anios_contrato = res.get("años_contrato"); min_jugados = res.get("minutes_real")
            liga = res.get("liga"); nivel_liga = res.get("nivel_liga")

            contrato_txt = ""
            if anios_contrato is not None:
                if anios_contrato <= 1.0: contrato_txt = "ventana de incorporación inmediata"
                elif anios_contrato <= 2.5: contrato_txt = "disponibilidad a medio plazo"
                else: contrato_txt = "vinculación larga (negociación potencialmente costosa)"

            orden_metricas = _orden_metricas_por_peso(res)
            detalle = res.get("detalle", {}) or {}
            prefer_per90 = (min_jugados is not None) and (min_jugados < 750)
            metricas = []
            for nombre_stat in (orden_metricas or detalle.keys()):
                datos = detalle.get(nombre_stat, {})
                metricas.append(_fmt_linea_metricas(nombre_stat, datos, prefer_per90))
            metricas_txt = "\n".join(metricas)

            rasgos = res.get("rasgos", {}) or {}
            rasgos_destacados=[]
            for k,v in rasgos.items():
                try:
                    if float(v) >= 75: rasgos_destacados.append(f"{k} (percentil {int(float(v))})")
                except: pass
            rasgos_txt = ", ".join(rasgos_destacados)

            bloque = (
                f"Nombre: {nombre}\n"
                f"Edad: {edad} | Posición: {pos_princ}"
                f"{' | Posiciones secundarias: ' + pos_sec if pos_sec else ''}\n"
                f"Pie dominante: {pie} | Altura: {altura} | Valor: {valor}"
                f"{f' | Contrato: {anios_contrato} años' if anios_contrato is not None else ''}\n"
                f"Minutos jugados: {min_jugados if min_jugados is not None else '-'}"
                + ("  |  análisis ponderado por 90'" if prefer_per90 else "")
                + f" | Score total: {score}\n"
                f"Liga: {liga} ({nivel_liga})\n"
                f"Contrato: {contrato_txt}\n"
                f"Métricas clave:\n{metricas_txt}"
            )
            if rasgos_destacados:
                bloque += f"\nRasgos destacados: {rasgos_txt}"
            bloques.append(bloque)
        return "\n\n".join(bloques)

    def explicar_resultados(self, query: str, resultados: List[Dict]) -> str:
        jugadores_txt = self.formatear_jugadores(resultados)
        user_prompt = (
            f"[Tu turno]\n"
            f"Query: {query}\n\n"
            f"Jugadores seleccionados:\n\n"
            f"{jugadores_txt}\n\n"
            "Genera una explicación profesional destacando los aspectos positivos de cada jugador dentro del contexto de la búsqueda. "
            "Recuerda que son los mejores candidatos tras los filtros aplicados, y que los percentiles por 90 y rasgos deben valorarse especialmente si han jugado pocos minutos."
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":few_shot_example},
                {"role":"user","content":user_prompt},
            ],
            temperature=0.5,
            max_tokens=1200,
        )
        return resp.choices[0].message.content.strip()
