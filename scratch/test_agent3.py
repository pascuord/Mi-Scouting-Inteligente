
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from scouting.agents.agent0 import Agente0VectorRetriever
from scouting.agents.agent1 import Agente1HardFilter
from scouting.agents.agent2 import ScoreEvaluatorAgent
from scouting.agents.agent3 import Agente3Explanation

os.environ["LLM_PROVIDER"] = "openai"

a0 = Agente0VectorRetriever()
a1 = Agente1HardFilter()
a2 = ScoreEvaluatorAgent()
a3 = Agente3Explanation()

query = "defensa italiano"
tipo = "jugador"
df_faiss, _ = a0.recuperar(query, tipo=tipo)
print("A0 rows:", df_faiss.height)

df_filtrado, tipo_out = a1.filtrar(df_faiss, query, tipo)
print("A1 rows:", df_filtrado.height)

resultados, df_top3 = a2.score_dataframe(df_filtrado, query, tipo)
print("A2 resultados count:", len(resultados))

print("Agent3 formatting:")
print(a3.formatear_jugadores(resultados))

print("Invoking LLM...")
explicacion = a3.explicar_resultados(query, resultados)
print("LLM Output:")
print(explicacion)
