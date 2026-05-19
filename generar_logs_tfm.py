import os
import sys

# Forzar ejecución en CPU para evitar problemas de memoria
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

# Asegurar que la ruta src está en el path
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scouting.agents.pipeline import pipeline

# Batería de preguntas de tu TFM (Anexo D)
PREGUNTAS = [
    "Delantero de la liga escocesa con buen juego aéreo.",
    "Lateral derecho de la Eredivisie rápido y con buen centro.",
    "Mediocentro defensivo de la liga portuguesa con alta capacidad de recuperación de balón.",
    "Defensa central menor de 23 años de la liga suiza con buena salida de balón.",
    "Extremo izquierdo de la Championship inglesa con buen 1vs1 y capacidad de desborde.",
    "Pivote de la liga turca con buena salida de balón y valor inferior a 10 millones.",
    "Delantero sub-21 de ligas nórdicas con buen pressing y más de 0.40 goles por partido.",
    "Central zurdo de Sudamérica con más de 1.90 m, dominante en duelos aéreos y experiencia internacional.",
    "Interior ofensivo de segunda división francesa con buen último pase, alta producción de xA y contrato < 2 años.",
    "Reemplazo para Rodri: 22-27 años, posicionamiento defensivo, pases progresivos, < 35 millones.",
    "Búscame a LeBron James",
    "Búscame un portero que marque más de 20 goles por temporada"
]

# Modelos a probar
MODELOS = [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "groq", "model": "openai/gpt-oss-120b"},
    {"provider": "openai", "model": "gpt-5.5"}
]

# Abrir un archivo maestro para volcar absolutamente todo
with open("logs_completos_tfm.txt", "w", encoding="utf-8") as f:
    
    # Redirigir la salida estándar de Python (los prints) al archivo
    original_stdout = sys.stdout
    sys.stdout = f

    print("=" * 80)
    print("DUMP COMPLETO DE LOGS DE SCOUTING PARA TFM")
    print("=" * 80 + "\n")

    for m in MODELOS:
        os.environ["LLM_PROVIDER"] = m["provider"]
        if m["provider"] == "openai":
            os.environ["OPENAI_MODEL_SUPERVISOR"] = m["model"]
        else:
            os.environ["GROQ_MODEL_SUPERVISOR"] = m["model"]

        print(f"\n{'#' * 80}")
        print(f"### EVALUANDO PROVEEDOR: {m['provider'].upper()} | MODELO: {m['model']}")
        print(f"{'#' * 80}\n")

        for idx, pregunta in enumerate(PREGUNTAS, 1):
            print(f"\n--- [PREGUNTA {idx}/12] ---")
            print(f"Query: {pregunta}\n")
            
            try:
                pipeline.invoke({
                    "query": pregunta,
                    "chat_id": "dump_logs"
                })
            except Exception as e:
                print(f"!!! ERROR EN LA EJECUCIÓN !!! -> {e}")
            
            print("-" * 40)

    # Restaurar la salida por pantalla
    sys.stdout = original_stdout

print("✅ Todos los logs han sido volcados exitosamente en: logs_completos_tfm.txt")
