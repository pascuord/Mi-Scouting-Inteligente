# src/scouting/agents/agente3.py
from __future__ import annotations
from openai import OpenAI
from typing import List, Dict, Any

# System Prompt — scouting
system_prompt = (
    "Eres un asistente experto en análisis futbolístico dentro de un sistema de scouting inteligente. "
    "Tu rol es analizar y justificar por qué los jugadores seleccionados encajan con una consulta hecha por un club. "
    "Estos jugadores han sido seleccionados por distintos agentes del sistema y representan las mejores opciones disponibles "
    "según la query proporcionada. Redacta un análisis profesional y constructivo en {lang} claro y natural, sin tecnicismos innecesarios ni expresiones forzadas. "
    "Para cada jugador, comenta edad, posición, minutos jugados, pie, altura, valor, contrato restante y score. "
    "Justifica por qué encaja usando métricas clave (percentil, percentil por 90 y peso métrica) y valora más percentil por 90 si ha jugado pocos minutos (<750).  "
    "Interpreta correctamente las métricas con nombre negativo (p.ej., Dispossessed, Dribbled past, Fouls committed): pese a su nombre, un percentil ALTO implica menos pérdidas/regates sufridos/faltas, lo cual es positivo; "
    "un percentil BAJO en ellas indica debilidad y no debe presentarse como fortaleza. "
    "Contrato: menos años = mayor facilidad de incorporación inmediata (posible coste inferior al valor). Contrato largo = encaje a largo plazo y potencial coste alto. "
    "Si el jugador no es de la posición objetivo de la query pero ha actuado ahí (Posiciones secundarias), indícalo y advierte que sus percentiles se comparan con su posición principal pero que podría ser interesante."
    "En caso de que no coincidan {{liga}} y {{liga_stats}} puedes indicar algo así como: Actualmente en {{liga}}, pero las estadísticas provienen de {{liga_stats}} {{temporada_stats}}"
    "Si hay rasgos ≥75, destácalos como fortalezas. No inventes datos: si falta algo, omítelo. "
    "Regla estricta: NO reasignes la posición. Usa exactamente el campo 'Posición'. Si la posición principal no coincide con la buscada (p.ej., extremos), dilo explícitamente y no etiquetes al jugador como tal; explica su encaje potencial y advierte que los percentiles se comparan con su demarcación principal."
    "Evita frases negativas; aporta lectura útil y positiva para el club."
)

few_shot_example = """
[Ejemplo de entrada]

Query: "Busco un defensa central joven y barato"

Jugadores seleccionados:

Nombre: Joaquín Martín | Nacionalidad: España
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

[Ejemplo de entrada]

Query: "Portero sobrio, con buena salida por alto y que sepa distribuir bien el balón"

Jugadores seleccionados:

Nombre: Diego López  | Nacionalidad: España
Edad: 24 años | Posición: Portero
Pie dominante: Derecho | Altura: 1,90 m | Valor: €500K | Contrato: 1.5 años
Minutos jugados: 520  |  análisis ponderado por 90' | Score total: 67.1
Liga: Segunda División (nivel competitivo intermedio)
Contrato: disponibilidad a medio plazo
Métricas clave:
- High claims: percentil 83 (percentil por 90: 68.2), peso 0.25
- Accurate long balls: percentil 79 (percentil por 90: 73.4), peso 0.22
- Save percentage: percentil 74, peso 0.20
- Goals prevented: percentil 72, peso 0.18
- Pass accuracy: percentil 61, peso 0.15
Rasgos destacados: Seguridad por alto (percentil 82), Juego con los pies (percentil 79)

[Salida esperada]

Según los criterios de la búsqueda, estos son los tres porteros que mejor encajan:

**1. Diego López** (score: 67.1) es un portero joven y sobrio que destaca especialmente en el juego aéreo y la distribución. A sus 24 años, y con un valor asequible de €500K, su contrato de 1.5 años ofrece una opción viable a medio plazo. Ha disputado 520 minutos esta temporada, por lo que el análisis principal se basa en sus datos por 90 minutos. En salidas por alto alcanza un percentil 83 (6.2 por partido), y en balones largos precisos, un percentil 79, confirmando su capacidad para distribuir desde atrás. Su porcentaje de paradas (p74) y goles evitados (p72) reflejan un rendimiento sólido bajo palos. Además, muestra buena precisión en el pase (p61). Tiene rasgos destacados en seguridad aérea y juego con los pies, que refuerzan su perfil como portero sobrio, fiable y con buena salida.
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
    def __init__(self, model: str = "gpt-4o-mini", lang: str = "es"):
        # coge OPENAI_API_KEY del entorno (.env)
        self.client = OpenAI()
        self.model = model
        self.lang = lang  # "es" | "en" | "fr" | "it" | "de" (del supervisor)

        # Inyecta el idioma humano-legible en el system prompt:
        lang_label = {
            "en": "inglés",
            "fr": "francés",
            "it": "italiano",
            "de": "alemán",
            "es": "español",
        }.get((lang or "es").lower(), "español")
        self.system_prompt = system_prompt.format(lang=lang_label)


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
            liga_stats = res.get("liga_stats"); temporada_stats = res.get("temporada_stats")

            contrato_txt = ""
            if anios_contrato is not None:
                if anios_contrato <= 1.0: contrato_txt = "ventana de incorporación inmediata y posible coste por debajo del valor"
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
                f"Minutos jugados: {min_jugados if min_jugados is not None else '-'} en {liga_stats} {temporada_stats} ({nivel_liga})"
                + ("  |  análisis ponderado por 90'" if prefer_per90 else "")
                + f" | Score total: {score}\n"
                f"Liga actual: {liga} \n"
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
            f"Genera la explicación en {self.lang}. "
            "Debe ser profesional destacando los aspectos positivos de cada jugador dentro del contexto de la búsqueda. "
            "Recuerda que son los mejores candidatos tras los filtros aplicados, que los percentiles por 90 deben valorarse especialmente si han jugado pocos minutos (<750) y deben mencionarse como cualidades destacadas los rasgos que superen el valor de percentil 75."
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role":"system","content":self.system_prompt},
                {"role":"user","content":few_shot_example},
                {"role":"user","content":user_prompt},
            ],
            temperature=0.35,
            max_tokens=1500,
        )
        return resp.choices[0].message.content.strip()
