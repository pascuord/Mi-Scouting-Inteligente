
import os
import sys

# Add src to pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from scouting.agents.agent4 import GraphComparisonAgent

a4 = GraphComparisonAgent()
resultados = [
    {
        "nombre": "Manuel Locatelli",
        "metricas_clave": {"Duels won": 0.5, "Pass accuracy": 0.5},
        "detalle": {
            "Duels won": {"raw": {"percentile": 80, "percentile_per90": 85}},
            "Pass accuracy": {"raw": {"percentile": 90, "percentile_per90": 92}}
        }
    },
    {
        "nombre": "Bryan Cristante",
        "metricas_clave": {"Duels won": 0.5, "Pass accuracy": 0.5},
        "detalle": {
            "Duels won": {"raw": {"percentile": 70, "percentile_per90": 75}},
            "Pass accuracy": {"raw": {"percentile": 80, "percentile_per90": 82}}
        }
    },
    {
        "nombre": "Roberto Gagliardini",
        "metricas_clave": {"Duels won": 0.5, "Pass accuracy": 0.5},
        "detalle": {
            "Duels won": {"raw": {"percentile": 60, "percentile_per90": 65}},
            "Pass accuracy": {"raw": {"percentile": 70, "percentile_per90": 72}}
        }
    }
]

try:
    print("Testing radar...")
    out_dir = "/tmp/test_agent4"
    os.makedirs(out_dir, exist_ok=True)
    res = a4.build_radar_collage(resultados, out_dir=out_dir)
    print("Radar OK:", res)
except Exception as e:
    import traceback
    traceback.print_exc()

try:
    print("Testing pizza...")
    res2 = a4.build_pizza_collage(resultados, out_dir=out_dir)
    print("Pizza OK:", res2)
except Exception as e:
    import traceback
    traceback.print_exc()

